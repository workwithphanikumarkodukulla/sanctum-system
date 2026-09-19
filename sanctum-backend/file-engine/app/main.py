"""FastAPI application entry point for the Multimodal Evidence Engine."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.documents import router as documents_router
from app.api.evidence import router as evidence_router
from app.api.images import router as images_router
from app.core.config import settings
from app.evidence.storage import storage
from app.observability.processing_trace import trace_store

# Ensure Paddle C++ failure signal handler is disabled to avoid SIGSEGV on macOS during reload/signals
try:
    import paddle  # type: ignore
    if hasattr(paddle, "disable_signal_handler"):
        paddle.disable_signal_handler()
except Exception:
    pass

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("evidence_engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Multimodal Evidence Engine initialized. Confidence threshold: %.2f | Ollama URL: %s",
        settings.CONFIDENCE_THRESHOLD,
        settings.OLLAMA_BASE_URL,
    )
    yield
    logger.info("Multimodal Evidence Engine shutting down.")


app = FastAPI(
    title="Multimodal Evidence Engine",
    description=(
        "Standalone microservice for document and image ingestion producing cited, "
        "structured evidence JSON with PaddleOCR / Tesseract fallback and local Ollama gemma4 vision escalation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(documents_router)
app.include_router(images_router)
app.include_router(evidence_router)


@app.get("/health", tags=["system"])
async def health_check():
    """System health check and configuration report."""
    return {
        "status": "healthy",
        "service": "multimodal-evidence-engine",
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "vision_model": settings.OLLAMA_VISION_MODEL,
        "tesseract_configured": bool(settings.TESSERACT_CMD),
    }


@app.get("/debug/trace/{document_id}", tags=["debug"])
async def get_debug_trace(document_id: str):
    """Debug route returning the full machine-readable processing trace."""
    trace = trace_store.get(document_id)
    if trace:
        return trace.to_dict()
    doc = storage.get_document(document_id)
    if doc and doc.metadata and "processing_trace" in doc.metadata:
        return doc.metadata["processing_trace"]
    raise HTTPException(status_code=404, detail=f"Trace for document '{document_id}' not found.")


@app.get("/debug/trace/{document_id}/text", response_class=PlainTextResponse, tags=["debug"])
async def get_debug_trace_text(document_id: str):
    """Debug route returning the full human-readable ASCII audit trace."""
    trace = trace_store.get(document_id)
    if trace:
        return trace.to_human_readable()
    doc = storage.get_document(document_id)
    if doc and doc.metadata and "processing_trace" in doc.metadata:
        from app.api.documents import get_document_trace_text
        return await get_document_trace_text(document_id)
    raise HTTPException(status_code=404, detail=f"Trace for document '{document_id}' not found.")


@app.get("/debug/text/{document_id}", response_class=PlainTextResponse, tags=["debug"])
async def get_debug_text(document_id: str):
    """Debug route returning all extracted text elements combined in reading order."""
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    text_lines = [el.text for el in doc.elements if el.text and el.text.strip()]
    return "\n\n".join(text_lines)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
