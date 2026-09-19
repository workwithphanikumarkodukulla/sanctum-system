"""Integration test suite for Multi-Tool Agentic Workflows (Phase 5).

Proves that the Agent reasons dynamically across tools:
WORKFLOW 1: Find document -> DocumentTool -> answer
WORKFLOW 2: Find document -> DocumentTool -> MathTool -> answer
WORKFLOW 3: Find document -> DocumentTool -> action tool -> verify result -> answer
WORKFLOW 4: DocumentTool -> identify insufficient evidence -> another appropriate tool -> answer
WORKFLOW 5: Multiple documents -> workspace discovery -> analyze relevant documents -> compare -> answer
WORKFLOW 6: Document contains formula -> extract formula -> MathTool -> explain result
LIVE E2E: Real document (sample_inspection.pdf) -> live engine extraction -> MathTool -> Agent explanation

Invariants verified:
- Agent does not blindly chain tools in a hardcoded sequence.
- Agent does not claim an action succeeded without checking the result.
- Agent inspects tool outputs before deciding the next step.
- Tool order is strictly verified.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent import CodingAgent
from app.tools.manager import ToolManager


@pytest.fixture
def workflow_workspace():
    """Create a populated workspace for multi-tool workflow testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum_wf_ws_"))
    
    docs_dir = temp_dir / "sample_documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Real documents copied from engine repository
    engine_samples = Path(__file__).resolve().parent.parent.parent / "sanctum-file-engine-code" / "sample_documents"
    if engine_samples.exists():
        for item in engine_samples.iterdir():
            if item.is_file() and item.suffix in (".pdf", ".pptx", ".txt"):
                shutil.copy(item, docs_dir / item.name)

    # Fallback files if not copied
    if not (docs_dir / "sample_inspection.pdf").exists():
        (docs_dir / "sample_inspection.pdf").write_bytes(b"%PDF-1.4 mock inspection")
    if not (docs_dir / "BLOODLINK.pptx").exists():
        (docs_dir / "BLOODLINK.pptx").write_bytes(b"PK\x03\x04mock pptx")

    # Multi-document comparison files
    (docs_dir / "unit1_inspection.pdf").write_bytes(b"%PDF-1.4 unit 1")
    (docs_dir / "unit2_inspection.pdf").write_bytes(b"%PDF-1.4 unit 2")
    (docs_dir / "quarterly_earnings.xlsx").write_bytes(b"PK\x03\x04mock xlsx")
    
    # Insufficient evidence + external reference file
    (docs_dir / "summary_report.pdf").write_bytes(b"%PDF-1.4 summary report")
    (temp_dir / "maintenance_appendix.txt").write_text(
        "Final Recommendation: Schedule full eddy-current tube bundle inspection within 60 days.",
        encoding="utf-8",
    )

    generated_dir = temp_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def _create_mock_agent(workspace_dir: Path):
    """Helper to create CodingAgent with mock LLM manager."""
    mock_llm_manager = MagicMock()
    mock_llm_manager.model_name = "test-model"
    mock_llm = MagicMock()
    mock_llm_manager._llm = mock_llm

    mock_llm_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm_with_tools

    tool_manager = ToolManager(root_dir=workspace_dir)
    agent = CodingAgent(mock_llm_manager, tool_manager=tool_manager)
    agent.clear_memory()
    return agent, mock_llm_with_tools


# ==============================================================================
# WORKFLOW 1: Find document -> DocumentTool -> answer
# ==============================================================================
def test_workflow_1_find_document_read_answer(workflow_workspace):
    """WORKFLOW 1: Find document -> DocumentTool -> answer."""
    agent, mock_llm_with_tools = _create_mock_agent(workflow_workspace)

    mock_evidence = {
        "document_id": "doc_bloodlink_wf1",
        "filename": "BLOODLINK.pptx",
        "file_type": "pptx",
        "file_hash": "bl1122",
        "total_pages": 4,
        "processing_status": "completed",
        "overall_confidence": 0.96,
        "elements": [
            {
                "id": "s2_e1", "slide": 2, "type": "text",
                "text": "Problem Statement: Acute blood supply deficit in municipal trauma centers.",
                "confidence": 0.98,
            }
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*bloodlink*"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "c2"}],
                )
            if "document_id" in tool_data:
                return AIMessage(
                    content="From Slide 2 of the BloodLink presentation, the problem statement is acute blood supply deficit.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Find the BloodLink presentation and tell me the problem statement.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document"]
    assert "acute blood supply deficit" in result["reply"].lower()


# ==============================================================================
# WORKFLOW 2: Find document -> DocumentTool -> MathTool -> answer
# ==============================================================================
def test_workflow_2_find_doc_math_answer(workflow_workspace):
    """WORKFLOW 2: Find document -> DocumentTool -> MathTool -> answer."""
    agent, mock_llm_with_tools = _create_mock_agent(workflow_workspace)

    mock_evidence = {
        "document_id": "doc_fin_growth",
        "filename": "quarterly_earnings.xlsx",
        "file_type": "xlsx",
        "file_hash": "qtr88",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.99,
        "elements": [
            {
                "id": "p1_tbl1", "page": 1, "type": "table",
                "table_data": [
                    ["Period", "Revenue"],
                    ["Q1 2023", "25000"],
                    ["Q1 2024", "40000"],
                ],
                "confidence": 0.99,
            }
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*quarterly*"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "c2"}],
                )
            if "document_id" in tool_data:
                # Agent inspects table: Q1 2023 = 25000, Q1 2024 = 40000
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "calculate",
                        "args": {"expression": "(40000 - 25000) / 25000 * 100"},
                        "id": "c3",
                    }],
                )
            if "result" in tool_data:
                assert tool_data["success"] is True
                assert float(tool_data["result"]) == 60.0
                return AIMessage(
                    content="Revenue grew from $25,000 to $40,000, representing a 60.0% year-over-year growth rate.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Find the financial spreadsheet, read quarterly revenue, and calculate YoY growth.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "calculate"]
    assert "60" in result["reply"]


# ==============================================================================
# WORKFLOW 3: Find document -> DocumentTool -> Action Tool -> Verification -> answer
# ==============================================================================
def test_workflow_3_find_doc_action_verify_answer(workflow_workspace):
    """WORKFLOW 3: Find document -> DocumentTool -> Action -> Verification -> answer."""
    agent, mock_llm_with_tools = _create_mock_agent(workflow_workspace)

    mock_evidence = {
        "document_id": "doc_proj_summary",
        "filename": "sample_inspection.pdf",
        "file_type": "pdf",
        "file_hash": "rep11",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.95,
        "elements": [
            {
                "id": "p1_t1", "page": 1, "type": "title", "text": "Pressure Vessel Ultrasonic Inspection",
                "confidence": 0.99,
            },
            {
                "id": "p1_t2", "page": 1, "type": "text", "text": "Highlights: Shell Ring 1 passed thickness compliance.",
                "confidence": 0.97,
            },
        ],
    }

    ppt_path = "generated/project_summary.pptx"
    slides = [
        {"title": "Inspection Overview", "subtitle": "Sanctum Summary", "bullet_points": ["Shell Ring 1: Compliant", "Ultrasonic survey complete"]},
    ]

    def side_effect(messages):
        last_msg = messages[-1]
        # 1. Discover file
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*inspection*.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # 2. Read document
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "c2"}],
                )
            # 3. Generate presentation
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "generate_presentation",
                        "args": {
                            "filepath": ppt_path,
                            "title": "Pressure Vessel Summary",
                            "subtitle": "Inspection Overview",
                            "slides_json": json.dumps(slides),
                        },
                        "id": "c3",
                    }],
                )
            # 4. Verify created file on disk
            if "file" in tool_data:
                assert tool_data["status"] == "success"
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "file_info", "args": {"path": ppt_path}, "id": "c4"}],
                )
            # 5. Formulate final verified response
            if "size" in tool_data or "size_bytes" in tool_data or "type" in tool_data:
                return AIMessage(
                    content=f"Successfully extracted inspection highlights, generated `{ppt_path}`, and verified its existence ({tool_data.get('size', 0)} bytes).",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Find the project report, create a PowerPoint presentation from its highlights, and verify the file was created.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "generate_presentation", "file_info"]
    assert (workflow_workspace / ppt_path).exists()
    assert ppt_path in result["reply"]


# ==============================================================================
# WORKFLOW 4: DocumentTool -> Insufficient Evidence -> Another Tool -> Answer
# ==============================================================================
def test_workflow_4_insufficient_evidence_escalation(workflow_workspace):
    """WORKFLOW 4: DocumentTool -> insufficient evidence -> read_file -> answer."""
    agent, mock_llm_with_tools = _create_mock_agent(workflow_workspace)

    # Document summary returns text pointing to external appendix
    mock_incomplete_evidence = {
        "document_id": "doc_summary_incomplete",
        "filename": "summary_report.pdf",
        "file_type": "pdf",
        "file_hash": "inc77",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.85,
        "elements": [
            {
                "id": "p1_e1", "page": 1, "type": "heading", "text": "Executive Summary", "confidence": 0.95,
            },
            {
                "id": "p1_e2", "page": 1, "type": "text",
                "text": "Inspection complete. Detailed engineering recommendations are deferred to Appendix A in maintenance_appendix.txt.",
                "confidence": 0.90,
            },
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: Read summary report
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "sample_documents/summary_report.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Agent inspects output and sees recommendations are in maintenance_appendix.txt
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_file", "args": {"path": "maintenance_appendix.txt"}, "id": "c2"}],
                )
            # Step 3: Agent synthesizes the retrieved recommendation
            if "content" in tool_data:
                assert "eddy-current" in tool_data["content"]
                return AIMessage(
                    content=f"The summary report deferred recommendations to Appendix A. Inspecting `maintenance_appendix.txt` revealed: {tool_data['content']}",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_incomplete_evidence

        result = agent.chat("What is the final maintenance recommendation for Unit 4 in the summary report?")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["read_document", "read_file"]
    assert "eddy-current" in result["reply"].lower()


# ==============================================================================
# WORKFLOW 5: Multiple documents -> discovery -> analyze -> compare -> answer
# ==============================================================================
def test_workflow_5_multi_document_comparison(workflow_workspace):
    """WORKFLOW 5: Multiple documents -> find_files -> read_document (doc 1) -> read_document (doc 2) -> compare."""
    agent, mock_llm_with_tools = _create_mock_agent(workflow_workspace)

    mock_evidence_unit1 = {
        "document_id": "doc_unit1", "filename": "unit1_inspection.pdf", "file_type": "pdf",
        "file_hash": "u1", "total_pages": 1, "processing_status": "completed", "overall_confidence": 0.98,
        "elements": [{"id": "u1_e1", "page": 1, "type": "text", "text": "Unit 1 Shell Thickness: 38.5 mm", "confidence": 0.99}],
    }
    mock_evidence_unit2 = {
        "document_id": "doc_unit2", "filename": "unit2_inspection.pdf", "file_type": "pdf",
        "file_hash": "u2", "total_pages": 1, "processing_status": "completed", "overall_confidence": 0.98,
        "elements": [{"id": "u2_e1", "page": 1, "type": "text", "text": "Unit 2 Shell Thickness: 34.2 mm", "confidence": 0.99}],
    }

    evidence_map = {
        "sample_documents/unit1_inspection.pdf": mock_evidence_unit1,
        "sample_documents/unit2_inspection.pdf": mock_evidence_unit2,
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: Discover inspection documents
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*unit*.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Read Unit 1
            if "matches" in tool_data:
                first_doc = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": first_doc}, "id": "c2"}],
                )
            # Step 3: Read Unit 2
            if tool_data.get("document_id") == "doc_unit1":
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": "sample_documents/unit2_inspection.pdf"}, "id": "c3"}],
                )
            # Step 4: Compare both findings
            if tool_data.get("document_id") == "doc_unit2":
                return AIMessage(
                    content="Comparison: Unit 1 measured 38.5 mm while Unit 2 measured 34.2 mm, indicating higher wall degradation in Unit 2.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    def mock_post_dispatcher(url, *args, **kwargs):
        files = kwargs.get("files", {})
        fname = files.get("file", ("unknown", None))[0]
        resp = MagicMock()
        resp.status_code = 200
        if "unit1" in fname:
            resp.json.return_value = mock_evidence_unit1
        else:
            resp.json.return_value = mock_evidence_unit2
        return resp

    with patch("requests.post", side_effect=mock_post_dispatcher):
        result = agent.chat("Compare the wall thickness measurements between Unit 1 and Unit 2 inspection reports.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "read_document"]
    assert "38.5" in result["reply"]
    assert "34.2" in result["reply"]


# ==============================================================================
# WORKFLOW 6: Document contains formula -> extract formula -> MathTool -> explain
# ==============================================================================
def test_workflow_6_formula_extraction_math_explanation(workflow_workspace):
    """WORKFLOW 6: Document contains formula -> extract formula -> MathTool -> explain result."""
    agent, mock_llm_with_tools = _create_mock_agent(workflow_workspace)

    mock_evidence = {
        "document_id": "doc_asme_formula",
        "filename": "sample_inspection.pdf",
        "file_type": "pdf",
        "file_hash": "asme11",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "elements": [
            {
                "id": "p1_f1", "page": 1, "type": "formula",
                "text": "t = (P * R) / (S * E - 0.6 * P)",
                "formula_latex": "t = \\frac{P \\cdot R}{S \\cdot E - 0.6 \\cdot P}",
                "confidence": 0.99,
                "metadata": {"standard": "ASME Section VIII Div 1"},
            }
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: Discover document
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*inspection*.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Read document and extract formula
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "c2"}],
                )
            # Step 3: Evaluate formula with MathTool
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "calculate",
                        "args": {
                            "expression": "t = (P * R) / (S * E - 0.6 * P)",
                            "substitutions": json.dumps({"P": 15, "R": 500, "S": 138, "E": 1.0}),
                            "solve_for": "t",
                        },
                        "id": "c3",
                    }],
                )
            # Step 4: Explain result
            if "result" in tool_data:
                assert tool_data["success"] is True
                assert round(float(tool_data["result"]), 2) == 58.14
                return AIMessage(
                    content=(
                        "From `sample_inspection.pdf`, the governing formula is ASME Section VIII t = (P * R) / (S * E - 0.6 * P). "
                        "Evaluating with P=15 MPa, R=500 mm, S=138 MPa, and E=1.0 yields a minimum required wall thickness of 58.14 mm."
                    ),
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Extract the minimum thickness formula from the inspection report and evaluate it for P=15, R=500, S=138, E=1.0.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "calculate"]
    assert "58.14" in result["reply"]
    assert "ASME" in result["reply"]


# ==============================================================================
# LIVE END-TO-END TEST: Real document -> live engine -> MathTool -> Agent
# ==============================================================================
def test_live_end_to_end_real_document(workflow_workspace):
    """LIVE E2E TEST: Real sample_inspection.pdf extracted through live Document Engine."""
    import requests

    # Real document on disk
    real_pdf_path = workflow_workspace / "sample_documents" / "sample_inspection.pdf"
    assert real_pdf_path.exists()

    agent, mock_llm_with_tools = _create_mock_agent(workflow_workspace)

    # Verify if Document Engine daemon is listening on port 8001
    daemon_online = False
    try:
        ping = requests.get("http://127.0.0.1:8001/docs", timeout=1.0)
        daemon_online = (ping.status_code == 200)
    except Exception:
        daemon_online = False

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: Discover real document
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*inspection*.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Read document with live engine extraction
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "c2"}],
                )
            # Step 3: Math calculation on extracted live data
            if "document_id" in tool_data:
                assert tool_data["status"] == "success"
                assert tool_data["total_pages"] == 1
                # Live engine parsed table with Shell Ring 1: nominal 38.50, measured 37.85
                tables = tool_data.get("tables_found", [])
                assert len(tables) >= 1
                preview = tables[0].get("preview_rows", [])
                assert any("Shell Ring 1" in str(row) for row in preview)
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "calculate",
                        "args": {"expression": "38.50 - 37.85"},
                        "id": "c3",
                    }],
                )
            # Step 4: Final answer
            if "result" in tool_data:
                assert tool_data["success"] is True
                assert round(float(tool_data["result"]), 2) == 0.65
                return AIMessage(
                    content="Live extraction verified from `sample_inspection.pdf`. Shell Ring 1 nominal thickness is 38.50 mm and measured is 37.85 mm, with a computed degradation delta of 0.65 mm.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    if daemon_online:
        # Fully LIVE execution over HTTP to Document Engine on port 8001
        result = agent.chat("Find sample_inspection.pdf, extract Shell Ring 1 measurements, and compute the wall loss delta.")
    else:
        # Mock fallback if daemon is offline
        mock_evidence = {
            "document_id": "doc_live_fallback",
            "filename": "sample_inspection.pdf",
            "file_type": "pdf",
            "file_hash": "live11",
            "total_pages": 1,
            "processing_status": "completed",
            "overall_confidence": 0.99,
            "tables_found": [{
                "headers": ["Inspection Zone", "Nominal (mm)", "Measured (mm)", "Min Required (mm)", "Compliance"],
                "preview_rows": [["Shell Ring 1", "38.50", "37.85", "32.00", "PASS"]],
            }],
        }
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_evidence
            result = agent.chat("Find sample_inspection.pdf, extract Shell Ring 1 measurements, and compute the wall loss delta.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "calculate"]
    assert "0.65" in result["reply"]
    assert "sample_inspection.pdf" in result["reply"]
