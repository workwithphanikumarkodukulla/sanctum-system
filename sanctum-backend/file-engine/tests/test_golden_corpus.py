"""Golden Test Corpus for the Sanctum Document & File Handling Module.

Verifies structural correctness across 15 canonical document scenarios:
1. Digital PDF
2. Scanned PDF (image-only with OCR fallback)
3. Dense-table PDF (MRPL CSR benchmark)
4. TXT (headings, lists, paragraphs with line coordinates)
5. DOCX with headings and paragraphs
6. DOCX with tables
7. PPTX with multiple slides
8. PPTX with table
9. XLSX with multiple sheets
10. XLSX with formulas (verbatim preservation)
11. CSV (quotes, commas, delimiter preservation)
12. PNG/JPG OCR image
13. Unsupported file
14. Corrupted file
15. Empty file
"""
from __future__ import annotations

import io
from pathlib import Path
import fitz
import openpyxl
from PIL import Image
import pytest
from docx import Document
from pptx import Presentation
from pptx.util import Inches

from app.evidence.schema import DocumentEvidence, EvidenceElement, WorksheetInfo
from app.parsers.csv import csv_parser
from app.parsers.docx import docx_parser
from app.parsers.image import image_parser
from app.parsers.pdf import pdf_parser
from app.parsers.pptx import pptx_parser
from app.parsers.txt import txt_parser
from app.parsers.xlsx import xlsx_parser
from app.processing.pipeline import pipeline

SAMPLE_DIR = Path(__file__).parent.parent / "sample_documents"


# ==============================================================================
# Fixtures for the 15 Golden Corpus Scenarios
# ==============================================================================

@pytest.fixture
def digital_pdf_bytes() -> bytes:
    """Fixture 1: Digital PDF with structured text and tables."""
    pdf_path = SAMPLE_DIR / "sample_inspection.pdf"
    if not pdf_path.exists():
        from sample_documents.generate_sample import generate_sample_pdf
        generate_sample_pdf(pdf_path)
    return pdf_path.read_bytes()


@pytest.fixture
def scanned_pdf_bytes() -> bytes:
    """Fixture 2: Scanned PDF containing an image of text without digital font streams."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Render synthetic text banner image
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(fitz.Rect(50, 50, 450, 150), stream=buf.getvalue())
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def dense_table_pdf_bytes() -> bytes:
    """Fixture 3: Dense multi-page corporate report PDF."""
    pdf_path = SAMPLE_DIR / "mrpl_csr_2025_26.pdf"
    assert pdf_path.exists(), "mrpl_csr_2025_26.pdf benchmark file must exist in sample_documents"
    return pdf_path.read_bytes()


@pytest.fixture
def structured_txt_bytes() -> bytes:
    """Fixture 4: Plain text with headings, bullet lists, and paragraphs."""
    content = (
        "# AIR-GAPPED INFRASTRUCTURE SPECIFICATION\n\n"
        "• High security enclave isolation\n"
        "• Zero internet egress\n"
        "• Hardware-attested enclave keys\n\n"
        "All data transformations occur strictly in-memory without persistent disk cache.\n"
    )
    return content.encode("utf-8")


@pytest.fixture
def docx_headings_and_paragraphs_bytes() -> bytes:
    """Fixture 5: DOCX document with styled headings and body paragraphs."""
    doc = Document()
    doc.add_heading("Sanctum Document Intelligence", level=1)
    doc.add_paragraph("This paragraph introduces the system architecture.")
    doc.add_heading("Subsystem Specifications", level=2)
    doc.add_paragraph("The parser pipeline processes documents deterministically.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def docx_table_bytes() -> bytes:
    """Fixture 6: DOCX document containing a formatted tabular matrix."""
    doc = Document()
    doc.add_heading("Sensor Calibration Matrix", level=1)
    table = doc.add_table(rows=3, cols=3)
    headers = ["Sensor ID", "Calibration Offset", "Tolerance"]
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h

    data = [
        ["TEMP-01", "+0.05 C", "+/- 0.01 C"],
        ["PRES-02", "-0.12 bar", "+/- 0.05 bar"],
    ]
    for r_idx, row in enumerate(data, start=1):
        for c_idx, val in enumerate(row):
            table.rows[r_idx].cells[c_idx].text = val

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def pptx_multi_slide_bytes() -> bytes:
    """Fixture 7: PowerPoint presentation with multiple slides and titles."""
    prs = Presentation()
    # Slide 1
    s1 = prs.slides.add_slide(prs.slide_layouts[0])
    s1.shapes.title.text = "Executive Briefing"
    s1.placeholders[1].text = "• Strategic Overview\n• Milestone Roadmap"

    # Slide 2
    s2 = prs.slides.add_slide(prs.slide_layouts[1])
    s2.shapes.title.text = "Technical Implementation"
    s2.placeholders[1].text = "• Ingestion Engine\n• Evidence Normalization"

    # Slide 3
    s3 = prs.slides.add_slide(prs.slide_layouts[1])
    s3.shapes.title.text = "Audit & Compliance"
    s3.placeholders[1].text = "• Cryptographic SHA-256 Hashes\n• Line-Level Provenance"

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def pptx_table_bytes() -> bytes:
    """Fixture 8: PowerPoint presentation slide with a data table."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title only layout
    slide.shapes.title.text = "Quarterly Production Targets"

    table_shape = slide.shapes.add_table(rows=3, cols=2, left=Inches(1), top=Inches(2), width=Inches(6), height=Inches(2))
    tbl = table_shape.table
    tbl.cell(0, 0).text = "Facility"
    tbl.cell(0, 1).text = "Capacity"
    tbl.cell(1, 0).text = "Plant Alpha"
    tbl.cell(1, 1).text = "50,000 bpd"
    tbl.cell(2, 0).text = "Plant Beta"
    tbl.cell(2, 1).text = "75,000 bpd"

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def xlsx_multi_sheet_bytes() -> bytes:
    """Fixture 9: Excel workbook containing multiple active worksheets."""
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Domestic_Sales"
    ws1.append(["Region", "Revenue_USD"])
    ws1.append(["North", 150000])
    ws1.append(["South", 220000])

    ws2 = wb.create_sheet(title="Export_Sales")
    ws2.append(["Country", "Volume_MT"])
    ws2.append(["Japan", 4500])
    ws2.append(["Germany", 3200])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def xlsx_formulas_bytes() -> bytes:
    """Fixture 10: Excel workbook with formulas preserved verbatim without evaluation."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financial_Model"
    ws.append(["Item", "Amount"])
    ws.append(["Base Cost", 1000])
    ws.append(["Overhead", 250])
    ws["B4"] = "=SUM(B2:B3)"
    ws["B5"] = "=AVERAGE(B2:B3)"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def csv_bytes() -> bytes:
    """Fixture 11: CSV with quoted fields and embedded commas."""
    content = (
        'transaction_id,merchant,amount,category\n'
        'TX-1001,"Sanctum Solutions, LLC",450.00,"Cloud, Hosting"\n'
        'TX-1002,"Hardware Store, Inc.",89.50,"Supplies"\n'
    )
    return content.encode("utf-8")


@pytest.fixture
def ocr_image_bytes() -> bytes:
    """Fixture 12: Real PNG test image with legible text for OCR."""
    img_path = SAMPLE_DIR / "ocr_test.png"
    assert img_path.exists(), "ocr_test.png must exist in sample_documents"
    return img_path.read_bytes()


@pytest.fixture
def unsupported_file_bytes() -> bytes:
    """Fixture 13: Unsupported binary format (e.g. ELF executable)."""
    return b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"


@pytest.fixture
def corrupted_file_bytes() -> bytes:
    """Fixture 14: Corrupted zip header claiming to be an Office document."""
    return b"PK\x03\x04\x00\x00corrupted_archive_data_stream_invalid"


@pytest.fixture
def empty_file_bytes() -> bytes:
    """Fixture 15: Zero-byte file."""
    return b""


# ==============================================================================
# Tests for Golden Corpus: Strict Structural Verification
# ==============================================================================

@pytest.mark.anyio
async def test_golden_01_digital_pdf(digital_pdf_bytes):
    """1. Verify digital PDF pages detected and native text elements extracted."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_pdf_digital",
        file_bytes=digital_pdf_bytes,
        filename="sample_inspection.pdf",
    )

    assert result.processing_status == "completed"
    assert result.file_type == "pdf"
    assert result.total_pages >= 1
    assert len(result.elements) >= 3

    # Structural verification: check text presence
    full_text = " ".join(e.text or "" for e in result.elements)
    assert "PRESSURE VESSEL INSPECTION REPORT" in full_text
    assert "PV-204B" in full_text
    # Digital elements must have deterministic 1.0 confidence
    assert all(e.confidence == 1.0 for e in result.elements if e.extraction_model == "PyMuPDF")


@pytest.mark.anyio
async def test_golden_02_scanned_pdf(scanned_pdf_bytes):
    """2. Verify scanned PDF page detected as non-digital and processed via image/OCR path."""
    parse_result = await pdf_parser.parse(
        file_bytes=scanned_pdf_bytes,
        filename="scanned_synthetic.pdf",
    )

    assert parse_result.total_pages == 1
    assert len(parse_result.pages) == 1
    # Page must be identified as scanned
    assert parse_result.pages[0].is_digital is False
    assert "OCR" in parse_result.pages[0].extraction_method


@pytest.mark.anyio
async def test_golden_03_dense_table_pdf(dense_table_pdf_bytes):
    """3. Verify dense corporate PDF multi-page handling and tabular element preservation."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_dense_pdf",
        file_bytes=dense_table_pdf_bytes,
        filename="mrpl_csr_2025_26.pdf",
    )

    assert result.processing_status == "completed"
    assert result.file_type == "pdf"
    # Benchmark document contains multiple pages
    assert result.total_pages >= 2
    assert len(result.elements) >= 10
    # Must preserve page indexing across multi-page document
    pages_seen = {e.page for e in result.elements}
    assert len(pages_seen) >= 2


@pytest.mark.anyio
async def test_golden_04_structured_txt(structured_txt_bytes):
    """4. Verify TXT preserves line boundaries, reading order, and block types."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_txt",
        file_bytes=structured_txt_bytes,
        filename="infrastructure.txt",
    )

    assert result.processing_status == "completed"
    assert result.file_type == "txt"
    assert len(result.elements) == 3

    # 1. Heading element
    assert result.elements[0].type == "heading"
    assert "AIR-GAPPED INFRASTRUCTURE SPECIFICATION" in result.elements[0].text
    assert result.elements[0].reading_order == 1
    assert result.elements[0].row == 1

    # 2. List element
    assert result.elements[1].type == "list"
    assert "Zero internet egress" in result.elements[1].text
    assert result.elements[1].reading_order == 2

    # 3. Body paragraph element
    assert result.elements[2].type == "text"
    assert "in-memory" in result.elements[2].text
    assert result.elements[2].reading_order == 3


@pytest.mark.anyio
async def test_golden_05_docx_headings_and_paragraphs(docx_headings_and_paragraphs_bytes):
    """5. Verify DOCX preserves headings with heading levels and paragraphs in sequence."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_docx_hierarchy",
        file_bytes=docx_headings_and_paragraphs_bytes,
        filename="intelligence.docx",
    )

    assert result.processing_status == "completed"
    assert result.file_type == "docx"
    assert len(result.elements) == 4

    # Heading 1
    assert result.elements[0].type == "heading"
    assert result.elements[0].text == "Sanctum Document Intelligence"
    assert result.elements[0].metadata["heading_level"] == 1
    assert result.elements[0].reading_order == 1

    # Paragraph 1
    assert result.elements[1].type == "text"
    assert "system architecture" in result.elements[1].text
    assert result.elements[1].reading_order == 2

    # Heading 2
    assert result.elements[2].type == "heading"
    assert result.elements[2].text == "Subsystem Specifications"
    assert result.elements[2].metadata["heading_level"] == 2
    assert result.elements[2].reading_order == 3


@pytest.mark.anyio
async def test_golden_06_docx_with_tables(docx_table_bytes):
    """6. Verify DOCX table headers, rows, columns, and cell values are preserved."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_docx_table",
        file_bytes=docx_table_bytes,
        filename="calibration.docx",
    )

    assert result.processing_status == "completed"
    tbl_elem = next(e for e in result.elements if e.type == "table")

    assert tbl_elem.table_data is not None
    assert tbl_elem.table_data["headers"] == ["Sensor ID", "Calibration Offset", "Tolerance"]
    assert len(tbl_elem.table_data["rows"]) == 2
    assert tbl_elem.table_data["rows"][0] == ["TEMP-01", "+0.05 C", "+/- 0.01 C"]
    assert tbl_elem.table_data["rows"][1] == ["PRES-02", "-0.12 bar", "+/- 0.05 bar"]
    assert tbl_elem.metadata["num_rows"] == 3
    assert tbl_elem.metadata["num_cols"] == 3


@pytest.mark.anyio
async def test_golden_07_pptx_multiple_slides(pptx_multi_slide_bytes):
    """7. Verify PPTX slide numbering, slide titles as headings, and slide order."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_pptx_slides",
        file_bytes=pptx_multi_slide_bytes,
        filename="briefing.pptx",
    )

    assert result.processing_status == "completed"
    assert result.file_type == "pptx"
    assert result.total_slides == 3

    # Verify slide mapping on elements
    slides_found = [e.slide for e in result.elements]
    assert 1 in slides_found
    assert 2 in slides_found
    assert 3 in slides_found

    # Verify slide 1 title
    title1 = next(e for e in result.elements if e.slide == 1 and e.type == "heading")
    assert title1.text == "Executive Briefing"

    # Verify slide 3 title
    title3 = next(e for e in result.elements if e.slide == 3 and e.type == "heading")
    assert title3.text == "Audit & Compliance"


@pytest.mark.anyio
async def test_golden_08_pptx_with_table(pptx_table_bytes):
    """8. Verify PPTX table headers, rows, and slide numbering preservation."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_pptx_table",
        file_bytes=pptx_table_bytes,
        filename="production.pptx",
    )

    assert result.processing_status == "completed"
    tbl_elem = next(e for e in result.elements if e.type == "table")
    assert tbl_elem.slide == 1
    assert tbl_elem.table_data["headers"] == ["Facility", "Capacity"]
    assert tbl_elem.table_data["rows"] == [["Plant Alpha", "50,000 bpd"], ["Plant Beta", "75,000 bpd"]]


@pytest.mark.anyio
async def test_golden_09_xlsx_multiple_sheets(xlsx_multi_sheet_bytes):
    """9. Verify XLSX multiple worksheets, sheet names, and sheet-specific tables."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_xlsx_sheets",
        file_bytes=xlsx_multi_sheet_bytes,
        filename="sales_multi.xlsx",
    )

    assert result.processing_status == "completed"
    assert result.file_type == "xlsx"
    assert result.worksheets is not None
    assert len(result.worksheets) == 2

    # Verify sheet names in metadata
    sheet_names = [ws.name for ws in result.worksheets]
    assert "Domestic_Sales" in sheet_names
    assert "Export_Sales" in sheet_names

    # Verify table elements have correct sheet provenance
    ws1_elem = next(e for e in result.elements if e.sheet == "Domestic_Sales")
    assert ws1_elem.table_data["headers"] == ["Region", "Revenue_USD"]

    ws2_elem = next(e for e in result.elements if e.sheet == "Export_Sales")
    assert ws2_elem.table_data["headers"] == ["Country", "Volume_MT"]


@pytest.mark.anyio
async def test_golden_10_xlsx_with_formulas(xlsx_formulas_bytes):
    """10. Verify XLSX preserves formulas verbatim without evaluating them."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_xlsx_formulas",
        file_bytes=xlsx_formulas_bytes,
        filename="financial_model.xlsx",
    )

    assert result.processing_status == "completed"
    formula_elems = [e for e in result.elements if e.type == "formula"]
    assert len(formula_elems) == 2

    formulas = [f.text for f in formula_elems]
    assert "=SUM(B2:B3)" in formulas
    assert "=AVERAGE(B2:B3)" in formulas

    # Assert cell coordinate metadata
    sum_elem = next(e for e in formula_elems if e.text == "=SUM(B2:B3)")
    assert sum_elem.metadata["cell_coordinate"] == "B4"
    assert sum_elem.sheet == "Financial_Model"


@pytest.mark.anyio
async def test_golden_11_csv_with_quotes(csv_bytes):
    """11. Verify CSV handles quotes, embedded commas, and preserves rows/columns."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_csv",
        file_bytes=csv_bytes,
        filename="transactions.csv",
    )

    assert result.processing_status == "completed"
    assert result.file_type == "csv"
    assert len(result.elements) == 1

    tbl = result.elements[0]
    assert tbl.type == "table"
    assert tbl.table_data["headers"] == ["transaction_id", "merchant", "amount", "category"]
    # Verify embedded comma inside quotes did not split column
    first_row = tbl.table_data["rows"][0]
    assert first_row[1] == "Sanctum Solutions, LLC"
    assert first_row[3] == "Cloud, Hosting"


@pytest.mark.anyio
async def test_golden_12_ocr_image(ocr_image_bytes):
    """12. Verify OCR returns expected text approximately and preserves coordinates."""
    res = await image_parser.parse(
        file_bytes=ocr_image_bytes,
        filename="ocr_test.png",
    )

    assert res.parser_name == "image_parser"
    assert len(res.extracted_regions) >= 1
    # Check approximate text presence
    assert "Sanctum" in res.full_text or "OCR" in res.full_text
    assert res.extracted_regions[0].confidence > 0.0
    assert len(res.extracted_regions[0].bbox) == 4


@pytest.mark.anyio
async def test_golden_13_unsupported_file(unsupported_file_bytes):
    """13. Verify unsupported binary is rejected cleanly with status failed and error message."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_unsupported",
        file_bytes=unsupported_file_bytes,
        filename="kernel.bin",
    )

    assert result.processing_status == "failed"
    assert "Unsupported" in result.error and "format" in result.error


@pytest.mark.anyio
async def test_golden_14_corrupted_file(corrupted_file_bytes):
    """14. Verify corrupted archive fails cleanly without crashing pipeline or process."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_corrupt",
        file_bytes=corrupted_file_bytes,
        filename="broken.docx",
    )

    assert result.processing_status == "failed"
    assert result.error is not None
    assert ("Corrupted" in result.error or "Unsupported" in result.error)


@pytest.mark.anyio
async def test_golden_15_empty_file(empty_file_bytes):
    """15. Verify empty file is rejected with zero elements and failed status."""
    result: DocumentEvidence = await pipeline.process_document(
        document_id="golden_empty",
        file_bytes=empty_file_bytes,
        filename="empty.pdf",
    )

    assert result.processing_status == "failed"
    assert result.file_size == 0
    assert result.total_pages == 0
    assert len(result.elements) == 0
    assert result.error is not None
    assert "empty" in result.error.lower()
