"""Phase 8 Integration Test Suite: Document Analysis -> Action Execution.

Verifies end-to-end integration of Document Engine analysis with existing action/generation tools:
- Excel (XLSX) -> PowerPoint summary (generate_presentation)
- PDF -> Word summary document (generate_word_document)
- PPTX -> Markdown structured note (generate_structured_note)
- XLSX -> Deterministic calculations (calculate / SymPy) -> Presentation (generate_presentation)
- CSV -> Analysis -> Excel workbook (generate_excel_sheet)
- Action failure -> Accurate error reporting without false success claims
- Missing output file on disk -> Detected and reported as failure
- Live E2E test against running Document Engine daemon on port 8001

Invariants verified:
- Document Engine handles DOCUMENT ANALYSIS.
- Existing tools handle ACTION/GENERATION.
- Agent handles REASONING/ORCHESTRATION.
- Responsibilities are strictly separated.
- Before claiming output was created: verify action result, verify file existence, preserve output path.
- Failure is reported accurately without fabricating success.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from openpyxl import load_workbook
from pptx import Presentation
from docx import Document

from app.agent import CodingAgent
from app.tools.manager import ToolManager


@pytest.fixture
def action_workspace():
    """Create an isolated workspace populated with documents for Phase 8 action tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum_phase8_ws_"))

    docs_dir = temp_dir / "sample_documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy real sample documents from engine if present
    engine_samples = Path(__file__).resolve().parent.parent.parent / "sanctum-file-engine-code" / "sample_documents"
    if engine_samples.exists():
        for item in engine_samples.iterdir():
            if item.is_file() and item.suffix in (".pdf", ".pptx", ".txt"):
                shutil.copy(item, docs_dir / item.name)

    # Fallbacks if not present
    if not (docs_dir / "sample_inspection.pdf").exists():
        (docs_dir / "sample_inspection.pdf").write_bytes(b"%PDF-1.4 mock inspection pdf")
    if not (docs_dir / "BLOODLINK.pptx").exists():
        (docs_dir / "BLOODLINK.pptx").write_bytes(b"PK\x03\x04mock bloodlink pptx")

    # Sample XLSX file
    (docs_dir / "quarterly_report.xlsx").write_bytes(b"PK\x03\x04mock quarterly report xlsx")

    # Sample CSV file
    csv_file = docs_dir / "telemetry_data.csv"
    csv_file.write_text(
        "Timestamp,Temperature_C,Pressure_Bar,Status\n"
        "2024-01-01T00:00:00,72.4,15.2,NORMAL\n"
        "2024-01-01T01:00:00,74.1,15.8,NORMAL\n"
        "2024-01-01T02:00:00,81.5,18.4,WARNING\n",
        encoding="utf-8",
    )

    generated_dir = temp_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def _create_agent(workspace_dir: Path):
    """Helper to initialize CodingAgent with mock LLM for deterministic orchestration."""
    mock_llm_manager = MagicMock()
    mock_llm_manager.model_name = "test-model-orchestrator"
    mock_llm = MagicMock()
    mock_llm_manager._llm = mock_llm

    mock_llm_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm_with_tools

    tool_manager = ToolManager(root_dir=workspace_dir)
    agent = CodingAgent(mock_llm_manager, tool_manager=tool_manager)
    agent.clear_memory()
    return agent, mock_llm_with_tools


# ==============================================================================
# 1. Excel (XLSX) -> PowerPoint summary (generate_presentation)
# ==============================================================================
def test_excel_report_to_pptx_summary(action_workspace):
    """Read an Excel report, inspect evidence, generate a PowerPoint summary, and verify output."""
    agent, mock_llm_with_tools = _create_agent(action_workspace)

    mock_evidence = {
        "document_id": "doc_excel_fin",
        "filename": "quarterly_report.xlsx",
        "file_type": "xlsx",
        "file_hash": "hash_xlsx_01",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "elements": [
            {
                "id": "p1_tbl1", "page": 1, "type": "table",
                "table_data": [
                    ["Metric", "Q1 Actual", "Q2 Actual", "YoY Target"],
                    ["Revenue ($M)", "120.5", "145.2", "140.0"],
                    ["Operating Margin", "18.2%", "21.5%", "20.0%"],
                    ["Active Subscriptions", "45000", "52000", "50000"],
                ],
                "confidence": 0.99,
            }
        ],
    }

    pptx_path = "generated/financial_performance_summary.pptx"
    slides = [
        {
            "title": "Executive Financial Highlights",
            "cards": [
                {"title": "Q2 Revenue", "text": "$145.2M (+20.5% YoY, surpassing target of $140M)"},
                {"title": "Operating Margin", "text": "Expanded to 21.5% from 18.2% in Q1"},
            ],
        },
        {
            "title": "Subscriber Growth",
            "bullet_points": [
                "Active subscriptions reached 52,000 (beat target of 50,000)",
                "Net subscriber additions accelerated across enterprise accounts",
            ],
        },
    ]

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*quarterly*"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 1: Discovered file -> call read_document
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target, "mode": "table"}, "id": "c2"}],
                )
            # Step 2: Inspected table -> generate presentation
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "generate_presentation",
                        "args": {
                            "filepath": pptx_path,
                            "title": "Quarterly Performance Overview",
                            "subtitle": "Q2 Financial Summary & Subscriptions",
                            "slides_json": json.dumps(slides),
                        },
                        "id": "c3",
                    }],
                )
            # Step 3: Action completed -> agent inspects action result
            if "file" in tool_data and tool_data.get("format") == "pptx":
                assert tool_data["status"] == "success"
                assert tool_data["file_exists"] is True
                assert tool_data["size_bytes"] > 0
                return AIMessage(
                    content=f"Successfully analyzed `quarterly_report.xlsx` and generated the PowerPoint presentation `{pptx_path}` ({tool_data['size_bytes']} bytes).",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Read the quarterly Excel report and create a PowerPoint summary.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "generate_presentation"]
    
    # Verify file physically exists on disk and is a valid PPTX
    out_file = action_workspace / pptx_path
    assert out_file.exists()
    prs = Presentation(str(out_file))
    assert len(prs.slides) == 3  # cover slide + 2 content slides
    assert pptx_path in result["reply"]


# ==============================================================================
# 2. PDF -> Word summary document (generate_word_document)
# ==============================================================================
def test_pdf_to_summary_document(action_workspace):
    """Read a PDF inspection report, extract findings, generate a Word document, and verify output."""
    agent, mock_llm_with_tools = _create_agent(action_workspace)

    mock_evidence = {
        "document_id": "doc_pdf_vessel",
        "filename": "sample_inspection.pdf",
        "file_type": "pdf",
        "file_hash": "hash_pdf_insp",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.97,
        "elements": [
            {
                "id": "p1_e1", "page": 1, "type": "title",
                "text": "Pressure Vessel Ultrasonic Thickness Inspection Report",
                "confidence": 0.99,
            },
            {
                "id": "p1_e2", "page": 1, "type": "text",
                "text": "Component: Shell Ring 1. Minimum measured thickness: 0.485 in. Allowable minimum: 0.450 in. Status: Compliant.",
                "confidence": 0.98,
            },
            {
                "id": "p1_e3", "page": 1, "type": "text",
                "text": "Recommendation: Continue routine monitoring. Next scheduled ultrasonic test in 24 months.",
                "confidence": 0.96,
            },
        ],
    }

    docx_path = "generated/vessel_inspection_summary.docx"
    sections = [
        {
            "heading": "Executive Summary",
            "content": "Ultrasonic thickness measurement of Shell Ring 1 confirmed mechanical compliance under ASME Section VIII standards.",
            "callout": "Component Status: COMPLIANT (0.485 in measured vs 0.450 in minimum required).",
        },
        {
            "heading": "Inspection Details",
            "table": {
                "headers": ["Component", "Measured Thickness", "Allowable Minimum", "Condition"],
                "rows": [["Shell Ring 1", "0.485 in", "0.450 in", "Pass"]],
            },
        },
        {
            "heading": "Maintenance Action Plan",
            "content": "Continue routine operation. Re-inspect ultrasonic thickness within 24 months.",
        },
    ]

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*inspection*.pdf"}, "id": "c1"}],
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
                    content="",
                    tool_calls=[{
                        "name": "generate_word_document",
                        "args": {
                            "filepath": docx_path,
                            "title": "Pressure Vessel Inspection Summary",
                            "subtitle": "Shell Ring 1 Assessment",
                            "sections_json": json.dumps(sections),
                        },
                        "id": "c3",
                    }],
                )
            if "file" in tool_data and tool_data.get("format") == "docx":
                assert tool_data["status"] == "success"
                assert tool_data["file_exists"] is True
                return AIMessage(
                    content=f"Generated executive Word summary at `{docx_path}` with {len(sections)} sections.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Read the inspection PDF and generate a Word document summary.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "generate_word_document"]

    out_file = action_workspace / docx_path
    assert out_file.exists()
    doc = Document(str(out_file))
    assert len(doc.tables) >= 1
    assert "Shell Ring 1" in doc.tables[0].rows[1].cells[0].text
    assert docx_path in result["reply"]


# ==============================================================================
# 3. PPTX -> Summary note (generate_structured_note)
# ==============================================================================
def test_pptx_to_summary_note(action_workspace):
    """Read a PPTX presentation, extract themes, generate a Markdown note, and verify output."""
    agent, mock_llm_with_tools = _create_agent(action_workspace)

    mock_evidence = {
        "document_id": "doc_pptx_bloodlink",
        "filename": "BLOODLINK.pptx",
        "file_type": "pptx",
        "file_hash": "hash_pptx_bl",
        "total_pages": 4,
        "processing_status": "completed",
        "overall_confidence": 0.96,
        "elements": [
            {
                "id": "s1_e1", "slide": 1, "type": "title",
                "text": "BloodLink: Real-time Emergency Blood Donation Logistics",
                "confidence": 0.99,
            },
            {
                "id": "s2_e1", "slide": 2, "type": "text",
                "text": "Core Problem: Lack of real-time inventory synchronization across municipal blood banks.",
                "confidence": 0.97,
            },
            {
                "id": "s3_e1", "slide": 3, "type": "text",
                "text": "Proposed Solution: Automated dispatcher matching nearby voluntary donors within 15 minutes.",
                "confidence": 0.98,
            },
        ],
    }

    note_path = "generated/bloodlink_summary.md"
    sections = [
        {
            "heading": "Project Overview",
            "bullets": [
                "BloodLink is an emergency logistics network connecting municipal trauma centers with donors.",
                "Primary objective: reduce fulfillment latency to under 15 minutes.",
            ],
            "tasks": [
                "Review API specs for regional hospital integrations",
                "Evaluate HIPAA compliance requirements",
            ],
        },
        {
            "heading": "Key Problem & Solution",
            "bullets": [
                "Problem: Fragmented inventory across blood banks causes acute supply delays.",
                "Solution: Geospatial donor dispatch algorithms with SMS and push notifications.",
            ],
        },
    ]

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
                    content="",
                    tool_calls=[{
                        "name": "generate_structured_note",
                        "args": {
                            "filepath": note_path,
                            "title": "BloodLink Platform Summary",
                            "summary": "Overview of BloodLink real-time donor dispatch system",
                            "tags_csv": "healthcare,logistics,bloodlink",
                            "sections_json": json.dumps(sections),
                        },
                        "id": "c3",
                    }],
                )
            if "file" in tool_data and tool_data.get("format") == "md":
                assert tool_data["status"] == "success"
                assert tool_data["file_exists"] is True
                return AIMessage(
                    content=f"Created structured summary note at `{note_path}`.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Read the BloodLink presentation and create a structured summary note.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "generate_structured_note"]

    out_file = action_workspace / note_path
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "title: BloodLink Platform Summary" in content
    assert "healthcare, logistics, bloodlink" in content
    assert "- [ ] Review API specs" in content
    assert note_path in result["reply"]


# ==============================================================================
# 4. XLSX -> calculations (MathTool) -> presentation (generate_presentation)
# ==============================================================================
def test_xlsx_to_calculations_to_presentation(action_workspace):
    """Read XLSX, perform deterministic calculation via MathTool, and generate presentation."""
    agent, mock_llm_with_tools = _create_agent(action_workspace)

    mock_evidence = {
        "document_id": "doc_sales_data",
        "filename": "quarterly_report.xlsx",
        "file_type": "xlsx",
        "file_hash": "hash_xlsx_sales",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.99,
        "elements": [
            {
                "id": "p1_tbl_sales", "page": 1, "type": "table",
                "table_data": [
                    ["Division", "Gross Revenue", "Operating Cost"],
                    ["North America", "150000", "90000"],
                    ["Europe", "120000", "78000"],
                ],
                "confidence": 0.99,
            }
        ],
    }

    pptx_path = "generated/division_margins.pptx"

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*quarterly*"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 1: Discovered file -> read document table
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target, "mode": "table"}, "id": "c2"}],
                )
            # Step 2: Extracted revenue/cost -> call calculate for North America margin
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "calculate",
                        "args": {"expression": "(150000 - 90000) / 150000 * 100"},
                        "id": "c3",
                    }],
                )
            # Step 3: MathTool returns deterministic 40.0% -> generate presentation
            if "result" in tool_data and tool_data.get("deterministic") is True:
                assert float(tool_data["result"]) == 40.0
                margin_val = tool_data["result"]
                slides = [
                    {
                        "title": "North America Division Margins",
                        "cards": [
                            {"title": "Gross Revenue", "text": "$150,000"},
                            {"title": "Operating Margin", "text": f"{margin_val}% profit margin ($60,000 net profit)"},
                        ],
                    }
                ]
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "generate_presentation",
                        "args": {
                            "filepath": pptx_path,
                            "title": "Division Profitability Report",
                            "subtitle": "Calculated Operating Margins",
                            "slides_json": json.dumps(slides),
                        },
                        "id": "c4",
                    }],
                )
            # Step 4: Presentation generated -> finalize
            if "file" in tool_data and tool_data.get("format") == "pptx":
                assert tool_data["status"] == "success"
                return AIMessage(
                    content=f"Computed North America margin of 40.0% using MathTool and generated slide deck `{pptx_path}`.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Read the quarterly revenue and cost numbers, calculate North America margin, and build a presentation.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "calculate", "generate_presentation"]

    out_file = action_workspace / pptx_path
    assert out_file.exists()
    prs = Presentation(str(out_file))
    assert len(prs.slides) == 2
    assert "40" in result["reply"]
    assert pptx_path in result["reply"]


# ==============================================================================
# 5. CSV -> analysis -> output (generate_excel_sheet)
# ==============================================================================
def test_csv_analysis_to_excel_sheet(action_workspace):
    """Read CSV telemetry, analyze entries, generate styled Excel sheet, and verify output."""
    agent, mock_llm_with_tools = _create_agent(action_workspace)

    mock_evidence = {
        "document_id": "doc_csv_telemetry",
        "filename": "telemetry_data.csv",
        "file_type": "csv",
        "file_hash": "hash_csv_01",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.99,
        "elements": [
            {
                "id": "p1_tbl_csv", "page": 1, "type": "table",
                "table_data": [
                    ["Timestamp", "Temperature_C", "Pressure_Bar", "Status"],
                    ["2024-01-01T00:00:00", "72.4", "15.2", "NORMAL"],
                    ["2024-01-01T01:00:00", "74.1", "15.8", "NORMAL"],
                    ["2024-01-01T02:00:00", "81.5", "18.4", "WARNING"],
                ],
                "confidence": 0.99,
            }
        ],
    }

    excel_path = "generated/telemetry_analysis.xlsx"
    sheets = [
        {
            "title": "Cleaned Telemetry",
            "headers": ["Timestamp", "Temp (°C)", "Pressure (Bar)", "Status Alert"],
            "rows": [
                ["2024-01-01T00:00:00", 72.4, 15.2, "NORMAL"],
                ["2024-01-01T01:00:00", 74.1, 15.8, "NORMAL"],
                ["2024-01-01T02:00:00", 81.5, 18.4, "HIGH PRESSURE WARNING"],
            ],
            "totals_row": ["Averages / Max", 76.0, 18.4, "1 Alert"],
        }
    ]

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*telemetry*"}, "id": "c1"}],
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
                    content="",
                    tool_calls=[{
                        "name": "generate_excel_sheet",
                        "args": {
                            "filepath": excel_path,
                            "sheets_json": json.dumps(sheets),
                        },
                        "id": "c3",
                    }],
                )
            if "file" in tool_data and tool_data.get("format") == "xlsx":
                assert tool_data["status"] == "success"
                assert tool_data["file_exists"] is True
                return AIMessage(
                    content=f"Analyzed telemetry CSV and exported styled Excel workbook to `{excel_path}`.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Analyze telemetry_data.csv and create a styled Excel spreadsheet.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "generate_excel_sheet"]

    out_file = action_workspace / excel_path
    assert out_file.exists()
    wb = load_workbook(str(out_file))
    assert "Cleaned Telemetry" in wb.sheetnames
    sheet = wb["Cleaned Telemetry"]
    assert sheet["D4"].value == "HIGH PRESSURE WARNING"
    assert excel_path in result["reply"]


# ==============================================================================
# 6. Action Failure -> Accurate error reporting without false success claims
# ==============================================================================
def test_action_failure_reporting_accurately(action_workspace):
    """When action tool fails (e.g. malformed json or write error), agent reports failure accurately."""
    agent, mock_llm_with_tools = _create_agent(action_workspace)

    mock_evidence = {
        "document_id": "doc_sample_report",
        "filename": "sample_inspection.pdf",
        "file_type": "pdf",
        "elements": [{"id": "p1", "text": "Inspection complete"}],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "sample_documents/sample_inspection.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "document_id" in tool_data:
                # Call generate_presentation with invalid malformed JSON
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "generate_presentation",
                        "args": {
                            "filepath": "generated/broken.pptx",
                            "title": "Broken Deck",
                            "subtitle": "Error Test",
                            "slides_json": "INVALID_NOT_JSON",
                        },
                        "id": "c2",
                    }],
                )
            if "status" in tool_data and tool_data["status"] == "error":
                # Deliberate false claim attempt by model
                return AIMessage(
                    content="I successfully generated the presentation at generated/broken.pptx!",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Read the inspection PDF and generate broken.pptx.")

    # Guard must have detected the failure and prevented the false success claim
    reply_lower = result["reply"].lower()
    assert "failed" in reply_lower or "cannot claim success" in reply_lower or "error" in reply_lower
    assert not (action_workspace / "generated/broken.pptx").exists()


# ==============================================================================
# 7. Action File Not Found on Disk Treated as Failure
# ==============================================================================
def test_action_file_not_found_on_disk_treated_as_failure(action_workspace):
    """If action tool returns without physical file existing, agent detects missing file and flags failure."""
    agent, mock_llm_with_tools = _create_agent(action_workspace)

    ghost_file = "generated/ghost.pptx"

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "generate_presentation", "args": {
                    "filepath": ghost_file,
                    "title": "Ghost",
                    "subtitle": "None",
                    "slides_json": "[]",
                }, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            return AIMessage(
                content="I have created the presentation successfully at generated/ghost.pptx.",
                tool_calls=[],
            )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    # Mock generate_presentation to return success but NOT create file on disk
    with patch.object(agent.doc_generator, "generate_presentation", return_value=ghost_file):
        # Ensure file definitely doesn't exist
        ghost_path = action_workspace / ghost_file
        if ghost_path.exists():
            ghost_path.unlink()

        result = agent.chat(f"Create presentation at {ghost_file}.")

    reply_lower = result["reply"].lower()
    assert "failed" in reply_lower or "cannot claim success" in reply_lower or "not found on disk" in reply_lower


# ==============================================================================
# 8. Live E2E Integration: Real Document Analysis -> Presentation Action
# ==============================================================================
def test_live_e2e_document_analysis_to_presentation(action_workspace):
    """Live E2E test against running Document Engine daemon on port 8001.
    
    Uploads sample_inspection.pdf, gets real canonical DocumentEvidence,
    decides slide content, calls real python-pptx generator, and verifies output on disk.
    """
    import urllib.request

    # Check daemon availability
    daemon_available = False
    try:
        with urllib.request.urlopen("http://127.0.0.1:8001/docs", timeout=2) as resp:
            if resp.status == 200:
                daemon_available = True
    except Exception:
        daemon_available = False

    if not daemon_available:
        pytest.skip("Document Engine daemon is not running on port 8001")

    agent, mock_llm_with_tools = _create_agent(action_workspace)

    pptx_path = "generated/live_inspection_summary.pptx"

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*inspection*.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # 1. Discovered file -> read document through real live engine
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target, "mode": "summary"}, "id": "c2"}],
                )
            # 2. Live DocumentEvidence received -> extract real title & generate presentation
            if "document_id" in tool_data:
                assert tool_data.get("status") == "success"
                excerpts = tool_data.get("key_content_excerpts", [])
                title_text = tool_data.get("filename", "Inspection Document")
                if excerpts and excerpts[0].get("text"):
                    title_text = excerpts[0]["text"][:60]

                slides = [
                    {
                        "title": "Live Extracted Inspection",
                        "cards": [
                            {"title": "Source File", "text": tool_data.get("filename", "sample_inspection.pdf")},
                            {"title": "Document ID", "text": tool_data.get("document_id", "live_doc")},
                        ],
                    },
                    {
                        "title": "Extraction Highlights",
                        "bullet_points": [
                            f"Total pages parsed: {tool_data.get('total_pages', 1)}",
                            f"Total tables found: {tool_data.get('total_tables', 0)}",
                            f"Overall confidence: {tool_data.get('overall_confidence', 1.0)}",
                        ],
                    },
                ]
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "generate_presentation",
                        "args": {
                            "filepath": pptx_path,
                            "title": "Live Ultrasonic Inspection Deck",
                            "subtitle": title_text,
                            "slides_json": json.dumps(slides),
                        },
                        "id": "c3",
                    }],
                )
            # 3. Inspect generated presentation
            if "file" in tool_data and tool_data.get("format") == "pptx":
                assert tool_data["status"] == "success"
                assert tool_data["file_exists"] is True
                assert tool_data["size_bytes"] > 0
                return AIMessage(
                    content=f"Extracted real evidence from live Document Engine and generated PowerPoint deck at `{pptx_path}` ({tool_data['size_bytes']} bytes).",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("Find sample_inspection.pdf, extract its evidence with Document Engine, and create a PowerPoint presentation.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "generate_presentation"]

    out_file = action_workspace / pptx_path
    assert out_file.exists()
    assert out_file.stat().st_size > 10000
    prs = Presentation(str(out_file))
    assert len(prs.slides) == 3
    assert pptx_path in result["reply"]
