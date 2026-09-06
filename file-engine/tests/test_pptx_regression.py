"""Comprehensive regression test suite for PowerPoint (PPTX) document processing."""
from __future__ import annotations

import io
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches, Pt

from app.classification.models import ContentType
from app.extractors.handwriting import HandwritingClassification
from app.parsers.pptx import (
    PptxImageItem,
    PptxParseResult,
    PptxTableItem,
    PptxTextItem,
    pptx_parser,
)
from app.processing.pipeline import pipeline


BLOODLINK_PATH = Path("sample_documents/BLOODLINK _ Team-CodeAlchemy.pptx")
HANDWRITTEN_NOTE_PATH = Path("sample_documents/handwritten_note.png")


def create_mock_image_bytes(text: str = "", width: int = 200, height: int = 100) -> bytes:
    """Helper to generate a PNG image with optional text."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    if text:
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- Test 1: Normal Native Title Text ---
@pytest.mark.anyio
async def test_pptx_native_title_text():
    """Verify normal native PowerPoint title is classified as digital text/heading, NOT handwriting."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Blood Link – Real-Time Blood Donation & Emergency Coordination System"

    buf = io.BytesIO()
    prs.save(buf)

    doc = await pipeline.process_document("title_test", buf.getvalue(), filename="title.pptx")
    assert doc.processing_status == "completed"
    assert len(doc.elements) >= 1

    title_elem = doc.elements[0]
    assert title_elem.type in ("heading", "text")
    assert title_elem.type != "handwriting"
    assert title_elem.confidence == 1.0
    assert "Blood Link" in (title_elem.text or "")
    assert title_elem.metadata.get("is_title") is True or title_elem.metadata.get("is_heading") is True
    assert title_elem.metadata.get("is_native_text") is True


# --- Test 2: Normal Native Paragraph Text ---
@pytest.mark.anyio
async def test_pptx_native_paragraph_text():
    """Verify native paragraph with CamelCase words (CodeAlchemy, S. Pranathi, dashes) is TEXT, NOT handwriting."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    tb = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3))
    tb.text_frame.text = (
        "Team Details\n"
        "Team name : CodeAlchemy\n"
        "Team leader name : S. Pranathi\n"
        "Problem Statement : Blood Link – Real-Time Blood Donation & Emergency Coordination System"
    )

    buf = io.BytesIO()
    prs.save(buf)

    doc = await pipeline.process_document("paragraph_test", buf.getvalue(), filename="paragraph.pptx")
    assert len(doc.elements) == 1
    elem = doc.elements[0]

    assert elem.type == "text"
    assert elem.type != "handwriting"
    assert elem.confidence == 1.0
    assert "CodeAlchemy" in elem.text
    classification = elem.metadata.get("content_classification", {})
    assert classification.get("content_type") == "text"
    assert elem.metadata.get("is_native_text") is True


# --- Test 3: Native Bullet-List Text ---
@pytest.mark.anyio
async def test_pptx_native_bullet_list_text():
    """Verify bullet-list text is classified appropriately (list/text), NOT handwriting."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    tb = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(3))
    tf = tb.text_frame
    tf.text = "Opportunities & Solution"
    p1 = tf.add_paragraph()
    p1.text = "• Google Maps Platform for navigation"
    p1.level = 1
    p2 = tf.add_paragraph()
    p2.text = "• Firebase / Firestore real-time synchronization"
    p2.level = 1

    buf = io.BytesIO()
    prs.save(buf)

    doc = await pipeline.process_document("bullet_test", buf.getvalue(), filename="bullet.pptx")
    assert len(doc.elements) >= 1
    elem = doc.elements[0]

    assert elem.type in ("list", "text")
    assert elem.type != "handwriting"
    assert elem.confidence == 1.0
    assert elem.metadata.get("is_native_text") is True


# --- Test 4: Native PowerPoint Table ---
@pytest.mark.anyio
async def test_pptx_native_table():
    """Verify native PowerPoint table extracts structured rows/cells without invoking OCR."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    table_shape = slide.shapes.add_table(4, 3, Inches(1), Inches(1), Inches(6), Inches(3))
    tbl = table_shape.table
    tbl.cell(0, 0).text = "Blood Group"
    tbl.cell(0, 1).text = "Units Available"
    tbl.cell(0, 2).text = "Status"

    tbl.cell(1, 0).text = "A+ (Positive)"
    tbl.cell(1, 1).text = "45"
    tbl.cell(1, 2).text = "Adequate"

    tbl.cell(2, 0).text = "O- (Universal)"
    tbl.cell(2, 1).text = "12"
    tbl.cell(2, 2).text = "Critical"

    tbl.cell(3, 0).text = "B+"
    tbl.cell(3, 1).text = "38"
    tbl.cell(3, 2).text = "Adequate"

    buf = io.BytesIO()
    prs.save(buf)

    doc = await pipeline.process_document("table_test", buf.getvalue(), filename="table.pptx")
    assert len(doc.elements) == 1
    elem = doc.elements[0]

    assert elem.type == "table"
    assert elem.confidence == 1.0
    assert elem.extraction_model == "python-pptx"
    assert elem.table_data is not None

    headers = elem.table_data.get("headers", [])
    rows = elem.table_data.get("rows", [])
    assert headers == ["Blood Group", "Units Available", "Status"]
    assert len(rows) == 3
    assert rows[0] == ["A+ (Positive)", "45", "Adequate"]
    assert rows[1] == ["O- (Universal)", "12", "Critical"]
    assert rows[2] == ["B+", "38", "Adequate"]

    assert elem.provenance.get("source") == "pptx"
    assert elem.provenance.get("slide") == 1
    assert elem.provenance.get("shape_id") is not None
    assert elem.provenance.get("reading_order") == 1
    assert len(elem.bbox) == 4

    summary = doc.metadata.get("pipeline_summary", {})
    assert summary.get("total_table_rows") == 3


# --- Test 5: Embedded Image ---
@pytest.mark.anyio
async def test_pptx_embedded_image():
    """Verify embedded image is preserved as clean image evidence with provenance without OCR/VLM."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    png_bytes = create_mock_image_bytes("DIAGRAM", width=120, height=80)
    slide.shapes.add_picture(io.BytesIO(png_bytes), Inches(1), Inches(1), Inches(3), Inches(2))

    buf = io.BytesIO()
    prs.save(buf)

    doc = await pipeline.process_document("image_test", buf.getvalue(), filename="image.pptx")
    assert len(doc.elements) == 1
    elem = doc.elements[0]

    assert elem.type == "image"
    assert elem.text is None
    assert elem.confidence == 1.0
    assert elem.slide == 1
    assert elem.metadata.get("is_image") is True
    assert elem.metadata.get("size_bytes", 0) > 0
    assert "image" in elem.metadata.get("content_type", "")
    assert elem.provenance.get("source") == "pptx"
    assert elem.provenance.get("shape_id") is not None
    assert elem.provenance.get("reading_order") == 1
    assert len(elem.bbox) == 4

    assert doc.metadata["pipeline_summary"]["vlm_escalations"] == 0


# --- Test 6: Embedded Image Containing Printed Text ---
@pytest.mark.anyio
async def test_pptx_embedded_image_printed_text_routing():
    """Verify embedded image routes to visual OCR only when routing requires it, and printed text avoids VLM."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    ocr_test_path = Path("sample_documents/ocr_test.png")
    assert ocr_test_path.exists(), "ocr_test.png not found"
    png_bytes = ocr_test_path.read_bytes()
    slide.shapes.add_picture(io.BytesIO(png_bytes), Inches(1), Inches(1), Inches(4), Inches(1.5))

    buf = io.BytesIO()
    prs.save(buf)

    # Parse and request visual routing on the image element
    res = await pptx_parser.parse(buf.getvalue(), filename="printed_img.pptx", document_id="doc_printed_img")
    elements = res.to_evidence_elements(document_id="doc_printed_img", file_hash="hash_p")
    assert len(elements) == 1

    # Request visual routing
    elements[0].metadata["route_visual"] = True

    routed = await pipeline.route_and_enrich_elements(elements, "doc_printed_img", "hash_p")
    assert len(routed) == 1
    img_elem = routed[0]

    # Handled via OCR; classified as printed/uncertain without VLM escalation
    assert img_elem.type in ("text", "image")
    assert img_elem.metadata.get("handwriting_classification") in ("printed", "uncertain")
    assert not img_elem.metadata.get("escalated_to_vision")
    assert img_elem.text is not None and "Sanctum" in img_elem.text


# --- Test 7: Embedded Image Containing Genuine Handwriting ---
@pytest.mark.anyio
async def test_pptx_embedded_image_handwriting_escalates_to_vlm(monkeypatch):
    """Verify embedded image containing genuine handwriting classifies as handwriting, escalates to VLM, and preserves reconciliation."""
    from unittest.mock import AsyncMock
    from app.models.vision_client import vision_client

    # Mock local VLM response
    vlm_mock = AsyncMock(return_value=("Emergency Dr Note: Urgent 2 units O negative blood needed", 0.95))
    monkeypatch.setattr(vision_client, "reread_cropped_region", vlm_mock)

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Use handwritten sample image if available or generate cursive-like mock
    hw_bytes = HANDWRITTEN_NOTE_PATH.read_bytes() if HANDWRITTEN_NOTE_PATH.exists() else create_mock_image_bytes("Signed by Dr notes", 300, 100)
    slide.shapes.add_picture(io.BytesIO(hw_bytes), Inches(1), Inches(1), Inches(4), Inches(2))

    buf = io.BytesIO()
    prs.save(buf)

    res = await pptx_parser.parse(buf.getvalue(), filename="hw_img.pptx", document_id="doc_hw_img")
    elements = res.to_evidence_elements(document_id="doc_hw_img", file_hash="hash_hw")
    assert len(elements) == 1

    # Flag for visual routing
    elements[0].metadata["route_visual"] = True

    routed = await pipeline.route_and_enrich_elements(elements, "doc_hw_img", "hash_hw")
    assert len(routed) == 1
    hw_elem = routed[0]

    assert hw_elem.type == "handwriting"
    assert hw_elem.metadata.get("handwriting_classification") == "handwritten"
    assert hw_elem.metadata.get("escalated_to_vision") is True
    assert hw_elem.metadata.get("vlm_candidate") is not None
    assert "ocr_candidate" in hw_elem.metadata


# --- Test 8: Mixed Text + Image Slide ---
@pytest.mark.anyio
async def test_pptx_mixed_slide_bloodlink():
    """Verify mixed text + image presentation (BloodLink) keeps native text as text and images as images with 0 VLM."""
    assert BLOODLINK_PATH.exists(), f"Missing regression file: {BLOODLINK_PATH}"
    pptx_bytes = BLOODLINK_PATH.read_bytes()

    doc = await pipeline.process_document("bloodlink_mixed", pptx_bytes, filename=BLOODLINK_PATH.name)

    assert doc.processing_status == "completed"
    assert doc.total_pages == 10
    assert doc.total_slides == 10
    assert len(doc.elements) == 30

    type_counts = {}
    for el in doc.elements:
        type_counts[el.type] = type_counts.get(el.type, 0) + 1

    assert type_counts.get("image") == 21
    assert type_counts.get("text", 0) + type_counts.get("list", 0) == 9
    assert type_counts.get("handwriting", 0) == 0, f"False handwriting detected: {type_counts}"

    summary = doc.metadata.get("pipeline_summary", {})
    assert summary.get("vlm_escalations") == 0
    assert summary.get("reconciliations") == 0


# --- Test 9: Deterministic Reading Order ---
@pytest.mark.anyio
async def test_pptx_reading_order_deterministic():
    """Verify shapes on a slide maintain deterministic reading order based on geometric position."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Add shapes in reverse spatial order
    tb_bottom = slide.shapes.add_textbox(Inches(1), Inches(5), Inches(4), Inches(1))
    tb_bottom.text_frame.text = "Bottom Box (Should be 3)"

    tb_middle = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(4), Inches(1))
    tb_middle.text_frame.text = "Middle Box (Should be 2)"

    tb_top = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    tb_top.text_frame.text = "Top Box (Should be 1)"

    buf = io.BytesIO()
    prs.save(buf)

    res = await pptx_parser.parse(buf.getvalue(), filename="order.pptx")
    slide1 = res.slides[0]

    assert len(slide1.items) == 3
    assert slide1.items[0].text == "Top Box (Should be 1)"
    assert slide1.items[0].reading_order == 1

    assert slide1.items[1].text == "Middle Box (Should be 2)"
    assert slide1.items[1].reading_order == 2

    assert slide1.items[2].text == "Bottom Box (Should be 3)"
    assert slide1.items[2].reading_order == 3


# --- Test 10: Complete Provenance Contract ---
@pytest.mark.anyio
async def test_pptx_provenance_contract():
    """Verify every PPTX evidence element retains document_id, slide, shape_id, shape_name, bbox, reading_order, source."""
    assert BLOODLINK_PATH.exists(), f"Missing regression file: {BLOODLINK_PATH}"
    pptx_bytes = BLOODLINK_PATH.read_bytes()

    doc = await pipeline.process_document("bloodlink_prov", pptx_bytes, filename=BLOODLINK_PATH.name)

    for el in doc.elements:
        assert el.document_id == "bloodlink_prov"
        assert el.slide is not None and 1 <= el.slide <= 10
        assert el.page == el.slide
        assert el.reading_order is not None and el.reading_order >= 1
        assert len(el.bbox) == 4
        assert el.extraction_model == "python-pptx"
        assert el.file_hash == doc.file_hash

        prov = el.provenance if isinstance(el.provenance, dict) else {}
        assert prov.get("source") == "pptx"
        assert prov.get("slide") == el.slide
        assert prov.get("shape_id") is not None
        assert prov.get("shape_name") is not None


# --- Test 11: Zero Unnecessary VLM Calls on Clean PPTX ---
@pytest.mark.anyio
async def test_pptx_no_unnecessary_vlm():
    """Verify clean native PowerPoint deck results in exactly zero VLM escalations."""
    assert BLOODLINK_PATH.exists(), f"Missing regression file: {BLOODLINK_PATH}"
    pptx_bytes = BLOODLINK_PATH.read_bytes()

    doc = await pipeline.process_document("bloodlink_clean", pptx_bytes, filename=BLOODLINK_PATH.name)
    summary = doc.metadata.get("pipeline_summary", {})

    assert summary.get("vlm_escalations") == 0
    assert summary.get("reconciliations") == 0
    assert summary.get("conflicts_requiring_review") == 0


# --- Test 12: Malformed / Corrupt PPTX Fails Safely ---
@pytest.mark.anyio
async def test_pptx_corrupt_fails_safely():
    """Verify malformed/corrupt PPTX returns controlled error without crashing service."""
    corrupt_bytes = b"PK\x03\x04CORRUPTED_NON_PPTX_PAYLOAD"

    # Parser level check
    res = await pptx_parser.parse(corrupt_bytes, filename="corrupt.pptx")
    assert isinstance(res, PptxParseResult)
    assert res.metadata.get("is_corrupt") is True
    assert len(res.slides) == 0

    # Pipeline level check
    doc = await pipeline.process_document("corrupt_test", corrupt_bytes, filename="corrupt.pptx")
    assert doc is not None
    assert len(doc.elements) == 0


# --- Test 13: Canonical DocumentEvidence Schema Verification ---
@pytest.mark.anyio
async def test_pptx_canonical_document_evidence():
    """Verify DocumentEvidence canonical properties for PPTX files."""
    assert BLOODLINK_PATH.exists(), f"Missing regression file: {BLOODLINK_PATH}"
    pptx_bytes = BLOODLINK_PATH.read_bytes()

    doc = await pipeline.process_document("bloodlink_canonical", pptx_bytes, filename=BLOODLINK_PATH.name)

    assert doc.document_id == "bloodlink_canonical"
    assert doc.filename == "BLOODLINK _ Team-CodeAlchemy.pptx"
    assert doc.file_type == "pptx"
    assert doc.mime_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert doc.total_slides == 10
    assert doc.total_pages == 10
    assert doc.parser_used == "python-pptx"
    assert doc.processing_status == "completed"
    assert doc.overall_confidence == 1.0
    assert doc.created_at is not None
    assert doc.completed_at is not None
    assert doc.processing_time_ms is not None and doc.processing_time_ms > 0
