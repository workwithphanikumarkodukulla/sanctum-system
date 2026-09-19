"""Regression tests for PDF table extraction, multi-page continuation, and digital/scanned routing."""
from __future__ import annotations

import io
from pathlib import Path
import fitz
import pytest
from PIL import Image, ImageDraw

from app.ingestion.detector import detector
from app.parsers.pdf import pdf_parser
from app.processing.pdf import pdf_processor
from app.processing.pipeline import pipeline


CSR_PDF_PATH = Path("sample_documents/CSR_Expenditure_Incurred_by_MRPL_during_2025-26.pdf")


def create_mock_scanned_pdf(text: str) -> bytes:
    """Create a 1-page image-only scanned PDF."""
    img = Image.new("RGB", (500, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=500, height=200)
    page.insert_image(page.rect, stream=buf.getvalue())
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# --- Test A: Digital PDF Detection ---
@pytest.mark.anyio
async def test_pdf_digital_detection():
    """Verify digital PDF is accurately detected as digital with valid MIME type."""
    assert CSR_PDF_PATH.exists(), f"Missing regression file: {CSR_PDF_PATH}"
    pdf_bytes = CSR_PDF_PATH.read_bytes()
    detection = detector.detect(pdf_bytes, filename=CSR_PDF_PATH.name)

    assert detection.is_supported is True
    assert detection.file_type.value == "pdf"
    assert detection.mime_type == "application/pdf"

    doc = pdf_processor.load_pdf(pdf_bytes)
    inspection = pdf_processor.inspect_page(doc[0], page_num=1)
    assert inspection["is_digital"] is True
    doc.close()


# --- Tests B, C, D, E, F, G, H, I: CSR 22-Page Table Ingestion ---
@pytest.mark.anyio
async def test_pdf_csr_22page_table_extraction():
    """Verify end-to-end processing of the 22-page CSR expenditure report."""
    assert CSR_PDF_PATH.exists(), f"Missing regression file: {CSR_PDF_PATH}"
    pdf_bytes = CSR_PDF_PATH.read_bytes()

    # Process through complete evidence pipeline
    evidence = await pipeline.process_document(
        document_id="csr_expenditure_test",
        file_bytes=pdf_bytes,
        filename=CSR_PDF_PATH.name,
    )

    # Test B: 22-page PDF processes successfully
    assert evidence.processing_status == "completed"
    assert evidence.total_pages == 22

    # Test C: Every page is processed
    pages_with_elements = {el.page for el in evidence.elements}
    assert len(pages_with_elements) == 22
    for p in range(1, 23):
        assert p in pages_with_elements, f"Page {p} missing from extracted elements"

    # Test D: Table content is detected
    table_elements = [el for el in evidence.elements if el.type == "table"]
    assert len(table_elements) == 22, f"Expected 22 table elements, got {len(table_elements)}"

    # Test E: Multiple rows can be reconstructed from a page
    for el in table_elements:
        assert el.table_data is not None, f"Page {el.page} table element missing table_data"
        rows = el.table_data.get("rows", [])
        assert len(rows) >= 5, f"Page {el.page} only has {len(rows)} rows, expected >= 5 (substantially > 1-2)"

    # Test F: Multi-page table continuation works
    all_table_rows: list[list[str]] = []
    for el in sorted(table_elements, key=lambda x: x.page):
        all_table_rows.extend(el.table_data["rows"])

    # Total reconstructed rows across all 22 pages
    total_reconstructed = len(all_table_rows)
    assert total_reconstructed >= 284, f"Expected >= 284 rows, got {total_reconstructed}"

    # Verify continued table metadata exists
    continued_tables = evidence.metadata.get("continued_tables") or []
    assert len(continued_tables) >= 1
    assert continued_tables[0]["total_pages"] == 22
    assert continued_tables[0]["total_rows"] == total_reconstructed

    # Test G: Repeated headers are not treated as data rows
    # Extract project rows starting with numeric serial numbers
    project_rows = [r for r in all_table_rows if r and r[0] and str(r[0]).strip().isdigit()]
    assert len(project_rows) == 284, f"Expected exactly 284 project rows, got {len(project_rows)}"

    # Verify no repeated headers exist in data rows
    for r in all_table_rows:
        row_str = " ".join(r).lower()
        assert "details of csr amount" not in row_str, f"Banner row leaked into data rows: {r}"
        if r[0] != "Sl No":
            assert "item from the list" not in row_str, f"Header row leaked into data rows: {r}"

    # Verify representative row numbers: early (1), middle (141), late (284)
    project_ids = [int(str(r[0]).strip()) for r in project_rows]
    assert 1 in project_ids, "Project Sl No 1 missing"
    assert 141 in project_ids, "Project Sl No 141 missing"
    assert 284 in project_ids, "Project Sl No 284 missing"
    assert project_ids == list(range(1, 285)), "Project Sl Nos are not strictly consecutive from 1 to 284"

    # Test H: Numeric columns remain intact
    # Check Project 1 numeric values: Allocated=18.44, Spent=16.70, Unspent=1.73
    p1 = project_rows[0]
    assert p1[0] == "1"
    assert "Govt" in p1[1] or "school" in p1[1].lower()
    assert "18.44" in p1[6], f"Allocated amount expected 18.44, got {p1[6]}"
    assert "16.70" in p1[7], f"Spent amount expected 16.70, got {p1[7]}"

    # Verify the final total row is preserved on page 22
    last_row = all_table_rows[-1]
    assert "Total" in last_row[1], f"Expected Total row at end, got {last_row}"
    assert "4867.01" in last_row[7], f"Expected 4867.01 in spent column of Total row, got {last_row}"

    # Test I: Page provenance is preserved
    for el in table_elements:
        assert el.provenance is not None
        prov = el.provenance if isinstance(el.provenance, dict) else {}
        assert prov.get("source") == "pdf"
        assert prov.get("page") == el.page
        assert prov.get("extraction_method") == "PyMuPDF-Direct"
        assert el.confidence >= 0.95
        assert len(el.bbox) == 4


# --- Dedicated Test: Continuous 1 through 284 Project Row Numbers ---
@pytest.mark.anyio
async def test_csr_project_row_numbers_strictly_continuous_1_to_284():
    """Verify that all project rows 1 through 284 are extracted with zero missing numbers."""
    assert CSR_PDF_PATH.exists(), f"Missing regression file: {CSR_PDF_PATH}"
    pdf_bytes = CSR_PDF_PATH.read_bytes()

    evidence = await pipeline.process_document(
        document_id="csr_continuity_test",
        file_bytes=pdf_bytes,
        filename=CSR_PDF_PATH.name,
    )

    table_elements = [el for el in evidence.elements if el.type == "table"]
    all_table_rows: list[list[str]] = []
    for el in sorted(table_elements, key=lambda x: x.page):
        all_table_rows.extend(el.table_data.get("rows", []))

    # Collect project numbers from column 0
    project_numbers: list[int] = []
    for r in all_table_rows:
        if r and r[0] and str(r[0]).strip().isdigit():
            project_numbers.append(int(str(r[0]).strip()))

    expected_numbers = set(range(1, 285))
    actual_numbers = set(project_numbers)
    missing_numbers = expected_numbers - actual_numbers
    unexpected_numbers = actual_numbers - expected_numbers

    # Exact count of project numbers must be 284
    assert len(project_numbers) == 284, f"Expected 284 project numbers, got {len(project_numbers)}"

    # Confirm zero missing numbers from 1 through 284
    assert not missing_numbers, f"Missing project numbers: {sorted(missing_numbers)}"

    # Confirm no numbers outside 1..284
    assert not unexpected_numbers, f"Unexpected project numbers: {sorted(unexpected_numbers)}"

    # Confirm zero duplicate project numbers
    duplicates = [n for n in set(project_numbers) if project_numbers.count(n) > 1]
    assert not duplicates, f"Duplicate project numbers found: {duplicates}"

    # Confirm strict sequence 1 to 284
    assert project_numbers == list(range(1, 285)), "Project numbers are not strictly consecutive 1 to 284"
    assert min(project_numbers) == 1
    assert max(project_numbers) == 284


# --- Test J: Scanned/Image PDF Uses Existing OCR Path ---
@pytest.mark.anyio
async def test_pdf_scanned_image_triggers_ocr_path():
    """Verify image-only / scanned PDF pages trigger rendering and OCR extraction."""
    scanned_bytes = create_mock_scanned_pdf("SCANNED INVOICE #9921")

    res = await pdf_parser.parse(
        file_bytes=scanned_bytes,
        filename="scanned_doc.pdf",
        document_id="doc_scanned_test",
        file_hash="hash_scanned",
    )

    assert res.total_pages == 1
    assert res.metadata["scanned_pages"] == 1
    assert res.metadata["digital_pages"] == 0

    page1 = res.pages[0]
    assert page1.is_digital is False
    assert "OCR" in page1.extraction_method
    assert len(page1.elements) >= 1
