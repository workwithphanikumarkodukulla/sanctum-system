"""Integration and regression test suite for Sanctum System Document Engine integration.

Covers tests A through K:
A. find a document
B. analyze PDF
C. analyze PPTX
D. analyze an unsupported file
E. nonexistent file
F. malformed document
G. preserve provenance
H. preserve document ID / hash
I. preserve confidence / review flags
J. ordinary conversation does not invoke DocumentTool
K. unrelated workspace request does not invoke DocumentTool
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agent import CodingAgent, _make_langchain_tools
from app.config import Config
from app.tools.document_tool import DocumentTool
from app.tools.manager import ToolManager
from app.tools.workspace import WorkspaceTool


@pytest.fixture
def test_workspace():
    """Create a temporary workspace populated with test documents."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum_test_ws_"))
    
    # 1. Plain code/text files
    (temp_dir / "main.py").write_text("print('hello world')", encoding="utf-8")
    (temp_dir / "notes.txt").write_text("Meeting notes from Monday", encoding="utf-8")

    # 2. Copy sample documents from engine repo if present
    repo_samples = Path(__file__).resolve().parent.parent.parent / "sanctum-file-engine-code" / "sample_documents"
    samples_dir = temp_dir / "sample_documents"
    samples_dir.mkdir(parents=True, exist_ok=True)

    if repo_samples.exists():
        for item in repo_samples.iterdir():
            if item.is_file():
                shutil.copy(item, samples_dir / item.name)

    # 3. Create dummy unsupported file
    (temp_dir / "corrupted_archive.bin").write_bytes(b"\x00\x01\x02\x03\x04\x05\x06\x07")

    # 4. Create empty 0-byte file
    (temp_dir / "empty_doc.pdf").write_bytes(b"")

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# TEST A: Find a document
# ==============================================================================
def test_a_find_document(test_workspace):
    """Test workspace file discovery by glob pattern, substring keyword, and extension."""
    ws_tool = WorkspaceTool(root_dir=test_workspace)

    # Search for PPTX files
    res_pptx = ws_tool.execute(action="find_files", pattern="*.pptx")
    assert res_pptx["action"] == "find_files"
    assert res_pptx["count"] >= 1
    assert any("BLOODLINK" in m["filename"] for m in res_pptx["matches"])

    # Search for keyword "bloodlink" (case-insensitive)
    res_kw = ws_tool.execute(action="find_files", pattern="bloodlink")
    assert res_kw["count"] >= 1
    assert any("BLOODLINK" in m["filename"] for m in res_kw["matches"])

    # Search for PDF files
    res_pdf = ws_tool.execute(action="find_files", pattern="*.pdf")
    assert res_pdf["count"] >= 1
    assert any("sample_inspection.pdf" in m["filename"] for m in res_pdf["matches"])

    # LangChain tool wrapper test
    tm = ToolManager(root_dir=test_workspace)
    tools = {t.name: t for t in _make_langchain_tools(tm)}
    assert "find_files" in tools
    lc_res = json.loads(tools["find_files"].invoke({"pattern": "*inspection*"}))
    assert lc_res["count"] >= 1
    assert any("inspection" in m["filename"].lower() for m in lc_res["matches"])


# ==============================================================================
# TEST B: Analyze PDF
# ==============================================================================
def test_b_analyze_pdf(test_workspace):
    """Test DocumentTool extraction of PDF documents."""
    pdf_path = "sample_documents/sample_inspection.pdf"
    full_pdf_path = test_workspace / pdf_path
    assert full_pdf_path.exists(), "Sample inspection PDF must exist for Test B."

    doc_tool = DocumentTool(root_dir=test_workspace)

    # Mock engine response if Document Engine is offline during isolated unit run
    mock_engine_response = {
        "document_id": "doc_test_pdf_001",
        "filename": "sample_inspection.pdf",
        "file_type": "pdf",
        "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "file_size": 2830,
        "processing_status": "completed",
        "total_pages": 1,
        "overall_confidence": 0.965,
        "metadata": {
            "pipeline_summary": {
                "total_elements": 6,
                "element_types": {"heading": 1, "text": 4, "table": 1},
                "conflicts_requiring_review": 0,
            }
        },
        "elements": [
            {
                "id": "p1_e1",
                "page": 1,
                "type": "heading",
                "text": "Pressure Vessel Ultrasonic Thickness Inspection Report",
                "reading_order": 1,
                "confidence": 0.99,
                "bbox": [54.0, 50.0, 500.0, 75.0],
                "extraction_model": "PyMuPDF",
            },
            {
                "id": "p1_e2",
                "page": 1,
                "type": "table",
                "text": "Inspection Zone | Nominal (mm) | Measured (mm) | Compliance",
                "reading_order": 2,
                "confidence": 0.98,
                "bbox": [54.0, 100.0, 550.0, 250.0],
                "extraction_model": "PyMuPDF",
                "table_data": {
                    "headers": ["Inspection Zone", "Nominal (mm)", "Measured (mm)", "Compliance"],
                    "rows": [
                        ["Shell Ring 1", "38.50", "37.85", "PASS"],
                        ["Bottom Nozzle N1", "25.40", "22.80", "MONITOR"],
                    ],
                },
            },
        ],
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_response

        res = doc_tool.execute(path=pdf_path, mode="summary")
        assert res["status"] == "success"
        assert res["document_id"] == "doc_test_pdf_001"
        assert res["file_type"] == "pdf"
        assert res["total_pages"] == 1
        assert len(res["tables_found"]) >= 1
        assert res["tables_found"][0]["headers"] == ["Inspection Zone", "Nominal (mm)", "Measured (mm)", "Compliance"]
        assert len(res["outline"]) >= 1
        assert "Pressure Vessel" in res["outline"][0]["heading"]


# ==============================================================================
# TEST C: Analyze PPTX
# ==============================================================================
def test_c_analyze_pptx(test_workspace):
    """Test DocumentTool extraction of PPTX presentations (BloodLink)."""
    pptx_path = "sample_documents/BLOODLINK _ Team-CodeAlchemy.pptx"
    full_pptx_path = test_workspace / pptx_path
    assert full_pptx_path.exists(), "BloodLink presentation must exist for Test C."

    doc_tool = DocumentTool(root_dir=test_workspace)

    mock_pptx_response = {
        "document_id": "doc_test_pptx_bloodlink",
        "filename": "BLOODLINK _ Team-CodeAlchemy.pptx",
        "file_type": "pptx",
        "file_hash": "a1b2c3d4e5f67890",
        "file_size": 8335384,
        "processing_status": "completed",
        "total_pages": 10,
        "total_slides": 10,
        "overall_confidence": 0.95,
        "metadata": {
            "pipeline_summary": {
                "total_elements": 25,
                "element_types": {"heading": 10, "text": 15},
                "conflicts_requiring_review": 0,
            }
        },
        "elements": [
            {
                "id": "s1_e1",
                "slide": 1,
                "page": 1,
                "type": "heading",
                "text": "BLOODLINK: Intelligent Emergency Blood Donor Dispatch",
                "reading_order": 1,
                "confidence": 0.99,
                "bbox": [50.0, 50.0, 600.0, 120.0],
                "extraction_model": "python-pptx",
            },
            {
                "id": "s3_e2",
                "slide": 3,
                "page": 3,
                "type": "text",
                "text": "Technology Stack: FastAPI, Flutter, PostgreSQL, Redis, Google Maps API, WebSockets",
                "reading_order": 2,
                "confidence": 0.98,
                "bbox": [50.0, 150.0, 600.0, 300.0],
                "extraction_model": "python-pptx",
            },
        ],
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_pptx_response

        res = doc_tool.execute(path=pptx_path, mode="summary")
        assert res["status"] == "success"
        assert res["document_id"] == "doc_test_pptx_bloodlink"
        assert res["file_type"] == "pptx"
        assert res["total_slides"] == 10
        assert len(res["outline"]) >= 1
        assert "BLOODLINK" in res["outline"][0]["heading"]
        assert any("Technology Stack" in excerpt["text"] for excerpt in res["key_content_excerpts"])


# ==============================================================================
# TEST D: Analyze an unsupported file
# ==============================================================================
def test_d_analyze_unsupported_file(test_workspace):
    """Test DocumentTool graceful rejection of unsupported file types."""
    doc_tool = DocumentTool(root_dir=test_workspace)

    mock_unsupported_response = {
        "document_id": "doc_unsupported_01",
        "status": "failed",
        "detected_file_type": "unknown",
        "error": "Unsupported file format: unknown. Supported formats: PDF, DOCX, PPTX, XLSX, CSV, TXT, PNG, JPG, WEBP, TIFF.",
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_unsupported_response

        res = doc_tool.execute(path="corrupted_archive.bin")
        assert res["status"] == "unsupported"
        assert "Unsupported file format" in res["error"]
        assert res["hint"] is not None


# ==============================================================================
# TEST E: Nonexistent file
# ==============================================================================
def test_e_nonexistent_file(test_workspace):
    """Test DocumentTool handling of non-existent file path."""
    doc_tool = DocumentTool(root_dir=test_workspace)
    res = doc_tool.execute(path="nonexistent_folder/missing_file.pdf")
    assert res["status"] == "error"
    assert "File not found" in res["error"]


# ==============================================================================
# TEST F: Malformed / empty document
# ==============================================================================
def test_f_malformed_document(test_workspace):
    """Test DocumentTool rejection of 0-byte empty files."""
    doc_tool = DocumentTool(root_dir=test_workspace)
    res = doc_tool.execute(path="empty_doc.pdf")
    assert res["status"] == "error"
    assert "empty (0 bytes)" in res["error"]


# ==============================================================================
# TEST G: Preserve provenance
# ==============================================================================
def test_g_preserve_provenance(test_workspace):
    """Verify that page/slide numbers, bounding boxes, extraction model, and reading orders are preserved."""
    doc_tool = DocumentTool(root_dir=test_workspace)

    mock_response = {
        "document_id": "doc_provenance_01",
        "filename": "inspection.pdf",
        "file_type": "pdf",
        "total_pages": 2,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "metadata": {"pipeline_summary": {"total_elements": 1}},
        "elements": [
            {
                "id": "p2_e5",
                "page": 2,
                "slide": None,
                "reading_order": 5,
                "bbox": [10.5, 20.0, 300.0, 150.0],
                "type": "table",
                "text": "Header A | Header B",
                "extraction_model": "PyMuPDF",
                "table_data": {"headers": ["Header A", "Header B"], "rows": [["1", "2"]]},
                "provenance": {"source": "native_layout"},
            }
        ],
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response

        res = doc_tool.execute(path="sample_documents/sample_inspection.pdf", mode="tables")
        assert res["status"] == "success"
        table = res["tables"][0]
        assert table["id"] == "p2_e5"
        assert table["page"] == 2
        assert table["bbox"] == [10.5, 20.0, 300.0, 150.0]
        assert table["provenance"] == {"source": "native_layout"}


# ==============================================================================
# TEST H: Preserve document ID and hash
# ==============================================================================
def test_h_preserve_document_id_and_hash(test_workspace):
    """Verify document_id and SHA-256 file_hash are preserved in output."""
    doc_tool = DocumentTool(root_dir=test_workspace)

    mock_response = {
        "document_id": "doc_canonical_998877",
        "filename": "sample_inspection.pdf",
        "file_type": "pdf",
        "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "file_size": 2830,
        "processing_status": "completed",
        "total_pages": 1,
        "overall_confidence": 0.95,
        "metadata": {"pipeline_summary": {"total_elements": 0}},
        "elements": [],
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response

        res = doc_tool.execute(path="sample_documents/sample_inspection.pdf", mode="summary")
        assert res["document_id"] == "doc_canonical_998877"
        assert res["file_hash"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert res["file_size"] == 2830


# ==============================================================================
# TEST I: Preserve confidence and review flags
# ==============================================================================
def test_i_preserve_confidence_and_review_flags(test_workspace):
    """Verify overall confidence and requires_human_review conflict details are exposed."""
    doc_tool = DocumentTool(root_dir=test_workspace)

    mock_response = {
        "document_id": "doc_conflict_01",
        "filename": "report.pdf",
        "file_type": "pdf",
        "file_hash": "123456",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.812,
        "metadata": {
            "pipeline_summary": {
                "total_elements": 1,
                "conflicts_requiring_review": 1,
            }
        },
        "elements": [
            {
                "id": "p1_e3",
                "page": 1,
                "type": "text",
                "text": "37.85 mm",
                "confidence": 0.75,
                "metadata": {
                    "requires_human_review": True,
                    "reconciliation_category": "number_mismatch",
                    "ocr_candidate": "37.85 mm",
                    "vlm_candidate": "37.35 mm",
                    "reconciliation_agreement_status": "material_disagreement",
                    "disagreement_details": "OCR detected 37.85 while VLM detected 37.35",
                },
            }
        ],
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_response

        res = doc_tool.execute(path="sample_documents/sample_inspection.pdf", mode="summary")
        assert res["requires_human_review"] is True
        assert res["conflicts_count"] == 1
        assert res["conflicts"][0]["ocr_candidate"] == "37.85 mm"
        assert res["conflicts"][0]["vlm_candidate"] == "37.35 mm"
        assert res["conflicts"][0]["agreement_status"] == "material_disagreement"


# ==============================================================================
# TEST J: Ordinary conversation does not invoke DocumentTool
# ==============================================================================
def test_j_ordinary_conversation_no_document_tool(test_workspace):
    """Verify that ordinary conversation requests do not invoke read_document."""
    mock_llm_manager = MagicMock()
    mock_llm_manager.model_name = "test-model"
    mock_llm = MagicMock()
    mock_llm_manager._llm = mock_llm

    # Simulate LLM returning a plain conversational answer without tool calls
    from langchain_core.messages import AIMessage
    mock_llm_with_tools = MagicMock()
    mock_llm_with_tools.invoke.return_value = AIMessage(
        content="Hello! I am Sanctum, your local assistant. How can I help you today?",
        tool_calls=[],
    )
    mock_llm.bind_tools.return_value = mock_llm_with_tools

    agent = CodingAgent(mock_llm_manager, tool_manager=ToolManager(root_dir=test_workspace))

    result = agent.chat("Hello there, how are you?")
    assert "Sanctum" in result["reply"]
    # Verify no tool calls were executed
    assert len(result["tool_actions"]) == 0
    assert not any(a["tool"] == "read_document" for a in result["tool_actions"])


# ==============================================================================
# TEST K: Unrelated workspace request does not invoke DocumentTool
# ==============================================================================
def test_k_unrelated_workspace_request_no_document_tool(test_workspace):
    """Verify that file operations invoke file tools and do NOT invoke read_document."""
    mock_llm_manager = MagicMock()
    mock_llm_manager.model_name = "test-model"
    mock_llm = MagicMock()
    mock_llm_manager._llm = mock_llm

    # Simulate LLM invoking create_file
    from langchain_core.messages import AIMessage
    mock_llm_with_tools = MagicMock()
    mock_llm_with_tools.invoke.return_value = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "create_file",
                "args": {"path": "test_script.py", "content": "print('testing')\n"},
                "id": "call_123",
            }
        ],
    )
    mock_llm.bind_tools.return_value = mock_llm_with_tools

    agent = CodingAgent(mock_llm_manager, tool_manager=ToolManager(root_dir=test_workspace))

    # Second invocation in loop terminates
    def mock_invoke_side_effect(msgs):
        if len(msgs) > 2:
            return AIMessage(content="Successfully created test_script.py.", tool_calls=[])
        return mock_llm_with_tools.invoke.return_value

    mock_llm_with_tools.invoke.side_effect = mock_invoke_side_effect

    result = agent.chat("Create a python file test_script.py that prints testing")
    assert any(a["tool"] == "create_file" for a in result["tool_actions"])
    assert not any(a["tool"] == "read_document" for a in result["tool_actions"])
    assert (test_workspace / "test_script.py").exists()
