"""Formula and LaTeX region extraction module powered by SymPy."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement

logger = logging.getLogger(__name__)

# Security: prohibited tokens and patterns to prevent arbitrary Python code execution
UNSAFE_TOKEN_PATTERNS = [
    r"__",
    r"\bimport\b",
    r"\bexec\b",
    r"\beval\b",
    r"\bopen\b",
    r"\bos\b",
    r"\bsys\b",
    r"\bsubprocess\b",
    r"\bclass\b",
    r"\blambda\b",
    r"\bdef\b",
    r"\byield\b",
    r"\bglobals\b",
    r"\blocals\b",
    r"\bbuiltins\b",
    r"\bgetattr\b",
    r"\bsetattr\b",
    r"\bdelattr\b",
    r"\bcompile\b",
]

# Restricted safe global namespace for SymPy parse_expr
SAFE_SYMPY_GLOBALS = {
    "__builtins__": None,
    "Integer": sympy.Integer,
    "Float": sympy.Float,
    "Number": sympy.Number,
    "Symbol": sympy.Symbol,
    "Rational": sympy.Rational,
    "sqrt": sympy.sqrt,
    "Abs": sympy.Abs,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "log": sympy.log,
    "exp": sympy.exp,
    "pi": sympy.pi,
    "E": sympy.E,
    "Eq": sympy.Eq,
    "symbols": sympy.symbols,
    "Pow": sympy.Pow,
    "Add": sympy.Add,
    "Mul": sympy.Mul,
    "diff": sympy.diff,
    "integrate": sympy.integrate,
    "limit": sympy.limit,
    "Derivative": sympy.Derivative,
    "Integral": sympy.Integral,
    "Limit": sympy.Limit,
    "oo": sympy.oo,
    "ln": sympy.log,
}

SAFE_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


@dataclass
class FormulaResult:
    """Structured result of formula parsing, variable extraction, and deterministic calculation."""
    status: Literal["parsed", "calculated", "verification_failed", "unsupported"]
    original_text: str
    latex: str | None = None
    sympy_expr: str | None = None
    variables: list[str] = field(default_factory=list)
    substitutions: dict[str, Any] | None = None
    result_value: Any = None
    solved_for: str | None = None
    error: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "original_text": self.original_text,
            "latex": self.latex,
            "sympy_expr": self.sympy_expr,
            "variables": self.variables,
            "substitutions": self.substitutions,
            "result_value": self.result_value,
            "solved_for": self.solved_for,
            "error": self.error,
            "provenance": self.provenance,
        }


class FormulaExtractor:
    """Extracts, parses, verifies, and calculates mathematical expressions deterministically using SymPy."""

    @classmethod
    def _sanitize_expression(cls, expr_str: str) -> None:
        """Enforce strict code safety: reject any attempts to execute arbitrary Python code."""
        lower_expr = expr_str.lower()
        for pattern in UNSAFE_TOKEN_PATTERNS:
            if re.search(pattern, lower_expr):
                raise ValueError(f"Unsafe expression detected: prohibited token or keyword matching '{pattern}'.")

        # Reject suspicious code delimiters
        if any(c in expr_str for c in [";", "`"]):
            raise ValueError("Unsafe expression detected: prohibited delimiter character.")

    @classmethod
    def _clean_for_sympy(cls, expr_str: str) -> str:
        """Convert common math, unicode, and LaTeX representations to SymPy parseable syntax."""
        cleaned = expr_str.strip().strip("$")
        # Strip spreadsheet leading '='
        if cleaned.startswith("="):
            cleaned = cleaned.lstrip("=").strip()

        # Unicode superscripts (e.g. ³, ², ¹, ⁰) -> **(digits)
        superscript_map = {
            "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
            "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
            "⁺": "+", "⁻": "-",
        }
        # Deduplicate OCR duplicate superscript + ASCII digit artifact (e.g. 'x³3' -> 'x³', 'x²2' -> 'x²')
        cleaned = re.sub(
            r"([⁰¹²³⁴⁵⁶⁷⁸⁹])([0-9])",
            lambda m: m.group(1) if superscript_map.get(m.group(1)) == m.group(2) else m.group(0),
            cleaned,
        )
        cleaned = re.sub(
            r"([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)",
            lambda m: f"**({''.join(superscript_map.get(c, c) for c in m.group(1))})",
            cleaned,
        )

        # Unicode math symbols from OCR
        cleaned = cleaned.replace("×", "*").replace("÷", "/")
        cleaned = cleaned.replace("−", "-").replace("–", "-")

        # LaTeX operator and relational cleanups
        cleaned = cleaned.replace("\\cdot", "*").replace("\\times", "*")
        cleaned = cleaned.replace("\\le", "<=").replace("\\ge", ">=")
        cleaned = cleaned.replace("\\ne", "!=").replace("\\pm", "+/-")

        # Convert \frac{num}{den} -> ((num)/(den))
        for _ in range(5):
            if "\\frac" not in cleaned:
                break
            cleaned = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", cleaned)

        # Convert \sqrt{x} -> sqrt(x)
        for _ in range(5):
            if "\\sqrt" not in cleaned:
                break
            cleaned = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", cleaned)

        # Remove backslashes from common standard math functions
        cleaned = re.sub(r"\\(sin|cos|tan|log|ln|exp|sqrt|pi|Abs)\b", r"\1", cleaned)

        # Convert ^ to ** for powers if not already handled
        cleaned = cleaned.replace("^", "**")
        return cleaned

    @classmethod
    def _to_native(cls, val: Any) -> Any:
        """Convert SymPy numeric types to native Python int/float/list representations."""
        if isinstance(val, (sympy.Integer, int)):
            return int(val)
        if isinstance(val, (sympy.Float, float)):
            f_val = float(val)
            return int(f_val) if f_val.is_integer() else round(f_val, 6)
        if isinstance(val, sympy.Rational):
            f_val = float(val)
            return int(f_val) if f_val.is_integer() else round(f_val, 6)
        if isinstance(val, (list, tuple)):
            return [cls._to_native(x) for x in val]
        return str(val)

    @classmethod
    def extract_formula_details(
        cls,
        text: str | None,
        raw_data: Any = None,
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Extract LaTeX representation and variable dictionary from a formula element.

        Preserved for 100% backward compatibility with existing parsers and enrichers.
        """
        if not text:
            return None, None

        cleaned = text.strip()
        # Convert simple arithmetic and equations to LaTeX style if not already
        latex_str = cleaned
        if not (latex_str.startswith("$") or "\\" in latex_str):
            replacements = [
                (" * ", " \\cdot "),
                ("<=", " \\le "),
                (">=", " \\ge "),
                ("!=", " \\ne "),
                ("+/-", " \\pm "),
                ("sqrt", "\\sqrt"),
                ("pi", "\\pi"),
                ("alpha", "\\alpha"),
                ("beta", "\\beta"),
                ("theta", "\\theta"),
                ("delta", "\\delta"),
            ]
            for orig, rep in replacements:
                latex_str = latex_str.replace(orig, rep)

        # Extract variable identifiers safely
        try:
            res = cls.process_formula(text)
            if res.variables:
                return latex_str, {v: None for v in res.variables}
        except Exception:
            pass

        # Regex fallback
        variable_names = set(re.findall(r"\b([A-Za-z](?:_[0-9A-Za-z]+)?)\b", cleaned))
        common_terms = {"sin", "cos", "tan", "log", "ln", "exp", "min", "max", "lim", "mod", "dt", "dx", "sqrt"}
        variables = {v: None for v in sorted(variable_names) if v.lower() not in common_terms}
        return latex_str, (variables if variables else None)

    @classmethod
    def _try_evaluate_calculus(
        cls,
        text: str,
        latex_str: str | None,
        prov: dict[str, Any],
    ) -> FormulaResult | None:
        """Detect and evaluate calculus operations (derivatives, integrals, limits).

        If the expression cannot be solved analytically (e.g. non-elementary integral
        or requires numerical discretization), returns status='unsupported' with a clear note
        rather than hallucinating.
        """
        trimmed = text.strip()

        # 1. Differentiation
        # Matches: "find derivative of ...", "derivative of ...", "d/dx(...)", "\frac{d}{dx}(...)", "diff(...)"
        deriv_var = None
        deriv_expr_str = None

        m_deriv_text = re.search(
            r"(?i)^(?:find\s+(?:the\s+)?)?derivative\s+of\s+(.+?)(?:\s+with\s+respect\s+to\s+([a-zA-Z]))?$",
            trimmed,
        )
        m_deriv_op = re.search(
            r"^(?:\\\\?frac\{d\}\{d([a-zA-Z])\}|d\s*/\s*d([a-zA-Z]))\s*(?:[\(\[\{](.*)[\)\]\}]|(?!\bwith\b)(.+?))$",
            trimmed,
        )

        if m_deriv_text:
            deriv_expr_str = m_deriv_text.group(1)
            deriv_var = m_deriv_text.group(2)
        elif m_deriv_op:
            deriv_var = m_deriv_op.group(1) or m_deriv_op.group(2)
            deriv_expr_str = (m_deriv_op.group(3) if m_deriv_op.group(3) is not None else m_deriv_op.group(4)).strip()
        elif trimmed.startswith("diff(") and trimmed.endswith(")"):
            inner = trimmed[5:-1]
            parts = [p.strip() for p in inner.split(",")]
            deriv_expr_str = parts[0]
            if len(parts) > 1:
                deriv_var = parts[1]

        if deriv_expr_str is not None:
            try:
                cleaned = cls._clean_for_sympy(deriv_expr_str)
                expr = parse_expr(cleaned, global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                free_syms = sorted([str(s) for s in expr.free_symbols])
                target_var = sympy.Symbol(deriv_var or (free_syms[0] if free_syms else "x"))
                deriv_result = sympy.diff(expr, target_var)

                if isinstance(deriv_result, sympy.Derivative):
                    prov["operation"] = "differentiation"
                    prov["calculus_status"] = "requires_numerical_or_external_solver"
                    return FormulaResult(
                        status="unsupported",
                        original_text=trimmed,
                        latex=latex_str,
                        sympy_expr=str(deriv_result),
                        variables=free_syms,
                        error="Requires numerical methods or external solver (derivative could not be resolved symbolically).",
                        provenance=prov,
                    )

                prov["operation"] = "differentiation"
                prov["differentiated_variable"] = str(target_var)
                return FormulaResult(
                    status="calculated",
                    original_text=trimmed,
                    latex=latex_str,
                    sympy_expr=str(deriv_result),
                    variables=free_syms,
                    result_value=str(deriv_result),
                    solved_for=f"d/d{target_var}",
                    provenance=prov,
                )
            except Exception as d_err:
                logger.debug("Calculus differentiation parse failed: %s", d_err)

        # 2. Integration
        integ_lower = None
        integ_upper = None
        integ_expr_str = None
        integ_var = None

        m_def_latex = re.search(
            r"(?:\\\\int|\\int)_\{?([0-9a-zA-Z\.\-]+)\}?\^\{?([0-9a-zA-Z\.\-]+)\}?\s+(.+?)\s*d([a-zA-Z])\b",
            trimmed,
        )
        m_def_text = re.search(
            r"(?i)^(?:evaluate\s+|calculate\s+)?integral\s+of\s+(.+?)\s+from\s+([0-9a-zA-Z\.\-]+)\s+to\s+([0-9a-zA-Z\.\-]+)(?:\s+with\s+respect\s+to\s+([a-zA-Z]))?$",
            trimmed,
        )
        m_indef_latex = re.search(
            r"(?:\\\\int|\\int)\s+(.+?)\s*d([a-zA-Z])\b",
            trimmed,
        )
        m_indef_text = re.search(
            r"(?i)^(?:evaluate\s+|calculate\s+)?integral\s+of\s+(.+?)(?:\s+with\s+respect\s+to\s+([a-zA-Z]))?$",
            trimmed,
        )

        if m_def_latex:
            integ_lower, integ_upper, integ_expr_str, integ_var = m_def_latex.groups()
        elif m_def_text:
            integ_expr_str, integ_lower, integ_upper, integ_var = m_def_text.groups()
        elif m_indef_latex:
            integ_expr_str, integ_var = m_indef_latex.groups()
        elif m_indef_text:
            integ_expr_str, integ_var = m_indef_text.groups()

        if integ_expr_str is not None:
            try:
                clean_raw = integ_expr_str.replace("e^", "exp(").replace("e**", "exp(")
                if clean_raw.count("(") > clean_raw.count(")"):
                    clean_raw += ")" * (clean_raw.count("(") - clean_raw.count(")"))
                cleaned = cls._clean_for_sympy(clean_raw)
                expr = parse_expr(cleaned, global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                free_syms = sorted([str(s) for s in expr.free_symbols])
                target_var = sympy.Symbol(integ_var or (free_syms[0] if free_syms else "x"))

                if integ_lower is not None and integ_upper is not None:
                    low_val = parse_expr(cls._clean_for_sympy(integ_lower), global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                    high_val = parse_expr(cls._clean_for_sympy(integ_upper), global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                    integ_result = sympy.integrate(expr, (target_var, low_val, high_val))
                    prov["operation"] = "definite_integration"
                    prov["limits"] = [str(low_val), str(high_val)]
                else:
                    integ_result = sympy.integrate(expr, target_var)
                    prov["operation"] = "indefinite_integration"

                # Check if SymPy could not resolve closed-form
                if isinstance(integ_result, sympy.Integral) or getattr(integ_result, "has", lambda *args: False)(sympy.Integral):
                    prov["calculus_status"] = "requires_numerical_or_external_solver"
                    return FormulaResult(
                        status="unsupported",
                        original_text=trimmed,
                        latex=latex_str,
                        sympy_expr=str(integ_result),
                        variables=free_syms,
                        error="Requires numerical methods or external solver (no closed-form symbolic solution found).",
                        provenance=prov,
                    )

                val_out = cls._to_native(integ_result.evalf()) if (integ_lower is not None and not integ_result.free_symbols) else str(integ_result)
                return FormulaResult(
                    status="calculated",
                    original_text=trimmed,
                    latex=latex_str,
                    sympy_expr=str(integ_result),
                    variables=free_syms,
                    result_value=val_out,
                    provenance=prov,
                )
            except Exception as i_err:
                logger.debug("Calculus integration parse failed: %s", i_err)

        # 3. Limits
        m_lim = re.search(
            r"(?:\\\\lim|\\lim)_\{?([a-zA-Z])\s*(?:\\to|->)\s*([0-9a-zA-Z\.\-\+]+)\}?\s*(.+)$",
            trimmed,
        )
        if m_lim:
            lim_var, lim_target, lim_expr = m_lim.groups()
            try:
                cleaned = cls._clean_for_sympy(lim_expr)
                expr = parse_expr(cleaned, global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                target_sym = sympy.Symbol(lim_var)
                target_val = parse_expr(cls._clean_for_sympy(lim_target), global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                lim_result = sympy.limit(expr, target_sym, target_val)

                if isinstance(lim_result, sympy.Limit):
                    prov["operation"] = "limit_evaluation"
                    prov["calculus_status"] = "requires_numerical_or_external_solver"
                    return FormulaResult(
                        status="unsupported",
                        original_text=trimmed,
                        latex=latex_str,
                        sympy_expr=str(lim_result),
                        error="Requires numerical methods or external solver (limit could not be evaluated symbolically).",
                        provenance=prov,
                    )

                prov["operation"] = "limit_evaluation"
                return FormulaResult(
                    status="calculated",
                    original_text=trimmed,
                    latex=latex_str,
                    sympy_expr=str(lim_result),
                    result_value=cls._to_native(lim_result),
                    provenance=prov,
                )
            except Exception as l_err:
                logger.debug("Calculus limit parse failed: %s", l_err)

        return None

    @classmethod
    def process_formula(
        cls,
        text: str | None,
        substitutions: dict[str, Any] | None = None,
        solve_for: str | None = None,
    ) -> FormulaResult:
        """Parse, verify, and deterministically calculate mathematical expressions via SymPy.

        Args:
            text: Formula string (e.g. 'F = m*a', 'sqrt(16) + 4', 'x^2 - 9 = 0').
            substitutions: Optional dict of variable values (e.g. {'m': 10, 'a': 9.8}).
            solve_for: Optional variable name to solve equation for (e.g. 'F' or 'x').

        Returns:
            FormulaResult with execution status, variables, numeric result, and provenance.
        """
        if not text or not text.strip():
            return FormulaResult(
                status="unsupported",
                original_text=text or "",
                error="Formula text is empty or blank.",
                provenance={"engine": "SymPy", "status": "unsupported"},
            )

        original_text = text.strip()
        latex_str, _ = cls.extract_formula_details(original_text)
        prov: dict[str, Any] = {
            "engine": "SymPy",
            "sympy_version": sympy.__version__,
            "operation": "symbolic_evaluation",
            "unit_verification": "unsupported_not_performed",
        }

        # 1. Security Check: Block unsafe Python execution attempts
        try:
            cls._sanitize_expression(original_text)
        except ValueError as sec_err:
            logger.warning("Rejected unsafe formula expression: %s", sec_err)
            return FormulaResult(
                status="unsupported",
                original_text=original_text,
                latex=latex_str,
                error=str(sec_err),
                provenance={"engine": "SymPy", "security": "rejected"},
            )

        # 2. Calculus & Equation Parsing vs Single Expression Parsing
        try:
            expr_to_parse = original_text
            if ":" in expr_to_parse and not expr_to_parse.startswith("http"):
                after_colon = expr_to_parse.split(":", 1)[1].strip()
                if after_colon and ("=" in after_colon or any(op in after_colon for op in "+-*/^") or "\\int" in after_colon or "derivative" in after_colon.lower()):
                    expr_to_parse = after_colon

            # Check for Calculus operations first
            calc_res = cls._try_evaluate_calculus(expr_to_parse, latex_str, prov)
            if calc_res is not None:
                return calc_res

            if "=" in expr_to_parse and not expr_to_parse.startswith("==") and not ("<=" in expr_to_parse or ">=" in expr_to_parse or "!=" in expr_to_parse):
                # Equation mode
                parts = expr_to_parse.split("=", 1)
                lhs_cleaned = cls._clean_for_sympy(parts[0])
                rhs_cleaned = cls._clean_for_sympy(parts[1])

                lhs_expr = parse_expr(lhs_cleaned, global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                rhs_expr = parse_expr(rhs_cleaned, global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                eq = sympy.Eq(lhs_expr, rhs_expr)

                free_syms = sorted([str(s) for s in eq.free_symbols])
                sympy_repr = str(eq)

                # Check if substitutions are provided
                if substitutions:
                    sub_dict = {sympy.Symbol(k): v for k, v in substitutions.items()}
                    sub_eq = eq.subs(sub_dict)

                    # Case A: Equation evaluated directly to True or False (all variables substituted)
                    if sub_eq in (True, sympy.true):
                        prov["operation"] = "equality_verification"
                        return FormulaResult(
                            status="calculated",
                            original_text=original_text,
                            latex=latex_str,
                            sympy_expr=sympy_repr,
                            variables=free_syms,
                            substitutions=substitutions,
                            result_value=True,
                            provenance=prov,
                        )
                    elif sub_eq in (False, sympy.false):
                        prov["operation"] = "equality_verification"
                        return FormulaResult(
                            status="verification_failed",
                            original_text=original_text,
                            latex=latex_str,
                            sympy_expr=sympy_repr,
                            variables=free_syms,
                            substitutions=substitutions,
                            result_value=False,
                            error="Verification failed: LHS != RHS after substitutions.",
                            provenance=prov,
                        )

                    remaining_symbols = sorted([str(s) for s in sub_eq.free_symbols])

                    # Case B: Solving for target variable or remaining variable
                    target_name = solve_for or (remaining_symbols[0] if len(remaining_symbols) == 1 else None)
                    if target_name and target_name in [str(s) for s in sub_eq.free_symbols]:
                        target_sym = sympy.Symbol(target_name)
                        solutions = sympy.solve(sub_eq, target_sym)
                        native_sols = cls._to_native(solutions)
                        res_val = native_sols[0] if len(native_sols) == 1 else native_sols

                        prov["operation"] = "equation_solution"
                        return FormulaResult(
                            status="calculated",
                            original_text=original_text,
                            latex=latex_str,
                            sympy_expr=sympy_repr,
                            variables=free_syms,
                            substitutions=substitutions,
                            result_value=res_val,
                            solved_for=target_name,
                            provenance=prov,
                        )

                # If solve_for requested without substitutions
                if solve_for and solve_for in free_syms:
                    target_sym = sympy.Symbol(solve_for)
                    solutions = sympy.solve(eq, target_sym)
                    prov["operation"] = "symbolic_solution"
                    return FormulaResult(
                        status="calculated",
                        original_text=original_text,
                        latex=latex_str,
                        sympy_expr=sympy_repr,
                        variables=free_syms,
                        result_value=cls._to_native(solutions),
                        solved_for=solve_for,
                        provenance=prov,
                    )

                # Pure equation parsed symbolically without complete calculation
                return FormulaResult(
                    status="parsed",
                    original_text=original_text,
                    latex=latex_str,
                    sympy_expr=sympy_repr,
                    variables=free_syms,
                    substitutions=substitutions,
                    provenance=prov,
                )

            else:
                # Expression mode (arithmetic, powers, roots)
                cleaned = cls._clean_for_sympy(expr_to_parse)
                expr = parse_expr(cleaned, global_dict=SAFE_SYMPY_GLOBALS, transformations=SAFE_TRANSFORMATIONS)
                free_syms = sorted([str(s) for s in expr.free_symbols])
                sympy_repr = str(expr)

                if substitutions:
                    sub_dict = {sympy.Symbol(k): v for k, v in substitutions.items()}
                    eval_expr = expr.subs(sub_dict)
                else:
                    eval_expr = expr

                # If no remaining free symbols, evaluate to numeric scalar
                if not eval_expr.free_symbols:
                    num_val = eval_expr.evalf()
                    prov["operation"] = "numeric_evaluation"
                    return FormulaResult(
                        status="calculated",
                        original_text=original_text,
                        latex=latex_str,
                        sympy_expr=sympy_repr,
                        variables=free_syms,
                        substitutions=substitutions,
                        result_value=cls._to_native(num_val),
                        provenance=prov,
                    )

                # Still has free symbols
                return FormulaResult(
                    status="parsed",
                    original_text=original_text,
                    latex=latex_str,
                    sympy_expr=sympy_repr,
                    variables=free_syms,
                    substitutions=substitutions,
                    result_value=str(eval_expr),
                    provenance=prov,
                )

        except Exception as exc:
            logger.info("SymPy formula processing could not parse '%s': %s", original_text, exc)
            return FormulaResult(
                status="unsupported",
                original_text=original_text,
                latex=latex_str,
                error=f"SymPy parsing failed: {exc}",
                provenance={"engine": "SymPy", "status": "unsupported"},
            )

    @classmethod
    def to_evidence_element(
        cls,
        result: FormulaResult,
        document_id: str,
        element_idx: int,
        page: int = 1,
        file_hash: str = "",
        bbox: list[float] | None = None,
    ) -> EvidenceElement:
        """Convert a FormulaResult into a canonical EvidenceElement."""
        conf = 1.0 if result.status in ("parsed", "calculated") else 0.50
        meta = {
            "formula_processing": result.to_dict(),
            "status": result.status,
            "sympy_expr": result.sympy_expr,
            "calculated_value": result.result_value,
            "solved_for": result.solved_for,
        }
        if result.error:
            meta["error"] = result.error

        return EvidenceBuilder.build_element(
            element_idx=element_idx,
            document_id=document_id,
            page=page,
            elem_type="formula",
            text=result.original_text,
            formula_latex=result.latex,
            formula_variables={v: (result.substitutions.get(v) if result.substitutions else None) for v in result.variables},
            bbox=bbox or [0.0, 0.0, 0.0, 0.0],
            confidence=conf,
            extraction_model="SymPy",
            file_hash=file_hash,
            metadata=meta,
        )


formula_extractor = FormulaExtractor()
