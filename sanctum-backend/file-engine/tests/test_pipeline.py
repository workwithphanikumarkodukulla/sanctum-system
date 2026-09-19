"""End-to-end integration and pipeline tests for Multimodal Evidence Engine."""
import io
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.evidence.schema import DocumentEvidence, EvidenceElement
from app.main import app

client = TestClient(app)


@pytest.fixture
def sample_pdf_path():
    path = Path(__file__).parent.parent / "sample_documents" / "sample_inspection.pdf"
    if not path.exists():
        from sample_documents.generate_sample import generate_sample_pdf
        generate_sample_pdf(path)
    return path


def test_health_check():
    """Verify health endpoint returns status healthy and configurations."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "confidence_threshold" in data
    assert "ollama_base_url" in data


def test_e2e_document_pipeline_pdf(sample_pdf_path):
    """End-to-end test following required specification:

    1. Ingest sample PDF through POST /api/documents
    2. Poll GET /api/documents/{id} until status is 'completed'
    3. Fetch GET /api/documents/{id}/evidence
    4. Assert JSON matches DocumentEvidence schema with elements having confidence > 0.
    """
    with open(sample_pdf_path, "rb") as f:
        file_bytes = f.read()

    # 1. Upload document
    upload_res = client.post(
        "/api/documents",
        files={"file": ("sample_inspection.pdf", file_bytes, "application/pdf")},
    )
    assert upload_res.status_code in (200, 202)
    upload_data = upload_res.json()
    assert "document_id" in upload_data
    doc_id = upload_data["document_id"]
    assert upload_data["status"] in ("processing", "completed")

    # 2. Poll until completed (timeout 15s)
    max_retries = 15
    status_data = None
    for _ in range(max_retries):
        status_res = client.get(f"/api/documents/{doc_id}")
        assert status_res.status_code == 200
        status_data = status_res.json()
        if status_data["status"] in ("completed", "failed"):
            break
        time.sleep(0.5)

    assert status_data is not None
    assert status_data["status"] == "completed"
    assert status_data["pages"] >= 1
    assert status_data["overall_confidence"] > 0

    # 3. Fetch full evidence
    evidence_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert evidence_res.status_code == 200
    evidence_data = evidence_res.json()

    # 4. Assert validated against DocumentEvidence Pydantic schema
    doc_evidence = DocumentEvidence(**evidence_data)
    assert doc_evidence.document_id == doc_id
    assert doc_evidence.total_pages >= 1
    assert len(doc_evidence.elements) > 0
    assert doc_evidence.overall_confidence > 0.0

    # Check first element compliance
    first_elem = doc_evidence.elements[0]
    assert isinstance(first_elem, EvidenceElement)
    assert first_elem.confidence > 0.0
    assert len(first_elem.bbox) == 4
    assert first_elem.file_hash
    assert first_elem.timestamp

    # 5. Test page-specific endpoint
    page_res = client.get(f"/api/documents/{doc_id}/pages/1")
    assert page_res.status_code == 200
    page_elements = page_res.json()
    assert isinstance(page_elements, list)
    assert len(page_elements) > 0
    assert page_elements[0]["page"] == 1

    # 6. Test single evidence element endpoint
    elem_id = first_elem.id
    single_res = client.get(f"/api/evidence/{elem_id}")
    assert single_res.status_code == 200
    single_elem = single_res.json()
    assert single_elem["id"] == elem_id
    assert single_elem["document_id"] == doc_id


def test_image_pipeline_and_vision_endpoint():
    """Verify processing for direct image uploads and direct vision endpoint."""
    # Create a small synthetic test image
    img = Image.new("RGB", (240, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # Ingest image through pipeline
    res = client.post(
        "/api/documents",
        files={"file": ("test_meter.png", img_bytes, "image/png")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    ev = DocumentEvidence(**ev_res.json())
    assert ev.total_pages == 1
    assert ev.processing_status == "completed"

    # Test direct vision endpoint POST /api/vision/analyze
    vision_res = client.post(
        "/api/vision/analyze",
        files={"file": ("test_meter.png", img_bytes, "image/png")},
    )
    assert vision_res.status_code == 200
    vision_data = vision_res.json()
    assert vision_data["filename"] == "test_meter.png"
    assert "vision_result" in vision_data


def test_pipeline_docx_integration():
    """Verify end-to-end ingestion and normalization for DOCX files."""
    from docx import Document

    doc = Document()
    doc.add_heading("Quarterly Operations Review", level=1)
    doc.add_paragraph("All subsystems performed within optimal operating parameters.")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Component"
    table.rows[0].cells[1].text = "Uptime"
    table.rows[1].cells[0].text = "Core Engine"
    table.rows[1].cells[1].text = "99.99%"

    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    res = client.post(
        "/api/documents",
        files={"file": ("review.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    evidence = DocumentEvidence(**ev_res.json())

    assert evidence.file_type == "docx"
    assert evidence.processing_status == "completed"
    assert len(evidence.elements) >= 3
    assert evidence.elements[0].type == "heading"
    assert evidence.elements[0].provenance["source"] == "docx"
    assert any(el.type == "table" for el in evidence.elements)


def test_pipeline_pptx_integration():
    """Verify end-to-end ingestion, slide count metadata, and normalization for PPTX presentations."""
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Sanctum Architecture"
    slide.placeholders[1].text = "• Air-Gapped Engine\n• Zero Data Exfiltration"

    buf = io.BytesIO()
    prs.save(buf)
    pptx_bytes = buf.getvalue()

    res = client.post(
        "/api/documents",
        files={"file": ("deck.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    evidence = DocumentEvidence(**ev_res.json())

    assert evidence.file_type == "pptx"
    assert evidence.processing_status == "completed"
    assert evidence.total_slides == 1
    assert len(evidence.elements) >= 2
    assert evidence.elements[0].type == "heading"
    assert evidence.elements[0].slide == 1
    assert evidence.elements[0].provenance["source"] == "pptx"


def test_pipeline_xlsx_integration():
    """Verify end-to-end ingestion, worksheet metadata, and formula normalization for XLSX spreadsheets."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Telemetry"
    ws.append(["Metric", "Score"])
    ws.append(["Latency", 42])
    ws["C3"] = "=AVERAGE(B2:B2)"

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    res = client.post(
        "/api/documents",
        files={"file": ("metrics.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    evidence = DocumentEvidence(**ev_res.json())

    assert evidence.file_type == "xlsx"
    assert evidence.processing_status == "completed"
    assert evidence.worksheets is not None
    assert len(evidence.worksheets) == 1
    assert evidence.worksheets[0].name == "Telemetry"

    # Verify both grid table and formula elements normalized
    types = [el.type for el in evidence.elements]
    assert "table" in types
    assert "formula" in types
    formula_elem = next(el for el in evidence.elements if el.type == "formula")
    assert formula_elem.text == "=AVERAGE(B2:B2)"
    assert formula_elem.sheet == "Telemetry"


def test_pipeline_csv_integration():
    """Verify end-to-end ingestion and table extraction for CSV files."""
    csv_content = "device_id,temperature,status\nDEV-001,36.5,NOMINAL\nDEV-002,41.2,WARNING\n".encode("utf-8")

    res = client.post(
        "/api/documents",
        files={"file": ("telemetry.csv", csv_content, "text/csv")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    evidence = DocumentEvidence(**ev_res.json())

    assert evidence.file_type == "csv"
    assert evidence.processing_status == "completed"
    assert len(evidence.elements) == 1
    assert evidence.elements[0].type == "table"
    assert evidence.elements[0].table_data["headers"] == ["device_id", "temperature", "status"]


def test_pipeline_txt_integration():
    """Verify end-to-end ingestion and block line normalization for plain text files."""
    txt_content = "SECURITY NOTICE\n\nAll connections to the Sanctum Evidence Engine are strictly local.\n".encode("utf-8")

    res = client.post(
        "/api/documents",
        files={"file": ("notice.txt", txt_content, "text/plain")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    ev_res = client.get(f"/api/documents/{doc_id}/evidence")
    assert ev_res.status_code == 200
    evidence = DocumentEvidence(**ev_res.json())

    assert evidence.file_type == "txt"
    assert evidence.processing_status == "completed"
    assert len(evidence.elements) >= 1
    assert evidence.elements[0].provenance["source"] == "txt"


def test_pipeline_webp_and_tiff_image_integration():
    """Verify WEBP and TIFF raster images are ingested through detector, router, and OCR pipeline."""
    # 1. WEBP
    img_webp = Image.new("RGB", (100, 50), color=(255, 255, 255))
    buf_webp = io.BytesIO()
    img_webp.save(buf_webp, format="WEBP")
    webp_bytes = buf_webp.getvalue()

    res_webp = client.post(
        "/api/documents",
        files={"file": ("photo.webp", webp_bytes, "image/webp")},
    )
    assert res_webp.status_code in (200, 202)
    doc_webp_id = res_webp.json()["document_id"]
    ev_webp = client.get(f"/api/documents/{doc_webp_id}/evidence").json()
    assert ev_webp["file_type"] == "webp"
    assert ev_webp["processing_status"] == "completed"

    # 2. TIFF
    img_tiff = Image.new("RGB", (100, 50), color=(255, 255, 255))
    buf_tiff = io.BytesIO()
    img_tiff.save(buf_tiff, format="TIFF")
    tiff_bytes = buf_tiff.getvalue()

    res_tiff = client.post(
        "/api/documents",
        files={"file": ("scan.tiff", tiff_bytes, "image/tiff")},
    )
    assert res_tiff.status_code in (200, 202)
    doc_tiff_id = res_tiff.json()["document_id"]
    ev_tiff = client.get(f"/api/documents/{doc_tiff_id}/evidence").json()
    assert ev_tiff["file_type"] == "tiff"
    assert ev_tiff["processing_status"] == "completed"


def test_pipeline_unsupported_file_fails_cleanly():
    """Verify that unsupported file formats fail cleanly without server crashes."""
    unsupported_bytes = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # ELF binary

    res = client.post(
        "/api/documents",
        files={"file": ("binary_program.bin", unsupported_bytes, "application/octet-stream")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    status_res = client.get(f"/api/documents/{doc_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "failed"
    assert status_data["error"] is not None
    assert "Unsupported file format" in status_data["error"]

