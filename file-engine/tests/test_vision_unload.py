"""Tests for vision model auto-unloading and explicit unload mechanisms."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from PIL import Image
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.vision_client import VisionClient, vision_client
from app.processing.pipeline import EvidencePipeline

client = TestClient(app)


@pytest.mark.anyio
async def test_vision_client_unload_model_success():
    """Verify unload_model sends keep_alive=0 and marks model as unloaded."""
    vc = VisionClient(base_url="http://localhost:11434", model="gemma4:latest")
    vc._model_loaded = True

    mock_res = AsyncMock()
    mock_res.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_res
        success = await vc.unload_model()

        assert success is True
        assert vc.is_model_loaded is False
        mock_post.assert_called_once_with(
            "http://localhost:11434/api/generate",
            json={"model": "gemma4:latest", "keep_alive": 0},
        )


@pytest.mark.anyio
async def test_vision_client_unload_model_handles_failure():
    """Verify unload_model handles HTTP or network errors gracefully."""
    vc = VisionClient(base_url="http://localhost:11434", model="gemma4:latest")
    vc._model_loaded = True

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = Exception("Ollama daemon unreachable")
        success = await vc.unload_model()

        assert success is False
        # Does not crash, returns False
        assert vc.is_model_loaded is True


@pytest.mark.anyio
async def test_vision_client_tracks_loaded_state():
    """Verify analyze_image tracks loaded state based on keep_alive value."""
    vc = VisionClient(base_url="http://localhost:11434", model="gemma4")
    assert vc.is_model_loaded is False

    mock_res = AsyncMock()
    mock_res.status_code = 200
    mock_res.json = lambda: {"response": "Detected text"}

    img = Image.new("RGB", (50, 50), color="white")

    # Call without keep_alive: sets _model_loaded = True
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_res
        res = await vc.analyze_image(img)
        assert res["success"] is True
        assert vc.is_model_loaded is True

    # Call with keep_alive=0: sets _model_loaded = False (Ollama unloads immediately)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_res
        res = await vc.analyze_image(img, keep_alive=0)
        assert res["success"] is True
        assert vc.is_model_loaded is False


def test_api_vision_unload_endpoint():
    """Verify POST /api/vision/unload triggers unload and returns status."""
    with patch.object(vision_client, "unload_model", new_callable=AsyncMock) as mock_unload:
        mock_unload.return_value = True
        res = client.post("/api/vision/unload?model=gemma4:latest")

        assert res.status_code == 200
        data = res.json()
        assert data["model"] == "gemma4:latest"
        assert data["unloaded"] is True
        assert data["status"] == "unloaded"
        mock_unload.assert_called_once_with(model="gemma4:latest")


@pytest.mark.anyio
async def test_pipeline_auto_unloads_when_model_loaded(monkeypatch):
    """Verify EvidencePipeline unloads the vision model in finally block if loaded."""
    monkeypatch.setattr(settings, "OLLAMA_AUTO_UNLOAD", True)
    monkeypatch.setattr(vision_client, "_model_loaded", True)

    pipeline = EvidencePipeline()

    with patch.object(vision_client, "unload_model", new_callable=AsyncMock) as mock_unload:
        mock_unload.return_value = True

        # Process a minimal TXT document through pipeline
        await pipeline.process_document(
            document_id="test_unload_doc",
            file_bytes=b"Sample document text",
            filename="sample.txt",
        )

        mock_unload.assert_called_once()


@pytest.mark.anyio
async def test_pipeline_skips_unload_when_model_not_loaded(monkeypatch):
    """Verify EvidencePipeline does not call unload if model was never loaded."""
    monkeypatch.setattr(settings, "OLLAMA_AUTO_UNLOAD", True)
    monkeypatch.setattr(vision_client, "_model_loaded", False)

    pipeline = EvidencePipeline()

    with patch.object(vision_client, "unload_model", new_callable=AsyncMock) as mock_unload:

        await pipeline.process_document(
            document_id="test_no_unload_doc",
            file_bytes=b"Sample document text",
            filename="sample.txt",
        )

        mock_unload.assert_not_called()


@pytest.mark.anyio
async def test_enrich_and_build_elements_auto_unloads_when_model_loaded(monkeypatch):
    """Verify OCREnricher.enrich_and_build_elements auto-unloads when model was loaded."""
    from app.parsers.ocr_enricher import ocr_enricher

    monkeypatch.setattr(settings, "OLLAMA_AUTO_UNLOAD", True)
    monkeypatch.setattr(vision_client, "_model_loaded", True)

    with patch.object(vision_client, "unload_model", new_callable=AsyncMock) as mock_unload:
        mock_unload.return_value = True

        raw_elements = [
            {
                "text": "Header",
                "confidence": 0.95,
                "bbox": [10, 10, 100, 30],
                "type": "text",
            }
        ]
        page_img = Image.new("RGB", (200, 200), color="white")

        await ocr_enricher.enrich_and_build_elements(
            raw_elements=raw_elements,
            page_image=page_img,
            page_num=1,
            document_id="doc_enrich_test",
            file_hash="hash123",
        )

        mock_unload.assert_called_once()
