"""Phase 7: Agent Error Recovery and Self-Correction Tests.

Validates that the Agent is robust against all failure modes:
1. File not found -> discover with find_files -> read document -> answer
2. Unsupported file type -> fallback to alternative valid tool (read_file) -> answer
3. Corrupt document -> report corruption cleanly, no hallucination
4. Document Engine unavailable -> report service status, no fabrication
5. OCR failure / unreadable region -> report inability to decipher
6. Malformed math -> self-correct syntax -> recalculate -> answer
7. MathTool mathematical error (division by zero) -> explain error, no fabrication
8. Action tool failure -> report failure accurately, never claim success
9. Timeout -> report timeout gracefully
10. Empty evidence -> report empty document
11. Low-confidence evidence -> warn user about potential recognition errors
12. Human-review-required -> explicitly highlight reconciliation disagreement
13. Loop prevention -> no infinite retries when tool calls repeat
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent import CodingAgent
from app.tools.document_tool import DocumentTool
from app.tools.manager import ToolManager


@pytest.fixture
def recovery_workspace(tmp_path: Path):
    """Setup workspace with sample test files."""
    workspace_dir = tmp_path / "recovery_workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = workspace_dir / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Valid PDF file placed in subfolder (not at root)
    (docs_dir / "annual_inspection.pdf").write_bytes(b"%PDF-1.4 valid inspection content")

    # Plain text file with .log extension
    (workspace_dir / "system.log").write_text("INFO: System initialized successfully at 04:00:00.\nERROR: None.", encoding="utf-8")

    yield workspace_dir

    shutil.rmtree(workspace_dir, ignore_errors=True)


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
# TEST 1: File Not Found -> Discovery with find_files -> Read -> Answer
# ==============================================================================
def test_recovery_01_file_not_found_discovery(recovery_workspace):
    """Agent encounters file not found, uses find_files to locate it, and answers."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    mock_evidence = {
        "document_id": "doc_annual_insp",
        "filename": "annual_inspection.pdf",
        "file_type": "pdf",
        "file_hash": "hash_annual_01",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "elements": [
            {"id": "p1_t1", "page": 1, "type": "text", "text": "Annual Inspection Verdict: Vessel Approved for 24 months."},
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: LLM tries to read file at root (which doesn't exist)
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "annual_inspection.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Tool returns error with hint to use find_files. LLM calls find_files.
            if tool_data.get("status") == "error":
                assert "File not found" in tool_data.get("error", "")
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "find_files", "args": {"pattern": "*annual_inspection*"}, "id": "c2"}],
                )
            # Step 3: find_files returns matches. LLM calls read_document on correct path.
            if "matches" in tool_data:
                correct_path = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": correct_path}, "id": "c3"}],
                )
            # Step 4: Final answer
            if "document_id" in tool_data:
                return AIMessage(
                    content="Located annual inspection in `documents/annual_inspection.pdf`. Verdict: Vessel Approved for 24 months.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Read annual_inspection.pdf and tell me the verdict.")

    tool_seq = [a["tool"] for a in result["tool_actions"]]
    assert tool_seq == ["read_document", "find_files", "read_document"]
    assert "Approved for 24 months" in result["reply"]


# ==============================================================================
# TEST 2: Unsupported File Type -> Fallback to read_file
# ==============================================================================
def test_recovery_02_unsupported_file_fallback_to_read_file(recovery_workspace):
    """When read_document returns unsupported file error, agent switches to read_file."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    mock_unsupported_evidence = {
        "document_id": "doc_log_unsupported",
        "processing_status": "failed",
        "error": "Unsupported file format: log. Supported formats: PDF, DOCX, PPTX, XLSX, CSV, TXT, PNG, JPG.",
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: LLM tries read_document on .log file
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "system.log"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Tool returns unsupported with hint to use read_file. LLM calls read_file.
            if tool_data.get("status") == "unsupported":
                assert "read_file" in tool_data.get("hint", "")
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_file", "args": {"path": "system.log"}, "id": "c2"}],
                )
            # Step 3: LLM inspects log content and answers
            if "content" in tool_data:
                return AIMessage(
                    content=f"Log file read via `read_file`: {tool_data['content']}",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_unsupported_evidence

        result = agent.chat("Read system.log and check if there are any errors.")

    tool_seq = [a["tool"] for a in result["tool_actions"]]
    assert tool_seq == ["read_document", "read_file"]
    assert "System initialized successfully" in result["reply"]


# ==============================================================================
# TEST 3: Corrupt Document Handling (No Hallucination)
# ==============================================================================
def test_recovery_03_corrupt_document_clean_reporting(recovery_workspace):
    """Agent reports document corruption accurately without fabricating content."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    corrupt_file = recovery_workspace / "documents" / "broken.pdf"
    corrupt_file.write_bytes(b"NOT A VALID PDF CORRUPT HEADER")

    mock_failed_evidence = {
        "document_id": "doc_corrupt_01",
        "processing_status": "failed",
        "error": "PyMuPDF failed to parse document: broken stream or corrupted xref table.",
    }

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "documents/broken.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Inspect failure and report cleanly to user without fabrication
            assert tool_data.get("status") == "failed"
            return AIMessage(
                content=f"The document `documents/broken.pdf` could not be analyzed: {tool_data.get('error')}. Please verify the file integrity.",
                tool_calls=[],
            )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_failed_evidence

        result = agent.chat("Summarize the findings in documents/broken.pdf.")

    assert result["tool_actions"][0]["tool"] == "read_document"
    assert "could not be analyzed" in result["reply"].lower() or "failed" in result["reply"].lower()
    assert "broken stream" in result["reply"]


# ==============================================================================
# TEST 4: Document Engine Unavailable
# ==============================================================================
def test_recovery_04_engine_unavailable_graceful_handling(recovery_workspace):
    """When Document Engine is unreachable, agent reports service status without fabricating."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "documents/annual_inspection.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            assert tool_data.get("status") == "error"
            assert "Could not connect to Document Engine" in tool_data.get("error", "")
            return AIMessage(
                content="The Document Engine service is currently unreachable on port 8001. Please start the service with `uvicorn app.main:app --port 8001`.",
                tool_calls=[],
            )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        result = agent.chat("Analyze documents/annual_inspection.pdf.")

    assert result["tool_actions"][0]["tool"] == "read_document"
    assert "Document Engine service is currently unreachable" in result["reply"]


# ==============================================================================
# TEST 5: OCR / Handwriting Failure Reporting
# ==============================================================================
def test_recovery_05_ocr_failure_reporting(recovery_workspace):
    """When handwriting/OCR cannot decipher text, agent reports the inability rather than guessing."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    mock_evidence = {
        "document_id": "doc_unreadable_note",
        "filename": "scanned_doctor_note.pdf",
        "file_type": "pdf",
        "file_hash": "hash_unreadable",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.25,
        "elements": [
            {
                "id": "p1_hw1",
                "page": 1,
                "type": "handwriting",
                "text": None,  # OCR & VLM could not decipher handwriting
                "confidence": 0.25,
                "metadata": {"reconciliation_agreement_status": "unreadable_ink"},
            }
        ],
    }

    dummy_file = recovery_workspace / "scanned_doctor_note.pdf"
    dummy_file.write_bytes(b"%PDF-1.4 unreadable note")

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "scanned_doctor_note.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            assert tool_data.get("low_confidence") is True
            return AIMessage(
                content="The handwritten doctor's note could not be deciphered by OCR (confidence 0.25). Please provide a clearer scan.",
                tool_calls=[],
            )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_evidence

        result = agent.chat("Read the prescription in scanned_doctor_note.pdf.")

    assert "could not be deciphered" in result["reply"].lower() or "confidence" in result["reply"].lower()


# ==============================================================================
# TEST 6: Malformed Math Self-Correction
# ==============================================================================
def test_recovery_06_malformed_math_self_correction(recovery_workspace):
    """When MathTool returns syntax error, Agent inspects error, self-corrects input, and succeeds."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: LLM makes a syntax mistake in calculation
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "calculate", "args": {"expression": "15 * + * 4"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Tool reports malformed_expression. LLM self-corrects to "15 * 4".
            if tool_data.get("operation") == "malformed_expression":
                assert tool_data["success"] is False
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "calculate", "args": {"expression": "15 * 4"}, "id": "c2"}],
                )
            # Step 3: LLM receives successful result (60)
            if tool_data.get("success") is True:
                assert int(tool_data["result"]) == 60
                return AIMessage(
                    content=f"Initial syntax was corrected. The evaluated result of 15 * 4 is {tool_data['result']}.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("Calculate 15 times 4.")

    tool_seq = [a["tool"] for a in result["tool_actions"]]
    assert tool_seq == ["calculate", "calculate"]
    # Verify self-correction
    assert result["tool_actions"][0]["args"]["expression"] == "15 * + * 4"
    assert result["tool_actions"][1]["args"]["expression"] == "15 * 4"
    assert "60" in result["reply"]


# ==============================================================================
# TEST 7: MathTool Division by Zero (No Fabrication)
# ==============================================================================
def test_recovery_07_math_zero_division_reporting(recovery_workspace):
    """MathTool returns division by zero error; Agent reports error without inventing numbers."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "calculate", "args": {"expression": "100 / (10 - 10)"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            assert tool_data.get("success") is False
            return AIMessage(
                content=f"Calculation failed: {tool_data.get('error')}. Division by zero is undefined.",
                tool_calls=[],
            )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("Compute 100 / (10 - 10).")

    assert result["tool_actions"][0]["tool"] == "calculate"
    assert "division by zero" in result["reply"].lower() or "undefined" in result["reply"].lower()


# ==============================================================================
# TEST 8: Action Failure Guard (Never Claim Success When Action Fails)
# ==============================================================================
def test_recovery_08_action_failure_guard_prevents_false_success(recovery_workspace):
    """When action fails (e.g. create_file error), agent guard prevents false claim of success."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    # Pre-create file so create_file will fail with FileExistsError
    existing_file = recovery_workspace / "immutable.txt"
    existing_file.write_text("Original content", encoding="utf-8")

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "create_file", "args": {"path": "immutable.txt", "content": "New content"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            # Simulate LLM falsely trying to claim success despite tool error
            return AIMessage(
                content="I have successfully created immutable.txt with the new content!",
                tool_calls=[],
            )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("Create immutable.txt with 'New content'.")

    # The action failure guard should have caught the error and prevented the false success claim
    assert "failed" in result["reply"].lower() or "cannot claim success" in result["reply"].lower()
    assert "File already exists" in result["reply"]


# ==============================================================================
# TEST 9: Timeout Handling
# ==============================================================================
def test_recovery_09_timeout_reporting(recovery_workspace):
    """When tool times out, agent reports the timeout cleanly."""
    tool = DocumentTool(root_dir=recovery_workspace)

    with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")):
        res = tool.execute(path="documents/annual_inspection.pdf")

    assert res["status"] == "error"
    assert res.get("timeout") is True
    assert "timed out after 90 seconds" in res["error"]


# ==============================================================================
# TEST 10: Empty Evidence Handling
# ==============================================================================
def test_recovery_10_empty_evidence_reporting(recovery_workspace):
    """When document has zero elements, tool flags empty_evidence."""
    tool = DocumentTool(root_dir=recovery_workspace)

    mock_empty_doc = {
        "document_id": "doc_empty_pdf",
        "filename": "blank.pdf",
        "file_type": "pdf",
        "file_hash": "hash_blank",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 1.0,
        "elements": [],
    }

    blank_file = recovery_workspace / "blank.pdf"
    blank_file.write_bytes(b"%PDF-1.4 blank")

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_empty_doc

        res = tool.execute(path="blank.pdf")

    assert res["status"] == "success"
    assert res["empty_evidence"] is True
    assert res["outline"] == []
    assert res["tables_found"] == []


# ==============================================================================
# TEST 11: Low-Confidence Evidence Warning
# ==============================================================================
def test_recovery_11_low_confidence_warning(recovery_workspace):
    """When document overall confidence is low, tool attaches low_confidence warning."""
    tool = DocumentTool(root_dir=recovery_workspace)

    mock_low_conf = {
        "document_id": "doc_low_conf",
        "filename": "smudged_fax.pdf",
        "file_type": "pdf",
        "file_hash": "hash_smudge",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.42,
        "elements": [
            {"id": "p1_e1", "page": 1, "type": "text", "text": "Smudged text ??#?", "confidence": 0.42},
        ],
    }

    smudged_file = recovery_workspace / "smudged_fax.pdf"
    smudged_file.write_bytes(b"%PDF-1.4 smudged")

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_low_conf

        res = tool.execute(path="smudged_fax.pdf")

    assert res["status"] == "success"
    assert res["low_confidence"] is True
    assert "Overall extraction confidence is low" in res["warning"]


# ==============================================================================
# TEST 12: Human Review Required Signaling
# ==============================================================================
def test_recovery_12_human_review_required_signaling(recovery_workspace):
    """When document requires human review due to conflict, tool and agent flag it explicitly."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    mock_conflict_doc = {
        "document_id": "doc_conflict_01",
        "filename": "reconciled_meter.pdf",
        "file_type": "pdf",
        "file_hash": "hash_conflict",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.85,
        "elements": [
            {
                "id": "p1_meter",
                "page": 1,
                "type": "text",
                "text": "1500 psi",
                "confidence": 0.85,
                "metadata": {
                    "requires_human_review": True,
                    "reconciliation_category": "pressure_reading",
                    "ocr_candidate": "1500 psi",
                    "vlm_candidate": "7500 psi",
                    "reconciliation_agreement_status": "disagreement",
                    "disagreement_details": "OCR read 1500 psi but VLM visually confirmed gauge needle at 7500 psi.",
                },
            }
        ],
    }

    meter_file = recovery_workspace / "reconciled_meter.pdf"
    meter_file.write_bytes(b"%PDF-1.4 meter reading")

    def side_effect(messages):
        last_msg = messages[-1]
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "reconciled_meter.pdf"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            assert tool_data["requires_human_review"] is True
            conflict = tool_data["conflicts"][0]
            return AIMessage(
                content=(
                    f"WARNING: Human review is required for `reconciled_meter.pdf`. "
                    f"OCR read '{conflict['ocr_candidate']}' while VLM read '{conflict['vlm_candidate']}'. "
                    f"Details: {conflict['details']}"
                ),
                tool_calls=[],
            )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_conflict_doc

        result = agent.chat("Read the pressure gauge in reconciled_meter.pdf.")

    assert "Human review is required" in result["reply"]
    assert "1500 psi" in result["reply"]
    assert "7500 psi" in result["reply"]


# ==============================================================================
# TEST 13: Loop Prevention (No Infinite Retries)
# ==============================================================================
def test_recovery_13_no_infinite_tool_loops(recovery_workspace):
    """When a tool call repeats with identical arguments, agent loop blocks repetition and terminates."""
    agent, mock_llm_with_tools = _create_mock_agent(recovery_workspace)

    call_count = 0

    def side_effect(messages):
        nonlocal call_count
        call_count += 1
        # LLM keeps stubbornly calling the exact same failing tool
        return AIMessage(
            content="",
            tool_calls=[{"name": "read_document", "args": {"path": "nonexistent.pdf"}, "id": f"c_{call_count}"}],
        )

    mock_llm_with_tools.invoke.side_effect = side_effect

    result = agent.chat("Read nonexistent.pdf.")

    # The loop must have terminated safely without crashing or running forever
    tool_actions = result["tool_actions"]
    assert len(tool_actions) >= 2
    # Second call must be flagged as already_executed
    second_result = json.loads(tool_actions[1]["result"])
    assert second_result.get("status") == "already_executed"
    assert "Avoid repeated calls" in second_result.get("message", "")
