"""Comprehensive test suite for file detector, router, native parsers, and API integration."""
from __future__ import annotations

import io
import time
from pathlib import Path
import openpyxl
import pytest
from docx import Document
from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.util import Inches

from app.evidence.schema import DocumentEvidence, EvidenceElement
from app.ingestion.detector import detector
from app.ingestion.models import FileType
from app.ingestion.router import router as file_router
from app.main import app
from app.parsers.csv import csv_parser
from app.parsers.docx import docx_parser
from app.parsers.pdf import pdf_parser
from app.parsers.pptx import pptx_parser
from app.parsers.txt import txt_parser
from app.parsers.xlsx import xlsx_parser
from app.processing.pipeline import pipeline

client = TestClient(app)


# --- Fixtures for In-Memory Test Documents ---

@pytest.fixture
def sample_docx_bytes() -> bytes:
    doc = Document()
    doc.add_heading("Equipment Inspection Report", level=0)
    doc.add_paragraph("This is an introductory paragraph regarding high-pressure equipment.")
    doc.add_heading("Pressure Test Data", level=1)
    table = doc.add_table(rows=3, cols=3)
    data = [
        ["Equipment ID", "Pressure (kPa)", "Status"],
        ["P-101", "500", "PASS"],
        ["P-102", "750", "REVIEW"],
    ]
    for r_idx, row in enumerate(data):
        for c_idx, val in enumerate(row):
            table.cell(r_idx, c_idx).text = val
    doc.add_paragraph("Conclusion: All equipment operating within permissible margins.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_pptx_bytes() -> bytes:
    prs = Presentation()
    # Slide 1: Title slide
    title_slide_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_slide_layout)
    slide1.shapes.title.text = "Q3 Plant Inspection Review"
    slide1.placeholders[1].text = "Sanctum Engineering Team"

    # Slide 2: Table and bullet slide
    blank_layout = prs.slide_layouts[6]
    slide2 = prs.slides.add_slide(blank_layout)
    txBox = slide2.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
    tf = txBox.text_frame
    tf.text = "Key Findings Overview"

    table_shape = slide2.shapes.add_table(2, 2, Inches(1), Inches(2.5), Inches(4), Inches(2))
    table = table_shape.table
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Max Flow Rate"
    table.cell(1, 1).text = "120 L/s"

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    # Sheet 1: Summary
    ws1 = wb.active
    ws1.title = "Summary"
    ws1.append(["Equipment", "Pressure_kPa", "Target_kPa"])
    ws1.append(["Reactor A", 450, 500])
    ws1.append(["Boiler B", 550, 500])
    ws1.append(["Average", "=AVERAGE(B2:B3)", 500])
    ws1.merge_cells("A5:C5")
    ws1["A5"] = "End of Summary"

    # Sheet 2: Specifications
    ws2 = wb.create_sheet(title="Specifications")
    ws2.append(["Param", "Tolerance"])
    ws2.append(["Temp", "+/- 5 C"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def sample_csv_bytes() -> bytes:
    content = "Asset_ID,Location,Status,Calibration_Date\nAST-001,Zone 4,Active,2026-01-15\nAST-002,Zone 9,Maintenance,2026-02-20\n"
    return content.encode("utf-8")


@pytest.fixture
def sample_txt_bytes() -> bytes:
    content = (
        "Operating Procedures Manual\nSection 4.1 Valve Inspection\n\n"
        "Ensure the emergency shutoff valve is seated securely before testing.\n"
        "Check hydraulic line pressure.\n\n"
        "Document any fluid leakage exceeding 2 drops per minute.\n"
    )
    return content.encode("utf-8")


# --- Unit Tests: File Detection & Routing ---

def test_file_detector_magic_bytes(sample_docx_bytes, sample_pptx_bytes, sample_xlsx_bytes, sample_csv_bytes, sample_txt_bytes):
    # DOCX
    info_docx = detector.detect(sample_docx_bytes, "report.docx")
    assert info_docx.file_type == FileType.DOCX
    assert info_docx.is_supported is True

    # PPTX
    info_pptx = detector.detect(sample_pptx_bytes, "presentation.pptx")
    assert info_pptx.file_type == FileType.PPTX
    assert info_pptx.is_supported is True

    # XLSX
    info_xlsx = detector.detect(sample_xlsx_bytes, "metrics.xlsx")
    assert info_xlsx.file_type == FileType.XLSX
    assert info_xlsx.is_supported is True

    # CSV
    info_csv = detector.detect(sample_csv_bytes, "data.csv")
    assert info_csv.file_type == FileType.CSV
    assert info_csv.is_supported is True

    # TXT
    info_txt = detector.detect(sample_txt_bytes, "notes.txt")
    assert info_txt.file_type == FileType.TXT
    assert info_txt.is_supported is True

    # Empty file
    info_empty = detector.detect(b"", "empty.bin")
    assert info_empty.file_type == FileType.UNKNOWN
    assert info_empty.is_supported is False

    # Corrupted / unsupported binary
    info_corrupt = detector.detect(b"\x00\x01\x02\x03\x04\x05\x06\x07", "unknown.bin")
    assert info_corrupt.file_type == FileType.UNKNOWN
    assert info_corrupt.is_supported is False


def test_file_router():
    assert file_router.get_parser(FileType.DOCX) == docx_parser
    assert file_router.get_parser(FileType.PPTX) == pptx_parser
    assert file_router.get_parser(FileType.XLSX) == xlsx_parser
    assert file_router.get_parser(FileType.CSV) == csv_parser
    assert file_router.get_parser(FileType.TXT) == txt_parser
    assert file_router.get_parser(FileType.PDF) == pdf_parser

    with pytest.raises(ValueError):
        file_router.get_parser(FileType.UNKNOWN)


# --- Unit Tests: Native Parsers ---

@pytest.mark.anyio
async def test_docx_parser(sample_docx_bytes):
    res = await docx_parser.parse(
        sample_docx_bytes,
        filename="test.docx",
        document_id="doc_docx_1",
        file_hash="hash_docx",
    )
    assert res.total_pages == 1
    assert res.parser_used == "python-docx"
    assert len(res.elements) >= 4

    types = [e.type for e in res.elements]
    assert "text" in types
    assert "table" in types

    table_elem = next(e for e in res.elements if e.type == "table")
    assert table_elem.table_data is not None
    assert "Equipment ID" in table_elem.table_data["headers"]
    assert len(table_elem.table_data["rows"]) == 2
    assert table_elem.confidence == 1.0


@pytest.mark.anyio
async def test_pptx_parser(sample_pptx_bytes):
    res = await pptx_parser.parse(
        sample_pptx_bytes,
        filename="test.pptx",
        document_id="doc_pptx_1",
        file_hash="hash_pptx",
    )
    assert res.total_pages == 2
    assert res.parser_used == "python-pptx"

    # Verify slide provenance
    slide_numbers = {e.slide for e in res.elements}
    assert 1 in slide_numbers
    assert 2 in slide_numbers

    # Verify table extracted from slide 2
    table_elems = [e for e in res.elements if e.type == "table"]
    assert len(table_elems) == 1
    assert table_elems[0].slide == 2
    assert table_elems[0].table_data["headers"] == ["Metric", "Value"]


@pytest.mark.anyio
async def test_xlsx_parser(sample_xlsx_bytes):
    res = await xlsx_parser.parse(
        sample_xlsx_bytes,
        filename="test.xlsx",
        document_id="doc_xlsx_1",
        file_hash="hash_xlsx",
    )
    assert res.total_pages == 2
    assert res.parser_used == "openpyxl"

    sheets = {e.sheet for e in res.elements}
    assert "Summary" in sheets
    assert "Specifications" in sheets

    # Verify formula extraction
    formula_elems = [e for e in res.elements if e.type == "formula"]
    assert len(formula_elems) >= 1
    assert formula_elems[0].text == "=AVERAGE(B2:B3)"
    assert formula_elems[0].sheet == "Summary"
    assert formula_elems[0].metadata["cell_coordinate"] == "B4"


@pytest.mark.anyio
async def test_csv_parser(sample_csv_bytes):
    res = await csv_parser.parse(
        sample_csv_bytes,
        filename="test.csv",
        document_id="doc_csv_1",
        file_hash="hash_csv",
    )
    assert res.total_pages == 1
    assert res.parser_used == "csv"
    assert len(res.elements) == 1

    elem = res.elements[0]
    assert elem.type == "table"
    assert elem.table_data["headers"] == ["Asset_ID", "Location", "Status", "Calibration_Date"]
    assert len(elem.table_data["rows"]) == 2
    assert elem.confidence == 1.0


@pytest.mark.anyio
async def test_txt_parser(sample_txt_bytes):
    res = await txt_parser.parse(
        sample_txt_bytes,
        filename="test.txt",
        document_id="doc_txt_1",
        file_hash="hash_txt",
    )
    assert res.total_pages == 1
    assert res.parser_used == "text"
    assert len(res.elements) == 3
    assert res.elements[0].row == 1


# --- Integration Tests: API End-to-End Across All Supported Formats ---

@pytest.mark.parametrize(
    "filename,fixture_name,mime,expected_type",
    [
        ("test.docx", "sample_docx_bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
        ("test.pptx", "sample_pptx_bytes", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
        ("test.xlsx", "sample_xlsx_bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
        ("test.csv", "sample_csv_bytes", "text/csv", "csv"),
        ("test.txt", "sample_txt_bytes", "text/plain", "txt"),
    ],
)
def test_api_e2e_all_formats(request, filename, fixture_name, mime, expected_type):
    file_bytes = request.getfixturevalue(fixture_name)

    upload_res = client.post(
        "/api/documents",
        files={"file": (filename, file_bytes, mime)},
    )
    assert upload_res.status_code in (200, 202)
    doc_id = upload_res.json()["document_id"]

    # Poll status
    max_retries = 15
    status_data = None
    for _ in range(max_retries):
        s_res = client.get(f"/api/documents/{doc_id}")
        assert s_res.status_code == 200
        status_data = s_res.json()
        if status_data["status"] in ("completed", "failed"):
            break
        time.sleep(0.3)

    assert status_data["status"] == "completed"
    assert status_data["pages"] >= 1

    # Fetch canonical evidence
    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    doc_evidence = DocumentEvidence(**ev_res.json())
    assert doc_evidence.document_id == doc_id
    assert doc_evidence.file_type == expected_type
    assert doc_evidence.file_size == len(file_bytes)
    assert len(doc_evidence.elements) > 0
    for el in doc_evidence.elements:
        assert isinstance(el, EvidenceElement)
        assert el.confidence > 0.0


def test_api_unsupported_file_fails_gracefully():
    corrupted_data = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    upload_res = client.post(
        "/api/documents",
        files={"file": ("corrupt.bin", corrupted_data, "application/octet-stream")},
    )
    assert upload_res.status_code in (200, 202)
    doc_id = upload_res.json()["document_id"]

    time.sleep(0.5)
    s_res = client.get(f"/api/documents/{doc_id}")
    assert s_res.status_code == 200
    status_data = s_res.json()
    assert status_data["status"] == "failed"
    assert "Unsupported file format" in status_data["error"]


def test_mrpl_csr_benchmark_pdf():
    """Benchmark test verifying extraction on the dense MRPL CSR report PDF."""
    pdf_path = Path(__file__).parent.parent / "sample_documents" / "mrpl_csr_2025_26.pdf"
    assert pdf_path.exists(), "mrpl_csr_2025_26.pdf should exist in sample_documents"

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    info = detector.detect(file_bytes, "mrpl_csr_2025_26.pdf")
    assert info.file_type == FileType.PDF

    upload_res = client.post(
        "/api/documents",
        files={"file": ("mrpl_csr_2025_26.pdf", file_bytes, "application/pdf")},
    )
    assert upload_res.status_code in (200, 202)
    doc_id = upload_res.json()["document_id"]

    # Poll status (PDF may take up to 20s)
    max_retries = 25
    status_data = None
    for _ in range(max_retries):
        s_res = client.get(f"/api/documents/{doc_id}")
        assert s_res.status_code == 200
        status_data = s_res.json()
        if status_data["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)

    assert status_data["status"] == "completed"
    assert status_data["pages"] >= 1

    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    evidence = DocumentEvidence(**ev_res.json())
    assert evidence.total_pages == status_data["pages"]
    assert len(evidence.elements) > 0
    assert evidence.overall_confidence > 0.0
