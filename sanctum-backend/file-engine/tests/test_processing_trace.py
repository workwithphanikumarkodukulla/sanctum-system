"""Comprehensive tests for ProcessingTrace observability and audit log layer."""
from __future__ import annotations

import io
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.evidence.schema import DocumentEvidence
from app.extractors.ocr import OCRExtractor
from app.main import app
from app.observability.processing_trace import ProcessingTrace, get_current_trace, set_current_trace, trace_store
from app.parsers.pdf import pdf_parser
from app.processing.pipeline import pipeline

client = TestClient(app)


def _create_synthetic_image(text_desc: str = "test") -> bytes:
    """Create a minimal RGB PNG image."""
    img = Image.new("RGB", (200, 60), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def clean_trace_context():
    """Ensure clean trace store and context variable before and after each trace test."""
    trace_store.clear()
    set_current_trace(None)
    yield
    trace_store.clear()
    set_current_trace(None)


@pytest.mark.anyio
async def test_trace_image_paddleocr_lifecycle():
    """1. Test Image -> PaddleOCR trace (Detector -> Router -> PaddleOCR -> Classifier -> Gate -> Evidence -> Storage)."""
    img_bytes = _create_synthetic_image("PaddleOCR pipeline test")
    doc_id = "test_img_trace_01"

    # Mock PaddleOCR enabled and successful
    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", return_value=[
             {"type": "text", "bbox": [0, 0, 100, 30], "text": "Pressure Vessel PV-101", "confidence": 0.94, "extraction_model": "PaddleOCR"}
         ]):
        doc = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="test_vessel.png",
        )

    assert doc.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None
    events = trace.events

    stages = [e.stage for e in events]
    components = [e.component for e in events]

    assert "INGESTION" in stages
    assert "DETECTION" in stages
    assert "ROUTING" in stages
    assert "VISUAL_EXTRACTION" in stages
    assert "CONTENT_CLASSIFICATION" in stages
    assert "CONFIDENCE_GATE" in stages
    assert "CANONICAL_EVIDENCE" in stages
    assert "STORAGE" in stages

    # Ensure PaddleOCR is explicitly recorded and Tesseract NEVER executed
    assert "PaddleOCR" in components
    assert "Tesseract" not in components

    ocr_events = [e for e in events if e.stage == "VISUAL_EXTRACTION" and e.component == "PaddleOCR"]
    assert len(ocr_events) == 2
    assert ocr_events[0].event == "OCR_STARTED"
    assert ocr_events[1].event == "OCR_COMPLETED"
    assert ocr_events[1].metadata["average_confidence"] == 0.94


@pytest.mark.anyio
async def test_trace_digital_pdf_pymupdf():
    """2. Test Digital PDF -> PyMuPDF trace."""
    import fitz

    # Create a simple digital PDF with text
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Sanctum Digital Engine Specification Document")
    pdf_bytes = doc.tobytes()
    doc.close()

    doc_id = "test_digital_pdf_trace"
    doc_res = await pipeline.process_document(
        document_id=doc_id,
        file_bytes=pdf_bytes,
        filename="digital_spec.pdf",
    )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    pymupdf_events = [e for e in trace.events if e.component == "PyMuPDF"]
    assert len(pymupdf_events) >= 2
    inspected = [e for e in pymupdf_events if e.event == "PAGE_INSPECTED"]
    assert inspected and inspected[0].metadata["is_digital"] is True
    extracted = [e for e in pymupdf_events if e.event == "TEXT_EXTRACTED"]
    assert extracted and extracted[0].status == "success"


@pytest.mark.anyio
async def test_trace_scanned_pdf_rendering_and_ocr():
    """3. Test Scanned PDF -> PDF inspection/rendering -> PaddleOCR."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    img = Image.new("RGB", (300, 100), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(fitz.Rect(50, 50, 350, 150), stream=buf.getvalue())
    scanned_pdf_bytes = doc.tobytes()
    doc.close()

    doc_id = "test_scanned_pdf_trace"
    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", return_value=[
             {"type": "text", "bbox": [50, 50, 350, 150], "text": "Scanned Certificate", "confidence": 0.91, "extraction_model": "PaddleOCR"}
         ]):
        doc_res = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=scanned_pdf_bytes,
            filename="scanned_cert.pdf",
        )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    render_events = [e for e in trace.events if e.event == "PAGE_RENDERED_FOR_OCR"]
    assert len(render_events) == 1
    assert render_events[0].component == "PyMuPDF"

    ocr_events = [e for e in trace.events if e.component == "PaddleOCR"]
    assert len(ocr_events) == 2
    assert ocr_events[1].event == "OCR_COMPLETED"


@pytest.mark.anyio
async def test_trace_formula_image_formula_extractor_and_sympy():
    """4. Test Formula image -> Formula classification -> FormulaExtractor (without automatic SymPy calculation during ingestion)."""
    img_bytes = _create_synthetic_image("Calculus formula")
    doc_id = "test_formula_trace"

    # Simulate PaddleOCR reading a calculus expression
    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", return_value=[
             {
                 "type": "formula",
                 "bbox": [10, 10, 180, 50],
                 "text": "d/dx(x^3 + 2*x^2 - 5*x + 1)",
                 "confidence": 0.95,
                 "extraction_model": "PaddleOCR",
             }
         ]), \
         patch("app.models.vision_client.vision_client.reread_cropped_region", return_value=(None, 0.0)):
        doc_res = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="calculus_problem.png",
        )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    # Check FormulaExtractor event under SPECIALIZED_EXTRACTION
    formula_events = [e for e in trace.events if e.component == "FormulaExtractor"]
    assert len(formula_events) >= 1
    assert formula_events[0].stage == "SPECIALIZED_EXTRACTION"
    assert formula_events[0].status == "success"
    assert "d/dx" in formula_events[0].metadata["latex"]

    # Ingestion does NOT invoke SymPy computation: trace must not claim symbolic computation occurred
    sympy_computation_events = [e for e in trace.events if e.stage == "SYMBOLIC_COMPUTATION"]
    assert len(sympy_computation_events) == 0


@pytest.mark.anyio
async def test_trace_no_formula_sympy_skipped():
    """5. Verify that when no formula is present, no symbolic computation is executed."""
    img_bytes = _create_synthetic_image("General text only")
    doc_id = "test_no_formula_trace"

    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", return_value=[
             {
                 "type": "text",
                 "bbox": [10, 10, 180, 50],
                 "text": "The annual meeting will be held on Monday afternoon.",
                 "confidence": 0.95,
                 "extraction_model": "PaddleOCR",
             }
         ]):
        doc_res = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="meeting_notice.png",
        )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    # No symbolic computation in trace
    sympy_events = [e for e in trace.events if e.component == "SymPy"]
    assert len(sympy_events) == 0


@pytest.mark.anyio
async def test_trace_high_confidence_vlm_skipped():
    """6. High-confidence image -> Confidence Gate ACCEPT -> VLM SKIPPED."""
    img_bytes = _create_synthetic_image("Clear clean text")
    doc_id = "test_high_conf_trace"

    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", return_value=[
             {
                 "type": "text",
                 "bbox": [10, 10, 180, 50],
                 "text": "Clear printed invoice number INV-9901",
                 "confidence": 0.96,
                 "extraction_model": "PaddleOCR",
             }
         ]):
        doc_res = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="invoice.png",
        )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    gate_events = [e for e in trace.events if e.component == "ConfidenceGate"]
    assert len(gate_events) >= 1
    assert gate_events[0].metadata["decision"] == "ACCEPT"
    assert gate_events[0].metadata["vlm"] == "SKIPPED"

    # VLM must NOT have been escalated
    vlm_escalations = [e for e in trace.events if e.component == "Local VLM"]
    assert len(vlm_escalations) == 0


@pytest.mark.anyio
async def test_trace_low_confidence_vlm_escalation_and_reconciliation():
    """7. Low-confidence image -> Confidence Gate ESCALATE -> VLM -> Reconciliation."""
    img_bytes = _create_synthetic_image("Blurry low confidence text")
    doc_id = "test_low_conf_trace"

    from app.models.vision_client import vision_client

    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", return_value=[
             {
                 "type": "text",
                 "bbox": [10, 10, 180, 50],
                 "text": "D4t4 5pec",
                 "confidence": 0.42,  # Low confidence triggers escalation
                 "extraction_model": "PaddleOCR",
             }
         ]), \
         patch.object(vision_client, "reread_cropped_region", return_value=("Data Spec", 0.92)):
        doc_res = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="blurry_spec.png",
        )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    gate_events = [e for e in trace.events if e.component == "ConfidenceGate"]
    assert any(e.metadata["decision"] == "ESCALATE" for e in gate_events)

    vlm_events = [e for e in trace.events if e.component == "Local VLM"]
    assert len(vlm_events) >= 2
    assert any(e.event == "ESCALATION_STARTED" for e in vlm_events)
    assert any(e.event == "ESCALATION_COMPLETED" and e.status == "success" for e in vlm_events)

    recon_events = [e for e in trace.events if e.component == "EvidenceReconciler"]
    assert len(recon_events) >= 1
    assert recon_events[0].status == "success"


@pytest.mark.anyio
async def test_trace_handwriting_mandatory_vlm_escalation_lifecycle():
    """7b. Handwriting -> Handwriting detection -> Gate (HANDWRITING_OVERRIDE/ESCALATE) -> VLM -> Reconciliation."""
    img_bytes = _create_synthetic_image("Handwriting sample")
    doc_id = "test_hw_vlm_trace"

    from app.models.vision_client import vision_client

    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", return_value=[
             {
                 "type": "text",
                 "bbox": [10, 10, 180, 50],
                 "text": "Deak Magnus, ouk gratitude fer youk lectures",
                 "confidence": 0.95,  # High OCR confidence
                 "extraction_model": "PaddleOCR",
             }
         ]), \
         patch.object(vision_client, "reread_cropped_region", return_value=("Dear Magnus, our gratitude for your lectures", 0.94)):
        doc_res = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="cursive_letter.png",
        )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    # Check that HANDWRITING classification occurred
    hw_events = [e for e in trace.events if e.component == "HandwritingClassifier"]
    assert len(hw_events) >= 1

    # Check that ConfidenceGate escalated handwriting despite high OCR confidence
    gate_events = [e for e in trace.events if e.component == "ConfidenceGate"]
    assert any(e.event == "HANDWRITING_OVERRIDE" or e.metadata.get("decision") == "ESCALATE" for e in gate_events)

    # Check VLM execution
    vlm_events = [e for e in trace.events if e.component == "Local VLM"]
    assert len(vlm_events) >= 2
    assert any(e.event == "ESCALATION_STARTED" for e in vlm_events)
    assert any(e.event == "ESCALATION_COMPLETED" and e.status == "success" for e in vlm_events)

    # Check Reconciliation execution
    recon_events = [e for e in trace.events if e.component == "EvidenceReconciler"]
    assert len(recon_events) >= 1
    assert recon_events[0].status == "success"

    # Evidence assembled
    elem = doc_res.elements[0]
    assert elem.type == "handwriting"
    assert elem.metadata["ocr_candidate"] == "Deak Magnus, ouk gratitude fer youk lectures"
    assert elem.metadata["vlm_candidate"] == "Dear Magnus, our gratitude for your lectures"



@pytest.mark.anyio
async def test_trace_paddle_failure_triggers_tesseract_fallback():
    """8. PaddleOCR failure -> PaddleOCR FAILED -> Tesseract FALLBACK."""
    img_bytes = _create_synthetic_image("Fallback test")
    doc_id = "test_fallback_trace"

    def raise_paddle_error(img):
        raise RuntimeError("PaddleOCR inference engine segmentation fault or out of memory")

    with patch.object(OCRExtractor, "is_paddle_active", True), \
         patch.object(OCRExtractor, "_extract_paddle", side_effect=raise_paddle_error), \
         patch.object(OCRExtractor, "_extract_tesseract", return_value=[
             {
                 "type": "text",
                 "bbox": [0, 0, 100, 30],
                 "text": "Recovered by Tesseract",
                 "confidence": 0.82,
                 "extraction_model": "Tesseract-Fallback",
             }
         ]):
        doc_res = await pipeline.process_document(
            document_id=doc_id,
            file_bytes=img_bytes,
            filename="fallback_doc.png",
        )

    assert doc_res.processing_status == "completed"
    trace = trace_store.get(doc_id)
    assert trace is not None

    paddle_failed = [e for e in trace.events if e.component == "PaddleOCR" and e.event == "OCR_FAILED"]
    assert len(paddle_failed) == 1
    assert paddle_failed[0].status == "error"
    assert "PaddleOCR inference engine" in paddle_failed[0].error

    tess_started = [e for e in trace.events if e.component == "Tesseract" and e.event == "FALLBACK_STARTED"]
    assert len(tess_started) == 1
    assert tess_started[0].metadata["reason"] == "PaddleOCR failure/fallback"

    tess_completed = [e for e in trace.events if e.component == "Tesseract" and e.event == "FALLBACK_COMPLETED"]
    assert len(tess_completed) == 1


def test_api_trace_endpoints():
    """9. Verify API endpoints GET /api/documents/{id}/trace, /trace/text, and /debug/trace/{id}."""
    doc_id = "test_api_trace_doc"
    trace = ProcessingTrace(
        document_id=doc_id,
        filename="api_test.png",
        file_hash="abcd1234ef5678",
        file_size=1024,
        detected_type="image/png",
    )
    trace.record_event(
        stage="VISUAL_EXTRACTION",
        component="PaddleOCR",
        event="OCR_COMPLETED",
        status="success",
        metadata={"regions": 1, "average_confidence": 0.94},
    )
    trace.finish("completed")
    trace_store.save(trace)

    # 1. JSON trace endpoint
    res_json = client.get(f"/api/documents/{doc_id}/trace")
    assert res_json.status_code == 200
    data = res_json.json()
    assert data["document_id"] == doc_id
    assert data["status"] == "completed"
    assert len(data["events"]) == 1
    assert data["events"][0]["component"] == "PaddleOCR"

    # 2. Text ASCII trace endpoint
    res_text = client.get(f"/api/documents/{doc_id}/trace/text")
    assert res_text.status_code == 200
    text_body = res_text.text
    assert "SANCTUM DOCUMENT PROCESSING TRACE" in text_body
    assert "PaddleOCR" in text_body
    assert "OCR_COMPLETED" in text_body

    # 3. Debug endpoints
    res_dbg_json = client.get(f"/debug/trace/{doc_id}")
    assert res_dbg_json.status_code == 200
    assert res_dbg_json.json()["document_id"] == doc_id

    res_dbg_text = client.get(f"/debug/trace/{doc_id}/text")
    assert res_dbg_text.status_code == 200
    assert "SANCTUM DOCUMENT PROCESSING TRACE" in res_dbg_text.text

    # 4. Verify TraceStore isolates independent document IDs without cross-leaking events
    doc_id_iso = "test_api_isolated_doc_2"
    trace_iso = ProcessingTrace(document_id=doc_id_iso, filename="isolated.png")
    trace_iso.record_event(stage="ROUTING", component="FileRouter", event="ROUTE_SELECTED")
    trace_store.save(trace_iso)
    assert trace_store.get(doc_id).document_id == doc_id
    assert trace_store.get(doc_id_iso).document_id == doc_id_iso
    assert len(trace_store.get(doc_id).events) == 1
    assert len(trace_store.get(doc_id_iso).events) == 1
    assert trace_store.get(doc_id).events[0].component == "PaddleOCR"
    assert trace_store.get(doc_id_iso).events[0].component == "FileRouter"

