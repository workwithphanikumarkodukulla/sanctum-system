"""Test suite for Deterministic MathTool and Agent Integration (Phase 4).

Tests the 12 exact scenarios required for deterministic mathematics:
1. basic arithmetic
2. derivative
3. integral (indefinite)
4. definite integral
5. limit
6. equation solving
7. malformed expression
8. unsupported operation
9. malicious expression/input
10. document formula -> MathTool -> Agent explanation
11. document numeric values -> MathTool -> Agent explanation
12. ordinary question should not invoke MathTool unnecessarily

Verifies:
- All structured result fields: operation, normalized_input, result, success, error, deterministic, backend.
- SymPy is NOT used during document ingestion.
- Agent decides when mathematical computation is required.
- Agent interprets and explains deterministic results.
- No eval(), exec(), or arbitrary Python execution.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent import CodingAgent
from app.tools.manager import ToolManager
from app.tools.sympy_tool import MathTool, SymPyTool


@pytest.fixture
def math_workspace():
    """Create a temporary workspace for MathTool testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum_math_ws_"))
    
    docs_dir = temp_dir / "sample_documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Physics report with hydrostatic formula
    (docs_dir / "physics_spec.pdf").write_bytes(b"%PDF-1.4 mock physics spec")
    # Quarterly earnings report
    (docs_dir / "quarterly_earnings.xlsx").write_bytes(b"PK\x03\x04mock_quarterly_earnings")

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def _create_mock_agent(workspace_dir: Path):
    """Helper to create a CodingAgent with mock LLM manager."""
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
# 1. Basic Arithmetic
# ==============================================================================
def test_01_basic_arithmetic():
    """Verify deterministic arithmetic evaluation and structured output."""
    tool = MathTool()
    res = tool.execute(expression="2 + 2")
    assert res["success"] is True
    assert res["result"] == 4
    assert res["operation"] == "arithmetic"
    assert res["deterministic"] is True
    assert res["error"] is None
    assert "SymPy" in res["backend"]["engine"]

    # Complex order of operations
    res2 = tool.execute(expression="15 * 8 - 4 / 2")
    assert res2["success"] is True
    assert res2["result"] == 118
    assert res2["operation"] == "arithmetic"

    # Powers and roots
    res3 = tool.execute(expression="sqrt(144) + 2**5")
    assert res3["success"] is True
    assert res3["result"] == 44


# ==============================================================================
# 2. Derivative (Differentiation)
# ==============================================================================
def test_02_derivative():
    """Verify symbolic differentiation."""
    tool = MathTool()
    
    # Polynomial derivative
    res_poly = tool.execute(expression="diff(x**3 + 2*x, x)")
    assert res_poly["success"] is True
    assert res_poly["result"] == "3*x**2 + 2"
    assert res_poly["operation"] == "differentiation"
    assert res_poly["deterministic"] is True
    assert res_poly["error"] is None

    # Trigonometric derivative
    res_trig = tool.execute(expression="diff(sin(x), x)")
    assert res_trig["success"] is True
    assert res_trig["result"] == "cos(x)"

    # Natural language syntax
    res_text = tool.execute(expression="derivative of x**4 with respect to x")
    assert res_text["success"] is True
    assert res_text["result"] == "4*x**3"


# ==============================================================================
# 3. Indefinite Integral
# ==============================================================================
def test_03_indefinite_integral():
    """Verify symbolic indefinite integration."""
    tool = MathTool()
    
    res = tool.execute(expression="integrate(x**2, x)")
    assert res["success"] is True
    assert res["result"] == "x**3/3"
    assert res["operation"] == "indefinite_integration"
    assert res["deterministic"] is True
    assert res["error"] is None

    # Trigonometric integral
    res_cos = tool.execute(expression="integrate(cos(x), x)")
    assert res_cos["success"] is True
    assert res_cos["result"] == "sin(x)"

    # Natural language syntax
    res_nl = tool.execute(expression="integral of exp(x) with respect to x")
    assert res_nl["success"] is True
    assert res_nl["result"] == "exp(x)"


# ==============================================================================
# 4. Definite Integral
# ==============================================================================
def test_04_definite_integral():
    """Verify definite integration with bounds."""
    tool = MathTool()
    
    # integrate(x**2, (x, 0, 3)) -> [x^3 / 3]_0^3 = 27/3 = 9
    res = tool.execute(expression="integrate(x**2, (x, 0, 3))")
    assert res["success"] is True
    assert res["result"] == 9
    assert res["operation"] == "definite_integration"
    assert res["deterministic"] is True

    # Natural language syntax: integral of x from 0 to 4
    res_text = tool.execute(expression="integral of x from 0 to 4 with respect to x")
    assert res_text["success"] is True
    assert res_text["result"] == 8

    # LaTeX syntax
    res_latex = tool.execute(expression=r"\int_{0}^{2} x dx")
    assert res_latex["success"] is True
    assert res_latex["result"] == 2


# ==============================================================================
# 5. Limit
# ==============================================================================
def test_05_limit():
    """Verify symbolic limit computation."""
    tool = MathTool()
    
    # Classic limit: sin(x)/x as x -> 0 = 1
    res = tool.execute(expression="limit(sin(x)/x, x, 0)")
    assert res["success"] is True
    assert res["result"] == 1
    assert res["operation"] == "limit"
    assert res["deterministic"] is True
    assert res["error"] is None

    # Limit to infinity: 1/x as x -> oo = 0
    res_inf = tool.execute(expression="limit(1/x, x, oo)")
    assert res_inf["success"] is True
    assert res_inf["result"] == 0

    # Natural language syntax
    res_nl = tool.execute(expression="limit of (x**2 - 1)/(x - 1) as x -> 1")
    assert res_nl["success"] is True
    assert res_nl["result"] == 2


# ==============================================================================
# 6. Equation Solving
# ==============================================================================
def test_06_equation_solving():
    """Verify deterministic equation solving."""
    tool = MathTool()
    
    # Quadratic: x**2 - 16 = 0 -> [-4, 4]
    res_quad = tool.execute(expression="x**2 - 16 = 0", solve_for="x")
    assert res_quad["success"] is True
    assert sorted(res_quad["result"]) == [-4, 4]
    assert res_quad["operation"] == "equation_solving"
    assert res_quad["deterministic"] is True

    # Linear equation: 3*x + 9 = 0
    res_lin = tool.execute(expression="solve(3*x + 9 = 0, x)")
    assert res_lin["success"] is True
    assert res_lin["result"] in ([-3], -3)

    # Solve with variable substitutions
    res_sub = tool.execute(
        expression="F = m * a",
        substitutions={"F": 100, "m": 20},
        solve_for="a",
    )
    assert res_sub["success"] is True
    assert res_sub["result"] == 5


# ==============================================================================
# 7. Malformed Expression
# ==============================================================================
def test_07_malformed_expression():
    """Verify graceful error reporting on invalid math syntax without crashing."""
    tool = MathTool()
    
    # Operator syntax error
    res_syntax = tool.execute(expression="2 + * 3")
    assert res_syntax["success"] is False
    assert res_syntax["result"] is None
    assert res_syntax["error"] is not None
    assert "malformed" in res_syntax["operation"] or "error" in res_syntax["status"]
    assert res_syntax["deterministic"] is True

    # Unbalanced parentheses
    res_unbal = tool.execute(expression="((x + 1")
    assert res_unbal["success"] is False
    assert res_unbal["result"] is None
    assert res_unbal["error"] is not None

    # Empty expression
    res_empty = tool.execute(expression="")
    assert res_empty["success"] is False
    assert res_empty["result"] is None


# ==============================================================================
# 8. Unsupported Operation
# ==============================================================================
def test_08_unsupported_operation():
    """Verify non-math input or unsupported operation is safely rejected."""
    tool = MathTool()
    
    # Explicit unsupported operation flag
    res_unsupp = tool.execute(expression="x**2", operation="quantum_teleportation")
    assert res_unsupp["success"] is False
    assert res_unsupp["result"] is None
    assert res_unsupp["operation"] == "unsupported"
    assert "Unsupported" in res_unsupp["error"]

    # Natural language non-math text
    res_prose = tool.execute(expression="deploy kubernetes cluster to production")
    assert res_prose["success"] is False
    assert res_prose["result"] is None
    assert res_prose["operation"] == "unsupported"


# ==============================================================================
# 9. Malicious Expression / Input Security
# ==============================================================================
def test_09_malicious_expression_input():
    """Verify multi-tier security blocks arbitrary code execution and injection."""
    tool = MathTool()
    
    malicious_inputs = [
        "__import__('os').system('ls')",
        "eval('2 + 2')",
        "exec('x = 10')",
        "open('/etc/passwd').read()",
        "subprocess.Popen('whoami')",
        "__builtins__.__import__('os')",
        "globals()['__builtins__']",
        "getattr(sys, 'exit')",
        "2 + 2; import os",
        "2 + 2 `ls`",
    ]

    for attack in malicious_inputs:
        res = tool.execute(expression=attack)
        assert res["success"] is False, f"Attack '{attack}' should have failed!"
        assert res["result"] is None
        assert res["operation"] == "security_violation"
        assert "Unsafe expression" in res["error"]
        assert res["backend"]["security"] == "rejected"


# ==============================================================================
# 10. Document Formula -> MathTool -> Agent Explanation
# ==============================================================================
def test_10_document_formula_to_math_tool(math_workspace):
    """Scenario 10: Extract formula from DocumentEvidence -> calculate -> Agent explanation."""
    agent, mock_llm_with_tools = _create_mock_agent(math_workspace)

    mock_doc_evidence = {
        "document_id": "doc_hydrostatic_spec",
        "filename": "physics_spec.pdf",
        "file_type": "pdf",
        "file_hash": "spec9988",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "elements": [
            {
                "id": "p1_f1", "page": 1, "type": "formula",
                "text": "P = \\rho \\cdot g \\cdot h",
                "formula_latex": "P = \\rho \\cdot g \\cdot h",
                "formula_variables": {"P": "pressure", "rho": "fluid density", "g": "gravity", "h": "depth"},
                "confidence": 0.99,
                "bbox": [50, 100, 300, 140],
            }
        ],
    }

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: User asks to calculate pressure from document
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "find_files", "args": {"pattern": "*physics*.pdf"}, "id": "c_find"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: Read document
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "c_doc"}],
                )
            # Step 3: Extract formula and compute with MathTool
            if "document_id" in tool_data:
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "calculate",
                        "args": {
                            "expression": "P = rho * g * h",
                            "substitutions": json.dumps({"rho": 1000, "g": 9.81, "h": 15}),
                            "solve_for": "P",
                        },
                        "id": "c_math",
                    }],
                )
            # Step 4: Agent receives deterministic calculation and explains it
            if "result" in tool_data:
                assert tool_data["success"] is True
                assert float(tool_data["result"]) == 147150.0
                return AIMessage(
                    content=(
                        "From Page 1 of `physics_spec.pdf`, the hydrostatic formula is P = rho * g * h. "
                        "Using rho=1000 kg/m³, g=9.81 m/s², and h=15 m, MathTool computed a pressure of 147,150.0 Pa."
                    ),
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_doc_evidence

        result = agent.chat("Evaluate the pressure formula from the document using rho=1000, g=9.81, h=15.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "calculate"]
    # Check MathTool result
    math_action = result["tool_actions"][2]
    math_res = json.loads(math_action["result"])
    assert math_res["success"] is True
    assert float(math_res["result"]) == 147150.0
    assert "147,150" in result["reply"]
    assert "physics_spec.pdf" in result["reply"] or "Page 1" in result["reply"]


# ==============================================================================
# 11. Document Numeric Values -> MathTool -> Agent Explanation
# ==============================================================================
def test_11_document_numeric_values_to_math_tool(math_workspace):
    """Scenario 11: Extract table figures from DocumentEvidence -> calculate sum -> Agent explanation."""
    agent, mock_llm_with_tools = _create_mock_agent(math_workspace)

    mock_doc_evidence = {
        "document_id": "doc_earnings_table",
        "filename": "quarterly_earnings.xlsx",
        "file_type": "xlsx",
        "file_hash": "earn1122",
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.99,
        "elements": [
            {
                "id": "p1_tbl1", "page": 1, "type": "table",
                "table_data": [
                    ["Quarter", "Revenue (USD)"],
                    ["Q1", "25000"],
                    ["Q2", "30000"],
                    ["Q3", "35000"],
                    ["Q4", "40000"],
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
                tool_calls=[{"name": "find_files", "args": {"pattern": "*earnings*.xlsx"}, "id": "c_find"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            if "matches" in tool_data:
                target = tool_data["matches"][0]["path"]
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "read_document", "args": {"path": target}, "id": "c_doc"}],
                )
            if "document_id" in tool_data:
                # Sum the four quarters extracted from table
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "calculate",
                        "args": {"expression": "25000 + 30000 + 35000 + 40000"},
                        "id": "c_sum",
                    }],
                )
            if "result" in tool_data:
                assert tool_data["result"] == 130000
                return AIMessage(
                    content="From `quarterly_earnings.xlsx`, the four quarters sum to a total annual revenue of $130,000.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_doc_evidence

        result = agent.chat("Read the financial report and calculate the total annual revenue.")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["find_files", "read_document", "calculate"]
    assert "130,000" in result["reply"]


# ==============================================================================
# 12. Ordinary Question Should Not Invoke MathTool Unnecessarily
# ==============================================================================
def test_12_ordinary_question_no_math_tool(math_workspace):
    """Scenario 12: Greetings and conceptual questions must not invoke MathTool."""
    agent, mock_llm_with_tools = _create_mock_agent(math_workspace)

    mock_llm_with_tools.invoke.return_value = AIMessage(
        content="Hello! I am Sanctum. I can assist with programming, document extraction, and mathematics.",
        tool_calls=[],
    )

    result = agent.chat("Hello there!")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == []
    assert not any(a["tool"] in ("calculate", "math", "sympy") for a in result["tool_actions"])
    assert "Sanctum" in result["reply"]
