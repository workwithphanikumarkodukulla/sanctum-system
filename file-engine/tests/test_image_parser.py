"""Unit tests for ImageParser covering PNG, JPG, WEBP, TIFF, sample OCR image, and extractor abstraction."""
from __future__ import annotations

import io
from pathlib import Path
import pytest
from PIL import Image

from app.parsers.image import ImageParseResult, ImageParser, image_parser


@pytest.fixture
def ocr_test_png_path() -> Path:
    p = Path(__file__).parent.parent / "sample_documents" / "ocr_test.png"
    assert p.exists(), "ocr_test.png should exist in sample_documents"
    return p


def create_test_image(fmt: str) -> bytes:
    """Helper to create a small test image in memory."""
    img = Image.new("RGB", (120, 60), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# --- Sample Documents OCR Test ---

@pytest.mark.anyio
async def test_image_parser_on_sample_ocr_test_png(ocr_test_png_path):
    """Verify OCR parsing on existing sample_documents/ocr_test.png."""
    with open(ocr_test_png_path, "rb") as f:
        img_bytes = f.read()

    res: ImageParseResult = await image_parser.parse(
        file_bytes=img_bytes,
        filename="ocr_test.png",
        document_id="doc_ocr_test",
        file_hash="hash_ocr_test",
    )

    assert isinstance(res, ImageParseResult)
    assert res.parser_name == "image_parser"
    assert res.image_width > 0
    assert res.image_height > 0
    assert res.metadata["vlm_invoked"] is False
    assert len(res.extracted_regions) >= 1

    # Verify normalization into EvidenceElements
    elements = res.to_evidence_elements()
    assert len(elements) == len(res.extracted_regions)
    assert elements[0].confidence > 0.0
    assert len(elements[0].bbox) == 4


# --- Format Support Tests: PNG, JPG, WEBP, TIFF ---

@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "TIFF"])
@pytest.mark.anyio
async def test_image_parser_formats(fmt):
    """Verify image parsing succeeds across PNG, JPG/JPEG, WEBP, and TIFF."""
    raw_bytes = create_test_image(fmt)
    res = await image_parser.parse(
        file_bytes=raw_bytes,
        filename=f"test.{fmt.lower()}",
        document_id="doc_fmt_test",
        file_hash="hash_fmt",
    )

    assert isinstance(res, ImageParseResult)
    assert res.image_width == 120
    assert res.image_height == 60
    assert res.metadata["ocr_engine"] in ("Tesseract", "PaddleOCR", "PP-StructureV3")


# --- Replaceable OCR Extractor Abstraction Test ---

@pytest.mark.anyio
async def test_replaceable_ocr_extractor_abstraction():
    """Verify ImageParser accepts an injected BaseOCRExtractor implementation."""
    class MockCustomExtractor:
        def __init__(self):
            self.called = False

        def extract(self, image: Image.Image):
            self.called = True
            return [
                {
                    "type": "text",
                    "bbox": [10.0, 10.0, 100.0, 40.0],
                    "text": "Extracted via Custom Mock Extractor",
                    "confidence": 0.99,
                    "extraction_model": "MockEngine-V1",
                    "raw": {},
                }
            ]

    mock_engine = MockCustomExtractor()
    custom_parser = ImageParser(extractor=mock_engine)

    dummy_bytes = create_test_image("PNG")
    res = await custom_parser.parse(dummy_bytes, filename="mock.png")

    assert mock_engine.called is True
    assert len(res.extracted_regions) == 1
    assert res.extracted_regions[0].text == "Extracted via Custom Mock Extractor"
    assert res.extracted_regions[0].extraction_model == "MockEngine-V1"
    assert res.full_text == "Extracted via Custom Mock Extractor"


# --- Error Handling Tests ---

@pytest.mark.anyio
async def test_image_parser_empty_and_corrupt():
    """Verify empty or corrupted images raise descriptive ValueErrors."""
    # 0 bytes
    with pytest.raises(ValueError, match="empty"):
        await image_parser.parse(b"", filename="empty.png")

    # Corrupted bytes
    with pytest.raises(ValueError, match="Invalid or unreadable"):
        await image_parser.parse(b"\x89PNG\r\n\x1a\ncorrupted_data_not_valid", filename="corrupt.png")
