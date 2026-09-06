"""Unit tests for the improved PDFParser covering digital PDFs, scanned PDFs, multi-page, and empty pages."""
from __future__ import annotations

import io
import fitz
import pytest
from PIL import Image, ImageDraw

from app.parsers.pdf import PdfParseResult, pdf_parser


def create_digital_pdf_bytes(pages_text: list[list[str]]) -> bytes:
    """Helper to generate an in-memory digital PDF with PyMuPDF text insertion."""
    doc = fitz.open()
    for page_lines in pages_text:
        page = doc.new_page(width=595, height=842)
        y = 72
        for line in page_lines:
            page.insert_text((72, y), line, fontsize=12)
            y += 30
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_scanned_pdf_bytes(text_on_image: str) -> bytes:
    """Helper to generate an image-only PDF page simulating a flatbed scan."""
    # Create PIL image containing drawn text
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 50), text_on_image, fill=(0, 0, 0))

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_data = img_buf.getvalue()

    # Embed as single full-page image in PDF without digital text
    doc = fitz.open()
    page = doc.new_page(width=600, height=300)
    page.insert_image(page.rect, stream=img_data)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# --- Digital PDF Tests ---

@pytest.mark.anyio
async def test_pdf_digital_text_extraction():
    """Verify digital PDF text is directly extracted with high confidence and bounding boxes."""
    lines = [
        "Engineering Facility Inspection Report",
        "Equipment Serial: ENG-44021",
        "Operating Pressure: 450 kPa (Standard)",
        "Check Valve Status: Operational",
    ]
    raw_pdf = create_digital_pdf_bytes([lines])

    res: PdfParseResult = await pdf_parser.parse(
        file_bytes=raw_pdf,
        filename="digital_test.pdf",
        document_id="doc_dig",
        file_hash="hash_dig",
    )

    assert isinstance(res, PdfParseResult)
    assert res.total_pages == 1
    assert res.metadata["digital_pages"] == 1
    assert res.metadata["scanned_pages"] == 0

    page1 = res.pages[0]
    assert page1.page_number == 1
    assert page1.is_digital is True
    assert page1.extraction_method == "PyMuPDF-Direct"

    # Verify extracted text and bounding boxes
    assert "Engineering Facility Inspection Report" in page1.text
    assert len(page1.elements) >= 1
    first_elem = page1.elements[0]
    assert first_elem.confidence >= 0.95
    assert len(first_elem.bbox) == 4
    assert first_elem.bbox[2] > first_elem.bbox[0]  # x2 > x1
    assert first_elem.bbox[3] > first_elem.bbox[1]  # y2 > y1


# --- Scanned / Image-Only PDF Tests ---

@pytest.mark.anyio
async def test_pdf_scanned_ocr_fallback():
    """Verify image-only / scanned PDF pages trigger rendering and OCR extraction."""
    raw_pdf = create_scanned_pdf_bytes("SCANNED REPORT 2026")

    res = await pdf_parser.parse(
        file_bytes=raw_pdf,
        filename="scanned_test.pdf",
        document_id="doc_scan",
        file_hash="hash_scan",
    )

    assert res.total_pages == 1
    assert res.metadata["scanned_pages"] == 1
    assert res.metadata["digital_pages"] == 0

    page1 = res.pages[0]
    assert page1.is_digital is False
    assert "OCR" in page1.extraction_method
    assert len(page1.elements) >= 1


# --- Multi-Page PDF Tests ---

@pytest.mark.anyio
async def test_pdf_multiple_pages():
    """Verify multi-page PDF preserves page numbering and page-by-page elements."""
    pages = [
        ["Page 1: Overview and Executive Summary", "Section 1.1 Scope of audit"],
        ["Page 2: Technical Observations", "Compressor Line B pressure readings"],
        ["Page 3: Remediation Roadmap", "Schedule maintenance for valve seals"],
    ]
    raw_pdf = create_digital_pdf_bytes(pages)

    res = await pdf_parser.parse(
        file_bytes=raw_pdf,
        filename="multipage.pdf",
        document_id="doc_multi_pdf",
        file_hash="hash_multi_pdf",
    )

    assert res.total_pages == 3
    assert len(res.pages) == 3
    assert res.pages[0].page_number == 1
    assert res.pages[1].page_number == 2
    assert res.pages[2].page_number == 3

    assert "Overview and Executive Summary" in res.pages[0].text
    assert "Compressor Line B" in res.pages[1].text
    assert "Remediation Roadmap" in res.pages[2].text


# --- Empty / Minimal Page Tests ---

@pytest.mark.anyio
async def test_pdf_empty_and_minimal_pages():
    """Verify empty and minimal pages parse cleanly without crashing."""
    doc = fitz.open()
    # Page 1: Completely empty blank page
    doc.new_page(width=595, height=842)
    # Page 2: Minimal text (single word)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((72, 72), "Index", fontsize=10)

    pdf_bytes = doc.tobytes()
    doc.close()

    res = await pdf_parser.parse(
        file_bytes=pdf_bytes,
        filename="minimal.pdf",
        document_id="doc_min",
        file_hash="hash_min",
    )

    assert res.total_pages == 2
    assert len(res.pages) == 2


# --- Resource Management & Error Handling Tests ---

@pytest.mark.anyio
async def test_pdf_corrupt_and_empty_error_handling():
    """Verify empty or corrupted PDF inputs raise clean ValueErrors."""
    # 0-byte input
    with pytest.raises(ValueError, match="empty"):
        await pdf_parser.parse(b"", filename="empty.pdf")

    # Corrupt PDF header
    with pytest.raises(ValueError, match="Invalid or corrupted"):
        await pdf_parser.parse(b"%PDF-corrupted-bytes-not-a-valid-document", filename="corrupt.pdf")
