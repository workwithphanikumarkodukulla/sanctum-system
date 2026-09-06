"""Direct vision analysis endpoints."""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.core.config import settings
from app.models.vision_client import vision_client
from app.processing.image import image_processor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"])

# NOTE: Authentication/Authorization Layer:
# In an enterprise deployment, inject an authentication dependency here.


@router.post("/analyze")
async def analyze_image_direct(
    file: UploadFile = File(...),
    prompt: str = Query(
        default="Transcribe all text, numbers, labels, formulas, and structural components visible in this image.",
        description="Prompt for the local vision model",
    ),
    auto_unload: bool | None = Query(
        default=None,
        description="Whether to immediately unload the model from RAM after analysis. Defaults to settings.OLLAMA_AUTO_UNLOAD.",
    ),
) -> dict[str, Any]:
    """Directly analyze an image using the local vision model (gemma4 via Ollama)."""
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    try:
        image = image_processor.load_image(image_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image format: {exc}",
        )

    should_unload = auto_unload if auto_unload is not None else settings.OLLAMA_AUTO_UNLOAD
    try:
        result = await vision_client.analyze_image(image, prompt=prompt)
        return {
            "filename": file.filename,
            "image_width": image.width,
            "image_height": image.height,
            "vision_result": result,
        }
    finally:
        if should_unload and getattr(vision_client, "is_model_loaded", False):
            try:
                await vision_client.unload_model()
            except Exception as unload_exc:
                logger.debug("Failed to auto-unload vision model after direct analysis: %s", unload_exc)


@router.post("/unload")
async def unload_vision_model(
    model: str | None = Query(
        default=None,
        description="Model to unload from RAM. Defaults to configured vision model.",
    ),
) -> dict[str, Any]:
    """Explicitly unload the vision model from host memory/VRAM to free resources."""
    unloaded = await vision_client.unload_model(model=model)
    return {
        "model": model or vision_client.model,
        "unloaded": unloaded,
        "status": "unloaded" if unloaded else "failed_or_offline",
    }
