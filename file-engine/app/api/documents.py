"""Document ingestion and evidence retrieval endpoints."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import DocumentEvidence, DocumentMetadata, EvidenceElement
from app.evidence.storage import storage
from app.ingestion.detector import detector
from app.observability.processing_trace import trace_store
from app.processing.pipeline import pipeline

router = APIRouter(prefix="/api/documents", tags=["documents"])

# NOTE: Authentication/Authorization Layer:
# In an enterprise deployment, inject an authentication dependency here
# (e.g. `Depends(verify_api_key)` or `Depends(get_current_user_from_jwt)`).
# Example: router = APIRouter(prefix="/api/documents", dependencies=[Depends(require_auth)])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    sync: bool = False,
) -> Any:
    """Accepts any supported file (PDF, DOCX, PPTX, XLSX, CSV, TXT, PNG, JPG, WEBP, TIFF) and initiates the extraction pipeline.
    
    If `sync=True` is requested, processes synchronously and returns the completed DocumentEvidence.
    Otherwise returns 202 Accepted and processes asynchronously in background.
    """
    # 1. Sanitize filename against path traversal and null-byte attacks
    raw_filename = file.filename or "unknown_file"
    clean_filename = Path(raw_filename.replace("\\", "/")).name.replace("\x00", "").strip() or "unknown_file"

    # 2. Read and validate file content
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    # 3. Enforce configurable maximum upload size limit
    file_size = len(file_bytes)
    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Uploaded file size ({file_size} bytes) exceeds maximum allowable limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes.",
        )

    # 4. Compute content SHA-256 hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # 5. Detect actual file type by content/magic-bytes (never trusting extension alone)
    detection = detector.detect(file_bytes, filename=clean_filename)

    document_id = f"doc_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    # 6. Reject unsupported files cleanly
    if not detection.is_supported:
        err_msg = (
            f"Unsupported file format: {detection.error_message or detection.file_type.value}. "
            "Supported formats: PDF, DOCX, PPTX, XLSX, CSV, TXT, PNG, JPG/JPEG, WEBP, TIFF."
        )
        failed_doc = EvidenceBuilder.assemble_document(
            document_id=document_id,
            filename=clean_filename,
            file_type=detection.file_type.value,
            mime_type=detection.mime_type,
            file_size=file_size,
            file_hash=file_hash,
            total_pages=0,
            elements=[],
            status="failed",
            error=err_msg,
            created_at=created_at,
            completed_at=created_at,
            processing_time_ms=0.0,
        )
        storage.save(failed_doc)
        return {
            "document_id": document_id,
            "status": "failed",
            "detected_file_type": detection.file_type.value,
            "mime_type": detection.mime_type,
            "file_size": file_size,
            "file_hash": file_hash,
            "error": err_msg,
        }

    # 7. If synchronous processing requested, process directly
    if sync:
        assembled = await pipeline.process_document(
            document_id=document_id,
            file_bytes=file_bytes,
            filename=clean_filename,
        )
        return assembled

    # 8. Register initial processing state in storage for async flow
    initial_doc = DocumentEvidence(
        document_id=document_id,
        filename=clean_filename,
        file_type=detection.file_type.value,
        mime_type=detection.mime_type,
        file_size=file_size,
        file_hash=file_hash,
        total_pages=0,
        elements=[],
        overall_confidence=0.0,
        processing_status="processing",
        created_at=created_at,
    )
    storage.save(initial_doc)

    background_tasks.add_task(
        pipeline.process_document,
        document_id=document_id,
        file_bytes=file_bytes,
        filename=clean_filename,
    )

    return {
        "document_id": document_id,
        "status": "processing",
        "detected_file_type": detection.file_type.value,
        "mime_type": detection.mime_type,
        "file_size": file_size,
        "file_hash": file_hash,
    }


@router.get("/{document_id}")
async def get_document_status(document_id: str) -> dict[str, Any]:
    """Returns high-level status, page count, and overall confidence for a document."""
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    return {
        "document_id": doc.document_id,
        "status": doc.processing_status,
        "pages": doc.total_pages,
        "overall_confidence": doc.overall_confidence,
        "pipeline_summary": doc.metadata.get("pipeline_summary") if doc.metadata else None,
        "error": doc.error,
    }


@router.get("/{document_id}/evidence", response_model=DocumentEvidence)
async def get_document_evidence(document_id: str) -> DocumentEvidence:
    """Returns the full DocumentEvidence object for a document."""
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return doc


@router.get("/{document_id}/text", response_class=PlainTextResponse)
async def get_document_text(document_id: str) -> str:
    """Returns all extracted text elements combined in reading order as clean plain text."""
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    text_lines = [el.text for el in doc.elements if el.text and el.text.strip()]
    return "\n\n".join(text_lines)


@router.get("/{document_id}/metadata", response_model=DocumentMetadata)
async def get_document_metadata(document_id: str) -> DocumentMetadata:
    """Returns canonical document-level metadata without elements payload."""
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return doc.to_metadata()


@router.get("/{document_id}/pages/{page_number}", response_model=list[EvidenceElement])
async def get_page_evidence(document_id: str, page_number: int) -> list[EvidenceElement]:
    """Returns just the extracted EvidenceElements for a specific page."""
    doc = storage.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    elements = storage.get_page_elements(document_id, page_number)
    return elements


@router.get("/{document_id}/trace")
async def get_document_trace(document_id: str) -> dict[str, Any]:
    """Returns the provable execution trace / audit log in machine-readable JSON format."""
    trace = trace_store.get(document_id)
    if trace:
        return trace.to_dict()

    doc = storage.get_document(document_id)
    if doc and doc.metadata and "processing_trace" in doc.metadata:
        return doc.metadata["processing_trace"]

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Processing trace for document '{document_id}' not found.",
    )


@router.get("/{document_id}/trace/text", response_class=PlainTextResponse)
async def get_document_trace_text(document_id: str) -> str:
    """Returns the human-readable ASCII processing trace / audit log for jury inspection."""
    trace = trace_store.get(document_id)
    if trace:
        return trace.to_human_readable()

    doc = storage.get_document(document_id)
    if doc and doc.metadata and "processing_trace" in doc.metadata:
        pt_dict = doc.metadata["processing_trace"]
        lines = [
            "=" * 60,
            "SANCTUM DOCUMENT PROCESSING TRACE",
            "=" * 60,
            f"Document:     {pt_dict.get('filename', 'unknown')}",
            f"Document ID:  {pt_dict.get('document_id', document_id)}",
            f"SHA256:       {pt_dict.get('file_hash', 'unknown')}",
            f"Total Time:   {pt_dict.get('total_duration_ms', 0):.1f} ms",
            "-" * 60,
        ]
        for idx, ev in enumerate(pt_dict.get("events", []), 1):
            dur = f" ({ev.get('duration_ms')}ms)" if ev.get("duration_ms") is not None else ""
            lines.append(f"[{idx:02d}] {ev.get('stage')} — {ev.get('event')}{dur}")
            lines.append(f"     Component: {ev.get('component')}")
            lines.append(f"     Status:    {ev.get('status', '').upper()}")
            for k, v in ev.get("metadata", {}).items():
                lines.append(f"     {k}: {v}")
            if ev.get("error"):
                lines.append(f"     Error:     {ev.get('error')}")
            lines.append("")
        lines.append("=" * 60)
        lines.append(f"PIPELINE STATUS: {pt_dict.get('status', 'COMPLETED').upper()}")
        lines.append("=" * 60)
        return "\n".join(lines)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Processing trace for document '{document_id}' not found.",
    )
