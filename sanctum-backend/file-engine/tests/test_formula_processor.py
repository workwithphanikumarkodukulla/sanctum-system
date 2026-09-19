"""Unit tests for the SymPy-powered deterministic formula processing module."""
from __future__ import annotations

import pytest
from app.extractors.formulas import FormulaResult, formula_extractor


def test_formula_f_equals_m_a_parsing():
    """Verify F = m*a extracts variables and creates symbolic Eq representation."""
    result = formula_extractor.process_formula("F = m*a")

    assert result.status == "parsed"
    assert result.original_text == "F = m*a"
    assert "Eq" in result.sympy_expr
    assert set(result.variables) == {"F", "a", "m"}
    assert result.provenance.get("engine") == "SymPy"
    assert result.provenance.get("operation") == "symbolic_evaluation"


def test_formula_variable_substitution_and_calculation():
    """Verify F = m*a with m=10, a=9.8 calculates F=98 deterministically."""
    result = formula_extractor.process_formula(
        "F = m*a",
        substitutions={"m": 10, "a": 9.8},
    )

    assert result.status == "calculated"
    assert result.result_value == 98
    assert result.solved_for == "F"
    assert result.provenance.get("operation") == "equation_solution"


def test_formula_audit_required_cases():
    """Verify exact formula requirements from final audit specification."""
    # 1. F = m*a with m = 20, a = 5 -> F = 100
    res_f = formula_extractor.process_formula("F = m*a", substitutions={"m": 20, "a": 5})
    assert res_f.status == "calculated"
    assert res_f.solved_for == "F"
    assert res_f.result_value == 100
    assert res_f.provenance.get("unit_verification") == "unsupported_not_performed"

    # 2. P = F/A with F = 25000, A = 0.05 -> P = 500000
    res_p = formula_extractor.process_formula("P = F/A", substitutions={"F": 25000, "A": 0.05})
    assert res_p.status == "calculated"
    assert res_p.solved_for == "P"
    assert res_p.result_value == 500000
    assert res_p.provenance.get("unit_verification") == "unsupported_not_performed"


def test_formula_equation_solving_for_target():
    """Verify equation solving for a specific variable (e.g. F = m*a solved for a, or x^2 - 16 = 0)."""
    # Solve F = m*a for a given F=100 and m=20
    res_a = formula_extractor.process_formula(
        "F = m*a",
        substitutions={"F": 100, "m": 20},
    )
    assert res_a.status == "calculated"
    assert res_a.result_value == 5
    assert res_a.solved_for == "a"

    # Quadratic equation solving: x^2 - 16 = 0
    res_quad = formula_extractor.process_formula("x^2 - 16 = 0", solve_for="x")
    assert res_quad.status == "calculated"
    assert res_quad.solved_for == "x"
    assert set(res_quad.result_value) == {-4, 4}


def test_formula_simple_arithmetic():
    """Verify basic arithmetic expressions evaluate deterministically without LLM calls."""
    result = formula_extractor.process_formula("(15 + 25) * 3 / 2")

    assert result.status == "calculated"
    assert result.result_value == 60
    assert result.variables == []
    assert result.provenance.get("operation") == "numeric_evaluation"


def test_formula_powers_and_sqrt():
    """Verify square roots and powers evaluate accurately."""
    # Standard sqrt
    res_sqrt = formula_extractor.process_formula("sqrt(144) + 2^3")
    assert res_sqrt.status == "calculated"
    assert res_sqrt.result_value == 20

    # LaTeX sqrt syntax
    res_latex_sqrt = formula_extractor.process_formula(r"\sqrt{25} * 4")
    assert res_latex_sqrt.status == "calculated"
    assert res_latex_sqrt.result_value == 20


def test_formula_equality_verification():
    """Verify equation verification succeeds on equality and fails on mismatch."""
    # Verified equality
    res_ok = formula_extractor.process_formula(
        "F = m*a",
        substitutions={"F": 100, "m": 10, "a": 10},
    )
    assert res_ok.status == "calculated"
    assert res_ok.result_value is True
    assert res_ok.provenance.get("operation") == "equality_verification"

    # Failed verification: 100 != 10 * 5
    res_fail = formula_extractor.process_formula(
        "F = m*a",
        substitutions={"F": 100, "m": 10, "a": 5},
    )
    assert res_fail.status == "verification_failed"
    assert res_fail.result_value is False
    assert "Verification failed" in res_fail.error


def test_formula_invalid_and_malformed_syntax():
    """Verify malformed formulas fail cleanly with status unsupported and clear error."""
    # Syntax error in math
    res_err = formula_extractor.process_formula("2 +* 5 / ((")
    assert res_err.status == "unsupported"
    assert res_err.error is not None
    assert "SymPy parsing failed" in res_err.error

    # Empty formula
    res_empty = formula_extractor.process_formula("   ")
    assert res_empty.status == "unsupported"
    assert "empty" in res_empty.error.lower()


def test_formula_security_sandbox():
    """Verify arbitrary Python execution attempts are strictly blocked by the sanitizer."""
    malicious_inputs = [
        "__import__('os').system('ls')",
        "eval('2 + 2')",
        "open('/etc/passwd').read()",
        "lambda x: x",
        "import sys; sys.exit()",
        "subprocess.call(['id'])",
    ]

    for bad_input in malicious_inputs:
        res = formula_extractor.process_formula(bad_input)
        assert res.status == "unsupported"
        assert "Unsafe expression detected" in (res.error or "")
        assert res.provenance.get("security") == "rejected"


def test_backward_compatibility_extract_formula_details():
    """Verify the original extract_formula_details API continues to return (latex, variables)."""
    latex, vars_dict = formula_extractor.extract_formula_details("P_max = (2 * S * t) / D")

    assert latex is not None
    assert r"\cdot" in latex or "*" in latex
    assert vars_dict is not None
    assert "P_max" in vars_dict or "D" in vars_dict


def test_formula_to_evidence_element():
    """Verify converting FormulaResult to an EvidenceElement preserves full metadata and provenance."""
    res = formula_extractor.process_formula("F = m*a", substitutions={"m": 5, "a": 2})
    elem = formula_extractor.to_evidence_element(
        result=res,
        document_id="doc_formula_test",
        element_idx=1,
        page=1,
        file_hash="hash12345",
    )

    assert elem.type == "formula"
    assert elem.text == "F = m*a"
    assert elem.confidence == 1.0
    assert elem.extraction_model == "SymPy"
    assert elem.metadata is not None
    assert elem.metadata.get("status") == "calculated"
    assert elem.metadata.get("calculated_value") == 10
    assert elem.metadata.get("solved_for") == "F"


def test_formula_calculus_derivative():
    """Verify symbolic differentiation via SymPy."""
    res = formula_extractor.process_formula("Find the derivative of x^3 + 2x^2 - 5x + 1")
    assert res.status == "calculated"
    assert res.provenance.get("operation") == "differentiation"
    assert "3*x**2 + 4*x - 5" in str(res.result_value)

    res2 = formula_extractor.process_formula("d/dx(x^3 + 2*x^2 - 5*x + 1)")
    assert res2.status == "calculated"
    assert "3*x**2 + 4*x - 5" in str(res2.result_value)


def test_formula_calculus_definite_integral():
    """Verify definite integration via SymPy."""
    res = formula_extractor.process_formula(r"Evaluate \int_0^1 x^2 e^x dx")
    assert res.status == "calculated"
    assert res.provenance.get("operation") == "definite_integration"
    # Definite integral of x^2 * exp(x) from 0 to 1 is e - 2 (~0.718282)
    assert abs(float(res.result_value) - 0.718282) < 1e-4


def test_formula_calculus_indefinite_integral():
    """Verify indefinite integration via SymPy."""
    res = formula_extractor.process_formula(r"\int x^3 + 2*x^2 - 5*x + 1 dx")
    assert res.status == "calculated"
    assert res.provenance.get("operation") == "indefinite_integration"
    assert "x**4/4" in str(res.result_value)
    assert "2*x**3/3" in str(res.result_value)


def test_formula_calculus_limit():
    """Verify limit calculation via SymPy."""
    res = formula_extractor.process_formula(r"\lim_{x \to 0} sin(x)/x")
    assert res.status == "calculated"
    assert res.provenance.get("operation") == "limit_evaluation"
    assert res.result_value == 1


def test_formula_calculus_derivative_exact_ocr_representation():
    """Verify exact real OCR derivative representations with unicode superscripts and spacing."""
    # 1. Exact user string
    res1 = formula_extractor.process_formula("d/dx (x³ + 2x² - 5x + 1)")
    assert res1.status == "calculated"
    assert res1.result_value == "3*x**2 + 4*x - 5"
    assert res1.provenance.get("operation") == "differentiation"
    assert res1.variables == ["x"]

    # 2. No space after d/dx
    res2 = formula_extractor.process_formula("d/dx(x³ + 2x² - 5x + 1)")
    assert res2.status == "calculated"
    assert res2.result_value == "3*x**2 + 4*x - 5"

    # 3. Bare variable with superscript
    res3 = formula_extractor.process_formula("d/dx x³")
    assert res3.status == "calculated"
    assert res3.result_value == "3*x**2"

    # 4. Spaced d / dx
    res4 = formula_extractor.process_formula("d / dx (x³ + 2x² - 5x + 1)")
    assert res4.status == "calculated"
    assert res4.result_value == "3*x**2 + 4*x - 5"


def test_formula_calculus_unsupported_numerical_cases():
    """Verify non-elementary / symbolic integrals return 'unsupported' without hallucinating."""
    res = formula_extractor.process_formula(r"\int sin(cos(x^4)) dx")
    assert res.status == "unsupported"
    assert "Requires numerical methods or external solver" in (res.error or "")
    assert res.provenance.get("calculus_status") == "requires_numerical_or_external_solver"

    # Genuinely unparseable / malformed derivative expressions return unsupported without guessing
    res_malformed = formula_extractor.process_formula("d/dx ($%^&)")
    assert res_malformed.status == "unsupported"
    assert "SymPy parsing failed" in (res_malformed.error or "")

    res_empty_paren = formula_extractor.process_formula("d/dx ()")
    assert res_empty_paren.status == "unsupported"

