"""Comprehensive Agent Orchestration and Tool Selection Test Suite.

Verifies the 10 exact user scenarios and core orchestration invariants:
1. "Hello" -> ordinary question -> no tool
2. "What is 2+2?" -> math question -> deterministic MathTool (calculate)
3. "What files are in my workspace?" -> workspace question -> workspace/file tool (list_files)
4. "What is in the BloodLink presentation?" -> document question -> workspace discovery -> DocumentTool
5. "What technologies does BloodLink use?" -> document question -> workspace discovery -> DocumentTool
6. "Read the CSR PDF and tell me the total expenditure." -> document question -> DocumentTool
7. "Read the spreadsheet and calculate the growth." -> document + math -> DocumentTool -> MathTool
8. "Read the report and create a PowerPoint." -> document + action -> DocumentTool -> action tool
9. "Explain this formula from the document." -> document question -> DocumentTool -> reasoning
10. "Find the document and then answer a question about it." -> workspace discovery -> DocumentTool

Also verifies architectural invariants:
- Ensure the LLM receives prior ToolMessages before deciding the next action.
- Ensure tool results are available to subsequent reasoning iterations.
- Ensure Agent does not stop after the first tool call when another tool is logically required.
- Preserve existing maximum iteration behavior (MAX_TOOL_ITERATIONS = 6).
- Prevent unnecessary repeated tool calls.
- Prevent unnecessary DocumentTool calls.
- Preserve user intent across tool calls.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent import CodingAgent
from app.tools.manager import ToolManager


@pytest.fixture
def orchestration_workspace():
    """Create a populated temporary workspace for testing orchestration workflows."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum_orchestration_"))
    
    # 1. Plain workspace files
    (temp_dir / "main.py").write_text("print('Sanctum initialized')\n", encoding="utf-8")
    (temp_dir / "notes.txt").write_text("Project roadmap and goals\n", encoding="utf-8")
    
    # 2. Sample presentations, PDFs, and spreadsheets
    docs_dir = temp_dir / "sample_documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # BloodLink presentation
    (docs_dir / "BLOODLINK.pptx").write_bytes(b"PK\x03\x04mock_bloodlink_presentation")
    # CSR report PDF
    (docs_dir / "csr_report.pdf").write_bytes(b"%PDF-1.4 mock csr report")
    # Financial spreadsheet
    (docs_dir / "financials.xlsx").write_bytes(b"PK\x03\x04mock_financials_spreadsheet")
    # Technical report with formula
    (docs_dir / "technical_report.pdf").write_bytes(b"%PDF-1.4 mock technical report")

    generated_dir = temp_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def _create_mock_agent(workspace_dir: Path):
    """Helper to create a CodingAgent with a mock LLM manager attached to workspace_dir."""
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
# SCENARIO 1: "Hello" -> ordinary question -> no tool
# ==============================================================================
def test_scenario_1_ordinary_conversation(orchestration_workspace):
    """Scenario 1: 'Hello' -> no tool calls. Direct conversational reply."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_llm_with_tools.invoke.return_value = AIMessage(
        content="Hello! I'm Sanctum, your AI coding and document assistant. How can I help you today?",
        tool_calls=[],
    )

    result = agent.chat("Hello")

    # Verify tool sequence: strictly empty
    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == [], f"Expected no tools, got {actual_tool_sequence}"
    assert "Hello" in result["reply"] or "Sanctum" in result["reply"]
    assert mock_llm_with_tools.invoke.call_count == 1


# ==============================================================================
# SCENARIO 2: "What is 2+2?" -> math question -> deterministic MathTool
# ==============================================================================
def test_scenario_2_pure_math_sympy(orchestration_workspace):
    """Scenario 2: 'What is 2+2?' -> calculate (deterministic SymPy)."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "calculate", "args": {"expression": "2 + 2"}, "id": "call_math_1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_output = json.loads(last_msg.content)
            assert tool_output.get("status") == "success"
            assert str(tool_output.get("result")) == "4"
            return AIMessage(content="2 + 2 equals 4.", tool_calls=[])
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("What is 2+2?")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["calculate"], f"Expected ['calculate'], got {actual_tool_sequence}"
    assert result["tool_actions"][0]["args"]["expression"] == "2 + 2"
    calc_res = json.loads(result["tool_actions"][0]["result"])
    assert calc_res["status"] == "success"
    assert str(calc_res["result"]) == "4"
    assert "4" in result["reply"]


# ==============================================================================
# SCENARIO 3: "What files are in my workspace?" -> workspace question -> workspace tool
# ==============================================================================
def test_scenario_3_workspace_question(orchestration_workspace):
    """Scenario 3: 'What files are in my workspace?' -> list_files."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "list_files", "args": {"path": "."}, "id": "call_ws_1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_output = json.loads(last_msg.content)
            assert "items" in tool_output
            return AIMessage(content="The workspace contains: main.py, notes.txt, sample_documents/", tool_calls=[])
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("What files are in my workspace?")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence in (["list_files"], ["workspace_tree"]), f"Unexpected sequence: {actual_tool_sequence}"
    assert not any(action["tool"] == "read_document" for action in result["tool_actions"])
    assert "main.py" in result["reply"]


# ==============================================================================
# SCENARIO 4: "What is in the BloodLink presentation?" -> discovery -> DocumentTool
# ==============================================================================
def test_scenario_4_bloodlink_presentation(orchestration_workspace):
    """Scenario 4: 'What is in the BloodLink presentation?' -> find_files -> read_document."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_engine_evidence = {
        "document_id": "doc_bloodlink_123",
        "filename": "BLOODLINK.pptx",
        "file_type": "pptx",
        "file_hash": "a1b2c3d4",
        "total_pages": 5,
        "processing_status": "completed",
        "overall_confidence": 0.95,
        "elements": [
            {
                "id": "s1_t1", "page": 1, "type": "title", "text": "BloodLink - Emergency Blood Donation Platform",
                "confidence": 0.98, "bounding_box": [10, 10, 200, 50],
            },
            {
                "id": "s2_t1", "page": 2, "type": "text", "text": "Problem Statement: Blood shortages during emergencies.",
                "confidence": 0.96, "bounding_box": [20, 20, 300, 100],
            },
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Iteration 1: discover file
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*bloodlink*"}, "id": "call_find_1"}],
            )
        # Subsequent iterations: inspect ToolMessage
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                matched_path = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": matched_path, "mode": "summary"}, "id": "call_doc_1"}],
                )
            if "document_id" in tool_data:
                assert tool_data["document_id"] == "doc_bloodlink_123"
                return AIMessage(
                    content="The BloodLink presentation describes an emergency blood donation platform solving blood shortages (Slide 1, Slide 2).",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_evidence

        result = agent.chat("What is in the BloodLink presentation?")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document"], f"Expected ['find_files', 'read_document'], got {actual_tool_sequence}"
    assert "BloodLink" in result["reply"]
    assert "Slide" in result["reply"] or "emergency" in result["reply"].lower()


# ==============================================================================
# SCENARIO 5: "What technologies does BloodLink use?" -> discovery -> DocumentTool
# ==============================================================================
def test_scenario_5_bloodlink_technologies(orchestration_workspace):
    """Scenario 5: 'What technologies does BloodLink use?' -> find_files -> read_document."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_engine_evidence = {
        "document_id": "doc_bloodlink_tech",
        "filename": "BLOODLINK.pptx",
        "file_type": "pptx",
        "file_hash": "e5f6g7h8",
        "total_pages": 4,
        "processing_status": "completed",
        "overall_confidence": 0.94,
        "elements": [
            {
                "id": "s3_t1", "page": 3, "type": "text",
                "text": "Tech Stack: Flutter mobile client, Firebase Authentication, Node.js backend, Google Maps API.",
                "confidence": 0.96, "bounding_box": [30, 40, 400, 120],
            },
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*bloodlink*"}, "id": "call_find_tech"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "call_doc_tech"}],
                )
            if "document_id" in tool_data:
                return AIMessage(
                    content="Based on Slide 3 of the BloodLink presentation, it uses Flutter, Firebase, Node.js, and Google Maps API.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_evidence

        result = agent.chat("What technologies does BloodLink use?")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document"]
    assert "Flutter" in result["reply"]
    assert "Firebase" in result["reply"]


# ==============================================================================
# SCENARIO 6: "Read the CSR PDF and tell me the total expenditure." -> discovery -> DocumentTool
# ==============================================================================
def test_scenario_6_csr_pdf_expenditure(orchestration_workspace):
    """Scenario 6: 'Read the CSR PDF and tell me the total expenditure.' -> find_files -> read_document."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_engine_evidence = {
        "document_id": "doc_csr_exp",
        "filename": "csr_report.pdf",
        "file_type": "pdf",
        "file_hash": "csr123",
        "total_pages": 3,
        "processing_status": "completed",
        "overall_confidence": 0.92,
        "elements": [
            {
                "id": "p2_tbl1", "page": 2, "type": "table",
                "table_data": [
                    ["Project", "Expenditure (INR)"],
                    ["Rural Education", "4,500,000"],
                    ["Healthcare Outreach", "3,200,000"],
                    ["Total CSR Expenditure", "7,700,000"],
                ],
                "confidence": 0.95,
            }
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*csr*.pdf"}, "id": "call_find_csr"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "call_doc_csr"}],
                )
            if "document_id" in tool_data:
                return AIMessage(
                    content="According to Page 2 Table 1 of the CSR report, the total expenditure is INR 7,700,000.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_evidence

        result = agent.chat("Read the CSR PDF and tell me the total expenditure.")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document"]
    assert "7,700,000" in result["reply"]


# ==============================================================================
# SCENARIO 7: "Read the spreadsheet and calculate the growth." -> DocumentTool -> MathTool
# ==============================================================================
def test_scenario_7_spreadsheet_calculate_growth(orchestration_workspace):
    """Scenario 7: 'Read the spreadsheet and calculate the growth.' -> find_files -> read_document -> calculate."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_engine_evidence = {
        "document_id": "doc_fin_sheet",
        "filename": "financials.xlsx",
        "file_type": "xlsx",
        "file_hash": "fin9988",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "elements": [
            {
                "id": "p1_tbl1", "page": 1, "type": "table",
                "table_data": [
                    ["Year", "Revenue"],
                    ["2023", "100000"],
                    ["2024", "125000"],
                ],
                "confidence": 0.99,
            }
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Iteration 1: locate spreadsheet
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*financials*.xlsx"}, "id": "call_find_fin"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Iteration 2: after find_files, read document
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "call_doc_fin"}],
                )
            # Iteration 3: after read_document, calculate with SymPy
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "calculate", "args": {"expression": "(125000 - 100000) / 100000 * 100"}, "id": "call_calc_growth"}],
                )
            # Iteration 4: after calculate, formulate final answer
            if "result" in tool_data:
                assert float(tool_data["result"]) == 25.0
                return AIMessage(
                    content="From the spreadsheet, Revenue 2023 was 100,000 and Revenue 2024 was 125,000. SymPy computed a growth rate of 25.0%.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_evidence

        result = agent.chat("Read the spreadsheet and calculate the growth.")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "calculate"], f"Expected discovery -> doc -> math, got {actual_tool_sequence}"
    assert "25" in result["reply"]


# ==============================================================================
# SCENARIO 8: "Read the report and create a PowerPoint." -> DocumentTool -> action tool
# ==============================================================================
def test_scenario_8_report_create_presentation(orchestration_workspace):
    """Scenario 8: 'Read the report and create a PowerPoint.' -> find_files -> read_document -> generate_presentation."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_engine_evidence = {
        "document_id": "doc_report_ppt",
        "filename": "csr_report.pdf",
        "file_type": "pdf",
        "file_hash": "rep77",
        "total_pages": 2,
        "processing_status": "completed",
        "overall_confidence": 0.95,
        "elements": [
            {
                "id": "p1_t1", "page": 1, "type": "title", "text": "Annual CSR Sustainability Report",
                "confidence": 0.98,
            },
            {
                "id": "p1_t2", "page": 1, "type": "text", "text": "Key Highlights: 15,000 beneficiaries across 40 villages.",
                "confidence": 0.95,
            },
        ],
    }

    slides_payload = [
        {"title": "Annual CSR Report", "subtitle": "Executive Overview", "bullet_points": ["Sustainability highlights", "Rural outreach"]},
        {"title": "Key Impact", "bullet_points": ["15,000 beneficiaries", "40 villages covered"]},
    ]

    def side_effect(messages):
        last_msg = messages[-1]
        # Iteration 1: locate report
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*csr*.pdf"}, "id": "call_find_rep"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Iteration 2: read document
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "call_doc_rep"}],
                )
            # Iteration 3: generate PowerPoint presentation
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "generate_presentation",
                        "args": {
                            "filepath": "generated/csr_summary.pptx",
                            "title": "CSR Report Highlights",
                            "subtitle": "Generated Presentation",
                            "slides_json": json.dumps(slides_payload),
                        },
                        "id": "call_gen_ppt",
                    }],
                )
            # Iteration 4: final answer confirming generation
            if "file" in tool_data:
                return AIMessage(
                    content="I read the CSR report and generated a presentation at `generated/csr_summary.pptx` with 2 slides.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_evidence

        result = agent.chat("Read the report and create a PowerPoint.")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "generate_presentation"]
    assert (orchestration_workspace / "generated" / "csr_summary.pptx").exists()
    assert "csr_summary.pptx" in result["reply"]


# ==============================================================================
# SCENARIO 9: "Explain this formula from the document." -> DocumentTool -> reasoning
# ==============================================================================
def test_scenario_9_explain_formula_from_document(orchestration_workspace):
    """Scenario 9: 'Explain this formula from the document.' -> find_files -> read_document -> reasoning."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_engine_evidence = {
        "document_id": "doc_tech_formula",
        "filename": "technical_report.pdf",
        "file_type": "pdf",
        "file_hash": "form99",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.93,
        "elements": [
            {
                "id": "p1_form1", "page": 1, "type": "formula",
                "text": "P = \\rho \\cdot g \\cdot h",
                "confidence": 0.96,
                "metadata": {"latex": "P = \\rho \\cdot g \\cdot h", "domain": "hydrostatics"},
            },
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*technical*.pdf"}, "id": "call_find_tech"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "call_doc_tech"}],
                )
            if "document_id" in tool_data:
                return AIMessage(
                    content=(
                        "From Page 1 of `technical_report.pdf`, the formula extracted is P = rho * g * h. "
                        "This is the hydrostatic pressure formula, where P is pressure, rho is fluid density, "
                        "g is gravitational acceleration, and h is the height/depth of the fluid column."
                    ),
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_evidence

        result = agent.chat("Explain this formula from the document.")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document"]
    assert "hydrostatic" in result["reply"].lower() or "pressure" in result["reply"].lower()
    # SymPy calculate was NOT needed since only explanation was requested
    assert "calculate" not in actual_tool_sequence


# ==============================================================================
# SCENARIO 10: "Find the document and then answer a question about it."
# ==============================================================================
def test_scenario_10_find_document_and_answer(orchestration_workspace):
    """Scenario 10: 'Find the document and then answer a question about it.' -> find_files -> read_document."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    mock_engine_evidence = {
        "document_id": "doc_general_find",
        "filename": "csr_report.pdf",
        "file_type": "pdf",
        "file_hash": "csr4455",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.95,
        "elements": [
            {
                "id": "p1_e1", "page": 1, "type": "text",
                "text": "The project was launched in May 2022 across the Southern District.",
                "confidence": 0.97,
            },
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*.pdf"}, "id": "call_f1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "call_d1"}],
                )
            if "document_id" in tool_data:
                return AIMessage(
                    content="The document indicates that the project was launched in May 2022 in the Southern District.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_engine_evidence

        result = agent.chat("Find the document and then answer a question about it.")

    actual_tool_sequence = [action["tool"] for action in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document"]
    assert "May 2022" in result["reply"]


# ==============================================================================
# ARCHITECTURAL INVARIANT TESTS
# ==============================================================================
def test_prevent_unnecessary_repeated_tool_calls(orchestration_workspace):
    """Verify that redundant identical tool calls are intercepted and cached."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "calculate", "args": {"expression": "10 * 5"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            if len([m for m in messages if isinstance(m, ToolMessage)]) == 1:
                # Re-call calculate with identical args
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "calculate", "args": {"expression": "10 * 5"}, "id": "c2"}],
                )
            return AIMessage(content="Final answer is 50.", tool_calls=[])
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("Calculate 10 * 5")
    # Verify second tool action was intercepted with already_executed notice
    assert len(result["tool_actions"]) == 2
    first_res = json.loads(result["tool_actions"][0]["result"])
    second_res = json.loads(result["tool_actions"][1]["result"])
    assert first_res["result"] == 50
    assert second_res["status"] == "already_executed"
    assert "Avoid repeated calls" in second_res["message"]


def test_tool_messages_passed_to_subsequent_iterations(orchestration_workspace):
    """Verify that prior ToolMessages are delivered in `messages` to the LLM."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    history_snapshots = []

    def side_effect(messages):
        history_snapshots.append(list(messages))
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "calculate", "args": {"expression": "3 * 3"}, "id": "c_mult"}],
            )
        return AIMessage(content="Result is 9.", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    agent.chat("Compute 3 * 3")

    # In iteration 2, the LLM must have received the ToolMessage
    assert len(history_snapshots) >= 2
    iter2_messages = history_snapshots[1]
    tool_msgs = [m for m in iter2_messages if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "c_mult"
    assert "9" in tool_msgs[0].content


def test_preserve_max_iterations(orchestration_workspace):
    """Verify MAX_TOOL_ITERATIONS remains 6."""
    agent, _ = _create_mock_agent(orchestration_workspace)
    assert agent.MAX_TOOL_ITERATIONS == 6


def test_prevent_unnecessary_document_tool_calls(orchestration_workspace):
    """Verify that math, greetings, and workspace listing requests never invoke read_document."""
    agent, mock_llm_with_tools = _create_mock_agent(orchestration_workspace)

    # Greeting
    mock_llm_with_tools.invoke.return_value = AIMessage(content="Hi!", tool_calls=[])
    res_greet = agent.chat("Hi")
    assert not any(a["tool"] == "read_document" for a in res_greet["tool_actions"])

    # Pure math
    mock_llm_with_tools.invoke.side_effect = [
        AIMessage(content="", tool_calls=[{"name": "calculate", "args": {"expression": "7 * 8"}, "id": "m1"}]),
        AIMessage(content="56", tool_calls=[]),
    ]
    res_math = agent.chat("7 * 8")
    assert [a["tool"] for a in res_math["tool_actions"]] == ["calculate"]
    assert not any(a["tool"] == "read_document" for a in res_math["tool_actions"])
