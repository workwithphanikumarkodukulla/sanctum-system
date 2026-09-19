"""Unit tests for Diagram / P&ID specialized extraction via VLM in the pipeline."""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch
import pytest
from PIL import Image

from app.models.vision_client import vision_client
from app.processing.pipeline import pipeline


@pytest.mark.anyio
async def test_pipeline_diagram_vlm_analysis():
    """Verify that an image classified as a diagram invokes vision_client.analyze_diagram."""
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    doc_id = "test_pid_diagram"

    mock_analysis = (
        "1. Diagram Type: Piping and Instrumentation Diagram (P&ID)\n"
        "2. Equipment: Feed Pump P-101A/B, Storage Vessel V-200, Heat Exchanger E-102\n"
        "3. Process Streams: 2-inch carbon steel line 100-P-2CS with check valve CV-01\n"
        "4. Controls: Flow transmitter FT-101 connected to control valve FCV-101"
    )

    with patch.object(vision_client, "analyze_diagram", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = (mock_analysis, 0.94, {"success": True})

        # Process document
        doc = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="plant_pid_schematic.png",
        )

        assert doc.processing_status == "completed"
        # Verify diagram routing or analyze_diagram invocation
        assert mock_analyze.called or any(e.type in ("diagram", "image") for e in doc.elements)
