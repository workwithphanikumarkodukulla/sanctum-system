"""Deterministic mathematical computation tool for the Sanctum agent.

Provides secure, AST-validated symbolic and numeric mathematics using SymPy:
- Basic arithmetic & numerical evaluation
- Symbolic simplification, factoring, and expansion
- Differentiation (symbolic derivatives)
- Indefinite & definite integration
- Limits
- Equation solving
- Variable substitutions with provenance

Security invariants:
- Never uses eval(), exec(), or arbitrary Python execution.
- Multi-tier defense: token regex blocklist + Python AST structural validation + SymPy safe globals (__builtins__ = None).
- Returns structured results with operation, normalized_input, result, success, error, and backend metadata.
"""
from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy SymPy import
# ---------------------------------------------------------------------------
_sympy = None
_parse_expr = None
_SAFE_GLOBALS: dict[str, Any] | None = None
_SAFE_TRANSFORMATIONS: tuple | None = None


def _ensure_sympy() -> None:
    """Import SymPy and build the safe evaluation namespace on first use."""
    global _sympy, _parse_expr, _SAFE_GLOBALS, _SAFE_TRANSFORMATIONS
    if _sympy is not None:
        return

    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            convert_xor,
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )
    except ImportError:
        import sys
        from pathlib import Path
        candidate = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "sanctum-file-engine-code"
            / "venv"
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
        try:
            import sympy
            from sympy.parsing.sympy_parser import (
                convert_xor,
                implicit_multiplication_application,
                parse_expr,
                standard_transformations,
            )
        except ImportError as exc:
            raise RuntimeError(
                "SymPy is not installed. Install it with: pip install sympy"
            ) from exc

    _sympy = sympy
    _parse_expr = parse_expr
    _SAFE_GLOBALS = {
        "__builtins__": None,
        "Integer": sympy.Integer,
        "Float": sympy.Float,
        "Number": sympy.Number,
        "Symbol": sympy.Symbol,
        "Rational": sympy.Rational,
        "sqrt": sympy.sqrt,
        "cbrt": sympy.cbrt,
        "root": sympy.root,
        "Abs": sympy.Abs,
        "abs": sympy.Abs,
        "sin": sympy.sin,
        "cos": sympy.cos,
        "tan": sympy.tan,
        "cot": sympy.cot,
        "sec": sympy.sec,
        "csc": sympy.csc,
        "asin": sympy.asin,
        "acos": sympy.acos,
        "atan": sympy.atan,
        "atan2": sympy.atan2,
        "sinh": sympy.sinh,
        "cosh": sympy.cosh,
        "tanh": sympy.tanh,
        "log": sympy.log,
        "ln": sympy.log,
        "log10": lambda x: sympy.log(x, 10),
        "log2": lambda x: sympy.log(x, 2),
        "exp": sympy.exp,
        "pi": sympy.pi,
        "Eq": sympy.Eq,
        "symbols": sympy.symbols,
        "Pow": sympy.Pow,
        "Add": sympy.Add,
        "Mul": sympy.Mul,
        "diff": sympy.diff,
        "integrate": sympy.integrate,
        "limit": sympy.limit,
        "solve": sympy.solve,
        "simplify": sympy.simplify,
        "factor": sympy.factor,
        "expand": sympy.expand,
        "Derivative": sympy.Derivative,
        "Integral": sympy.Integral,
        "Limit": sympy.Limit,
        "oo": sympy.oo,
    }
    _SAFE_TRANSFORMATIONS = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )


# ---------------------------------------------------------------------------
# Security: Prohibited Tokens and AST Validation
# ---------------------------------------------------------------------------
UNSAFE_TOKEN_PATTERNS = [
    r"__",
    r"\bimport\b",
    r"\bexec\b",
    r"\beval\b",
    r"\bopen\b",
    r"\bos\b",
    r"\bsys\b",
    r"\bsubprocess\b",
    r"\bshutil\b",
    r"\bposix\b",
    r"\bnt\b",
    r"\bpty\b",
    r"\bcommands\b",
    r"\bplatform\b",
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
    r"\bbreakpoint\b",
    r"\binput\b",
    r"\bhelp\b",
    r"\bquit\b",
    r"\bexit\b",
    r"\bformat\b",
    r"\bvars\b",
    r"\bdir\b",
]

ALLOWED_AST_NODES = (
    ast.Expression,
    ast.Constant,
    ast.UnaryOp,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Name,
    ast.Load,
    ast.Call,
    ast.Tuple,
    ast.List,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)

ALLOWED_FUNCTION_NAMES = {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "asin", "acos", "atan", "atan2",
    "sinh", "cosh", "tanh",
    "exp", "log", "ln", "log10", "log2",
    "sqrt", "cbrt", "root", "Abs", "abs",
    "diff", "Derivative", "integrate", "Integral",
    "limit", "Limit", "solve", "Eq", "simplify",
    "factor", "expand", "pi", "E", "oo", "symbols",
    "Symbol", "Integer", "Float", "Rational",
}


class _SafeMathASTValidator(ast.NodeVisitor):
    """Walk Python AST to ensure only safe mathematical constructs exist."""

    def visit(self, node: ast.AST) -> None:
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError(f"Disallowed AST node: {type(node).__name__}")
        super().visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            raise ValueError(f"Attribute call not allowed: {node.func.attr}")
        else:
            raise ValueError("Disallowed call target.")

        if func_name not in ALLOWED_FUNCTION_NAMES:
            raise ValueError(f"Prohibited function call: '{func_name}'")

        self.generic_visit(node)


def _sanitize_expression(expr_str: str) -> None:
    """Reject attempts to execute arbitrary Python or shell code."""
    lower_expr = expr_str.lower()
    for pattern in UNSAFE_TOKEN_PATTERNS:
        if re.search(pattern, lower_expr):
            raise ValueError(
                f"Unsafe expression detected: prohibited token or keyword matching '{pattern}'."
            )
    if any(c in expr_str for c in [";", "`", "\n", "\r", "\t", "\x00"]):
        raise ValueError("Unsafe expression detected: prohibited delimiter character.")

    # Validate AST structure for non-LaTeX expressions
    if not any(token in expr_str for token in ["\\", "integral of", "derivative of", "limit of"]):
        pre_ast = expr_str.replace("^", "**")
        # Support equal sign in equations by replacing with == for AST verification
        if "=" in pre_ast and not any(op in pre_ast for op in ["==", "<=", ">=", "!="]):
            pre_ast = pre_ast.replace("=", "==")
        try:
            tree = ast.parse(pre_ast, mode="eval")
            _SafeMathASTValidator().visit(tree)
        except SyntaxError:
            # Let SymPy parser or cleanup deal with math syntax details if it's not AST-valid
            pass


def _clean_for_sympy(expr_str: str) -> str:
    """Convert math symbols, unicode, and LaTeX representations to SymPy syntax."""
    cleaned = expr_str.strip().strip("$")
    if cleaned.startswith("="):
        cleaned = cleaned.lstrip("=").strip()

    # Unicode superscripts -> **(digits)
    superscript_map = {
        "\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2074": "4",
        "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
        "\u207a": "+", "\u207b": "-",
    }
    cleaned = re.sub(
        r"([\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079])([0-9])",
        lambda m: m.group(1) if superscript_map.get(m.group(1)) == m.group(2) else m.group(0),
        cleaned,
    )
    cleaned = re.sub(
        r"([\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207a\u207b]+)",
        lambda m: f"**({''.join(superscript_map.get(c, c) for c in m.group(1))})",
        cleaned,
    )

    # Unicode math symbols
    cleaned = cleaned.replace("\u00d7", "*").replace("\u00f7", "/")
    cleaned = cleaned.replace("\u2212", "-").replace("\u2013", "-")

    # LaTeX operators
    cleaned = cleaned.replace("\\cdot", "*").replace("\\times", "*")
    cleaned = cleaned.replace("\\le", "<=").replace("\\ge", ">=")
    cleaned = cleaned.replace("\\ne", "!=").replace("\\pm", "+/-")

    # \frac{num}{den} -> ((num)/(den))
    for _ in range(5):
        if "\\frac" not in cleaned:
            break
        cleaned = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"((\1)/(\2))", cleaned)

    # \sqrt{x} -> sqrt(x)
    for _ in range(5):
        if "\\sqrt" not in cleaned:
            break
        cleaned = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", cleaned)

    # Remove backslashes from standard functions
    cleaned = re.sub(r"\\(sin|cos|tan|cot|sec|csc|asin|acos|atan|sinh|cosh|tanh|log|ln|exp|sqrt|pi|Abs)\b", r"\1", cleaned)

    # ^ -> **
    cleaned = cleaned.replace("^", "**")
    return cleaned


def _to_native(val: Any) -> Any:
    """Convert SymPy objects to native Python numeric or string values."""
    _ensure_sympy()
    if isinstance(val, (_sympy.Integer, int)):
        return int(val)
    if isinstance(val, (_sympy.Float, float)):
        f_val = float(val)
        return int(f_val) if f_val.is_integer() else round(f_val, 6)
    if isinstance(val, _sympy.Rational):
        f_val = float(val)
        return int(f_val) if f_val.is_integer() else round(f_val, 6)
    if isinstance(val, (list, tuple)):
        return [_to_native(x) for x in val]
    if isinstance(val, dict):
        return {str(k): _to_native(v) for k, v in val.items()}
    return str(val)


# ---------------------------------------------------------------------------
# Calculus & Advanced Operations
# ---------------------------------------------------------------------------
def _try_evaluate_calculus(
    text: str,
    prov: dict[str, Any],
) -> dict[str, Any] | None:
    """Detect and compute calculus operations (derivatives, integrals, limits)."""
    _ensure_sympy()
    trimmed = text.strip()

    # 1. Differentiation
    deriv_var = None
    deriv_expr_str = None

    m_deriv_text = re.search(
        r"(?i)^(?:find\s+(?:the\s+)?)?derivative\s+of\s+(.+?)(?:\s+with\s+respect\s+to\s+([a-zA-Z]))?$",
        trimmed,
    )
    m_deriv_op = re.search(
        r"^(?:\\\\?frac\{d\}\{d([a-zA-Z])\}|d\s*/\s*d([a-zA-Z]))\s*(?:[\(\[\{](.*?)[\)\]\}]|(?!\bwith\b)(.+?))$",
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
            cleaned = _clean_for_sympy(deriv_expr_str)
            expr = _parse_expr(cleaned, global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
            free_syms = sorted([str(s) for s in expr.free_symbols])
            target_var = _sympy.Symbol(deriv_var or (free_syms[0] if free_syms else "x"))
            deriv_result = _sympy.diff(expr, target_var)

            prov["operation"] = "differentiation"
            prov["differentiated_variable"] = str(target_var)
            norm_input = f"diff({expr}, {target_var})"

            return {
                "operation": "differentiation",
                "normalized_input": norm_input,
                "result": str(deriv_result),
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "differentiation"},
                "status": "success",
                "result_value": str(deriv_result),
                "sympy_expr": str(deriv_result),
                "variables": free_syms,
                "solved_for": f"d/d{target_var}",
                "provenance": prov,
            }
        except Exception as d_err:
            logger.debug("Differentiation failed: %s", d_err)

    # 2. Integration
    integ_lower = None
    integ_upper = None
    integ_expr_str = None
    integ_var = None

    # Syntax: integrate(x**2, (x, 0, 3))
    m_integrate_def_call = re.search(
        r"^integrate\s*\(\s*(.+?)\s*,\s*\(\s*([a-zA-Z])\s*,\s*([0-9a-zA-Z.\-+/*]+)\s*,\s*([0-9a-zA-Z.\-+/*]+)\s*\)\s*\)$",
        trimmed,
    )
    # Syntax: integrate(x**2, x)
    m_integrate_indef_call = re.search(
        r"^integrate\s*\(\s*(.+?)(?:\s*,\s*([a-zA-Z]))?\s*\)$",
        trimmed,
    )
    m_def_latex = re.search(
        r"(?:\\\\int|\\int)_\{?([0-9a-zA-Z.\-+/*]+)\}?\^\{?([0-9a-zA-Z.\-+/*]+)\}?\s+(.+?)\s*d([a-zA-Z])\b",
        trimmed,
    )
    m_def_text = re.search(
        r"(?i)^(?:evaluate\s+|calculate\s+)?integral\s+of\s+(.+?)\s+from\s+([0-9a-zA-Z.\-+/*]+)\s+to\s+([0-9a-zA-Z.\-+/*]+)(?:\s+with\s+respect\s+to\s+([a-zA-Z]))?$",
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

    if m_integrate_def_call:
        integ_expr_str, integ_var, integ_lower, integ_upper = m_integrate_def_call.groups()
    elif m_integrate_indef_call:
        integ_expr_str, integ_var = m_integrate_indef_call.groups()
    elif m_def_latex:
        integ_lower, integ_upper, integ_expr_str, integ_var = m_def_latex.groups()
    elif m_def_text:
        integ_expr_str, integ_lower, integ_upper, integ_var = m_def_text.groups()
    elif m_indef_latex:
        integ_expr_str, integ_var = m_indef_latex.groups()
    elif m_indef_text:
        integ_expr_str, integ_var = m_indef_text.groups()

    if integ_expr_str is not None:
        try:
            cleaned = _clean_for_sympy(integ_expr_str)
            expr = _parse_expr(cleaned, global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
            free_syms = sorted([str(s) for s in expr.free_symbols])
            target_var = _sympy.Symbol(integ_var or (free_syms[0] if free_syms else "x"))

            if integ_lower is not None and integ_upper is not None:
                low_val = _parse_expr(_clean_for_sympy(integ_lower), global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
                high_val = _parse_expr(_clean_for_sympy(integ_upper), global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
                integ_result = _sympy.integrate(expr, (target_var, low_val, high_val))
                op_name = "definite_integration"
                norm_input = f"integrate({expr}, ({target_var}, {low_val}, {high_val}))"
            else:
                integ_result = _sympy.integrate(expr, target_var)
                op_name = "indefinite_integration"
                norm_input = f"integrate({expr}, {target_var})"

            prov["operation"] = op_name
            native_val = _to_native(integ_result) if (integ_lower and not getattr(integ_result, "free_symbols", None)) else str(integ_result)

            return {
                "operation": op_name,
                "normalized_input": norm_input,
                "result": native_val,
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": op_name},
                "status": "success",
                "result_value": native_val,
                "sympy_expr": str(integ_result),
                "variables": free_syms,
                "provenance": prov,
            }
        except Exception as i_err:
            logger.debug("Integration failed: %s", i_err)

    # 3. Limits
    m_lim_call = re.search(
        r"^limit\s*\(\s*(.+?)\s*,\s*([a-zA-Z])\s*,\s*([0-9a-zA-Z.\-+/*]+)\s*\)$",
        trimmed,
    )
    m_lim_text = re.search(
        r"(?i)^(?:find\s+|calculate\s+)?limit\s+of\s+(.+?)\s+(?:as|when)\s+([a-zA-Z])\s*(?:\\to|->|approaches)\s*([0-9a-zA-Z.\-+/*]+)$",
        trimmed,
    )
    m_lim_latex = re.search(
        r"(?:\\\\lim|\\lim)_\{?([a-zA-Z])\s*(?:\\to|->)\s*([0-9a-zA-Z.\-+/*]+)\}?\s*(.+)$",
        trimmed,
    )

    lim_var = None
    lim_target = None
    lim_expr = None

    if m_lim_call:
        lim_expr, lim_var, lim_target = m_lim_call.groups()
    elif m_lim_text:
        lim_expr, lim_var, lim_target = m_lim_text.groups()
    elif m_lim_latex:
        lim_var, lim_target, lim_expr = m_lim_latex.groups()

    if lim_expr is not None:
        try:
            cleaned = _clean_for_sympy(lim_expr)
            expr = _parse_expr(cleaned, global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
            target_sym = _sympy.Symbol(lim_var)
            target_val = _parse_expr(_clean_for_sympy(lim_target), global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
            lim_result = _sympy.limit(expr, target_sym, target_val)

            prov["operation"] = "limit"
            norm_input = f"limit({expr}, {target_sym}, {target_val})"
            res_val = _to_native(lim_result)

            return {
                "operation": "limit",
                "normalized_input": norm_input,
                "result": res_val,
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "limit"},
                "status": "success",
                "result_value": res_val,
                "sympy_expr": str(lim_result),
                "provenance": prov,
            }
        except Exception as l_err:
            logger.debug("Limit evaluation failed: %s", l_err)

    return None


# ---------------------------------------------------------------------------
# Primary Computation Dispatcher
# ---------------------------------------------------------------------------
def process_formula(
    text: str | None,
    substitutions: dict[str, Any] | None = None,
    solve_for: str | None = None,
    operation: str | None = None,
    limits: list[Any] | tuple[Any, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically parse and evaluate mathematical expressions via SymPy.

    Args:
        text: Mathematical expression (e.g. '2 + 2', 'diff(x**3, x)', 'x^2 - 16 = 0').
        substitutions: Optional dict of variable substitutions.
        solve_for: Optional variable to solve for.
        operation: Optional explicit operation override ('simplify', 'diff', 'integrate', 'limit', 'solve').
        limits: Optional [lower, upper] limits for definite integration.

    Returns:
        Structured result dict containing operation, normalized_input, result, success,
        error, deterministic, and backend metadata.
    """
    _ensure_sympy()

    if not text or not text.strip():
        return {
            "operation": "unknown",
            "normalized_input": text or "",
            "result": None,
            "success": False,
            "error": "Formula or mathematical expression cannot be empty.",
            "deterministic": True,
            "backend": {"engine": "SymPy", "status": "empty"},
            "status": "error",
            "result_value": None,
            "provenance": {"engine": "SymPy", "status": "empty"},
        }

    original_text = text.strip()

    # LaTeX display representation
    latex_str = original_text
    if not (latex_str.startswith("$") or "\\" in latex_str):
        for orig, rep in [
            (" * ", " \\cdot "), ("<=", " \\le "), (">=", " \\ge "),
            ("!=", " \\ne "), ("+/-", " \\pm "), ("sqrt", "\\sqrt"),
            ("pi", "\\pi"),
        ]:
            latex_str = latex_str.replace(orig, rep)

    prov: dict[str, Any] = {
        "engine": "SymPy",
        "sympy_version": _sympy.__version__,
        "operation": operation or "symbolic_evaluation",
    }

    # Security check: regex + AST validation
    try:
        _sanitize_expression(original_text)
    except ValueError as sec_err:
        logger.warning("Blocked unsafe expression: %s", sec_err)
        return {
            "operation": "security_violation",
            "normalized_input": original_text,
            "result": None,
            "success": False,
            "error": str(sec_err),
            "deterministic": True,
            "backend": {"engine": "SymPy", "security": "rejected"},
            "status": "unsupported",
            "result_value": None,
            "provenance": {"engine": "SymPy", "security": "rejected"},
        }

    # Validate substitutions
    if substitutions:
        if not isinstance(substitutions, dict):
            return {
                "operation": "unknown",
                "normalized_input": original_text,
                "result": None,
                "success": False,
                "error": "Substitutions must be a dictionary or valid JSON mapping.",
                "deterministic": True,
                "backend": {"engine": "SymPy"},
                "status": "error",
            }
        for k, v in substitutions.items():
            if not isinstance(k, str) or not k.isidentifier() or "__" in k or any(re.search(p, k.lower()) for p in UNSAFE_TOKEN_PATTERNS):
                return {
                    "operation": "security_violation",
                    "normalized_input": original_text,
                    "result": None,
                    "success": False,
                    "error": f"Security violation: unsafe substitution key '{k}'",
                    "deterministic": True,
                    "backend": {"engine": "SymPy", "security": "rejected"},
                    "status": "unsupported",
                }
            if not isinstance(v, (int, float, bool)) and not (isinstance(v, str) and re.match(r"^[0-9a-zA-Z.\-+/*^() ]+$", v)):
                return {
                    "operation": "security_violation",
                    "normalized_input": original_text,
                    "result": None,
                    "success": False,
                    "error": f"Security violation: unsafe substitution value for '{k}'",
                    "deterministic": True,
                    "backend": {"engine": "SymPy", "security": "rejected"},
                    "status": "unsupported",
                }

    try:
        expr_to_parse = original_text

        # Check for explicit unsupported operation
        KNOWN_OPERATIONS = {
            "arithmetic", "eval", "evaluate", "simplify", "diff", "derivative", "differentiation",
            "integrate", "integral", "indefinite_integration", "definite_integral", "definite_integration",
            "limit", "solve", "equation_solving", "symbolic_evaluation",
        }
        if operation and operation.lower() not in KNOWN_OPERATIONS:
            return {
                "operation": "unsupported",
                "normalized_input": original_text,
                "result": None,
                "success": False,
                "error": f"Unsupported mathematical operation: '{operation}'",
                "deterministic": True,
                "backend": {"engine": "SymPy", "status": "unsupported"},
                "status": "unsupported",
                "result_value": None,
                "provenance": {"engine": "SymPy", "status": "unsupported"},
            }

        # Check for non-mathematical plain natural language sentences
        words = original_text.split()
        if len(words) >= 3 and not any(c in original_text for c in "+-*/=^()\\_0123456789"):
            return {
                "operation": "unsupported",
                "normalized_input": original_text,
                "result": None,
                "success": False,
                "error": f"Unsupported operation or non-mathematical text: '{original_text}'",
                "deterministic": True,
                "backend": {"engine": "SymPy", "status": "unsupported"},
                "status": "unsupported",
                "result_value": None,
                "provenance": {"engine": "SymPy", "status": "unsupported"},
            }

        # Explicit operation routing
        if operation in ("diff", "derivative", "differentiation"):
            var_sym = solve_for or "x"
            m_unwrap = re.search(
                r"^(?:\\\\?frac\{d\}\{d([a-zA-Z])\}|d\s*/\s*d([a-zA-Z]))\s*(?:[\(\[\{](.*?)[\)\]\}]|(.+?))$",
                expr_to_parse.strip(),
            )
            if m_unwrap:
                var_sym = m_unwrap.group(1) or m_unwrap.group(2) or var_sym
                inner_raw = m_unwrap.group(3) if m_unwrap.group(3) is not None else m_unwrap.group(4)
                if inner_raw:
                    expr_to_parse = inner_raw.strip()
            cleaned = _clean_for_sympy(expr_to_parse)
            parsed_expr = _parse_expr(cleaned, global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
            diff_res = _sympy.diff(parsed_expr, _sympy.Symbol(var_sym))
            free_syms = sorted([str(s) for s in diff_res.free_symbols])
            res_val = str(diff_res)
            return {
                "operation": "differentiation",
                "normalized_input": f"diff({parsed_expr}, {var_sym})",
                "result": res_val,
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "differentiation"},
                "status": "success",
                "result_value": res_val,
                "sympy_expr": str(diff_res),
                "variables": free_syms,
                "provenance": prov,
            }

        if operation in ("integrate", "integral", "indefinite_integration"):
            var_sym = solve_for or "x"
            cleaned = _clean_for_sympy(expr_to_parse)
            parsed_expr = _parse_expr(cleaned, global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
            if limits and len(limits) == 2:
                int_res = _sympy.integrate(parsed_expr, (_sympy.Symbol(var_sym), limits[0], limits[1]))
            else:
                int_res = _sympy.integrate(parsed_expr, _sympy.Symbol(var_sym))
            free_syms = sorted([str(s) for s in int_res.free_symbols])
            res_val = str(int_res)
            return {
                "operation": "definite_integral" if limits else "indefinite_integration",
                "normalized_input": f"integrate({parsed_expr}, {var_sym})",
                "result": res_val,
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "integration"},
                "status": "success",
                "result_value": res_val,
                "sympy_expr": str(int_res),
                "variables": free_syms,
                "provenance": prov,
            }

        if operation == "simplify" or expr_to_parse.startswith("simplify(") and expr_to_parse.endswith(")"):
            inner = expr_to_parse[9:-1] if expr_to_parse.startswith("simplify(") else expr_to_parse
            cleaned = _clean_for_sympy(inner)
            parsed_expr = _parse_expr(cleaned, global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
            simplified = _sympy.simplify(parsed_expr)
            free_syms = sorted([str(s) for s in simplified.free_symbols])
            res_val = _to_native(simplified) if not free_syms else str(simplified)
            return {
                "operation": "simplification",
                "normalized_input": f"simplify({parsed_expr})",
                "result": res_val,
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "simplification"},
                "status": "success",
                "result_value": res_val,
                "sympy_expr": str(simplified),
                "variables": free_syms,
                "provenance": prov,
            }

        # Check calculus (derivatives, integrals, limits)
        calc_res = _try_evaluate_calculus(expr_to_parse, prov)
        if calc_res is not None:
            return calc_res

        # Check equation solving (contains single '=' or explicit solve)
        is_equation = (
            ("=" in expr_to_parse and not any(op in expr_to_parse for op in ["==", "<=", ">=", "!="]))
            or (expr_to_parse.startswith("solve(") and expr_to_parse.endswith(")"))
            or (operation == "solve")
        )

        if is_equation:
            eq_text = expr_to_parse
            target_var = solve_for

            if eq_text.startswith("solve(") and eq_text.endswith(")"):
                inner = eq_text[6:-1]
                parts = [p.strip() for p in inner.split(",")]
                eq_text = parts[0]
                if len(parts) > 1 and not target_var:
                    target_var = parts[1]

            if "=" in eq_text:
                lhs_str, rhs_str = eq_text.split("=", 1)
                lhs = _parse_expr(_clean_for_sympy(lhs_str), global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
                rhs = _parse_expr(_clean_for_sympy(rhs_str), global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
                eq = _sympy.Eq(lhs, rhs)
            else:
                expr = _parse_expr(_clean_for_sympy(eq_text), global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
                eq = _sympy.Eq(expr, 0)

            free_syms = sorted([str(s) for s in eq.free_symbols])
            target_sym = _sympy.Symbol(target_var or (free_syms[0] if free_syms else "x"))

            if substitutions:
                sub_dict = {_sympy.Symbol(k): v for k, v in substitutions.items()}
                eq = eq.subs(sub_dict)
                remaining_syms = sorted([str(s) for s in eq.free_symbols])
                if remaining_syms and target_var not in remaining_syms:
                    target_sym = _sympy.Symbol(remaining_syms[0])

            solutions = _sympy.solve(eq, target_sym)
            native_solutions = _to_native(solutions)
            sol_val = native_solutions[0] if (isinstance(native_solutions, list) and len(native_solutions) == 1) else native_solutions

            return {
                "operation": "equation_solving",
                "normalized_input": f"solve({eq}, {target_sym})",
                "result": sol_val,
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "equation_solving"},
                "status": "success",
                "result_value": sol_val,
                "sympy_expr": str(eq),
                "variables": free_syms,
                "solved_for": str(target_sym),
                "provenance": prov,
            }

        # Standard arithmetic / algebraic evaluation
        cleaned = _clean_for_sympy(expr_to_parse)
        expr = _parse_expr(cleaned, global_dict=_SAFE_GLOBALS, transformations=_SAFE_TRANSFORMATIONS)
        free_syms = sorted([str(s) for s in expr.free_symbols])

        if substitutions:
            sub_dict = {_sympy.Symbol(k): v for k, v in substitutions.items()}
            eval_expr = expr.subs(sub_dict)
        else:
            eval_expr = expr

        if not eval_expr.free_symbols:
            if eval_expr == _sympy.zoo or str(eval_expr) == "zoo":
                return {
                    "operation": "arithmetic",
                    "normalized_input": str(eval_expr),
                    "result": None,
                    "success": False,
                    "error": "Division by zero is undefined (complex infinity: zoo).",
                    "deterministic": True,
                    "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "arithmetic"},
                    "status": "error",
                    "result_value": None,
                    "provenance": prov,
                }
            if eval_expr == _sympy.nan or str(eval_expr) == "nan":
                return {
                    "operation": "arithmetic",
                    "normalized_input": str(eval_expr),
                    "result": None,
                    "success": False,
                    "error": "Expression evaluates to an indeterminate form (NaN).",
                    "deterministic": True,
                    "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "arithmetic"},
                    "status": "error",
                    "result_value": None,
                    "provenance": prov,
                }

            num_val = _to_native(eval_expr.evalf())
            op_name = "arithmetic"
            return {
                "operation": op_name,
                "normalized_input": str(eval_expr),
                "result": num_val,
                "success": True,
                "error": None,
                "deterministic": True,
                "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": op_name},
                "status": "success",
                "result_value": num_val,
                "sympy_expr": str(eval_expr),
                "variables": free_syms,
                "substitutions": substitutions,
                "provenance": prov,
            }

        # Symbolic representation
        return {
            "operation": "symbolic_evaluation",
            "normalized_input": str(eval_expr),
            "result": str(eval_expr),
            "success": True,
            "error": None,
            "deterministic": True,
            "backend": {"engine": "SymPy", "version": _sympy.__version__, "operation": "symbolic_evaluation"},
            "status": "success",
            "result_value": str(eval_expr),
            "sympy_expr": str(eval_expr),
            "variables": free_syms,
            "substitutions": substitutions,
            "provenance": prov,
        }

    except SyntaxError as syn_err:
        return {
            "operation": "malformed_expression",
            "normalized_input": original_text,
            "result": None,
            "success": False,
            "error": f"Malformed expression: Syntax error parsing '{original_text}': {syn_err}",
            "deterministic": True,
            "backend": {"engine": "SymPy", "status": "error"},
            "status": "error",
            "result_value": None,
            "provenance": {"engine": "SymPy", "status": "error"},
        }
    except Exception as exc:
        logger.info("SymPy computation failed for '%s': %s", original_text, exc)
        err_msg = str(exc)
        is_malformed = any(s in err_msg.lower() for s in ["syntax", "token", "parenthes", "bracket", "unexpected", "cannot parse"])
        op_name = "malformed_expression" if is_malformed else "unsupported"

        return {
            "operation": op_name,
            "normalized_input": original_text,
            "result": None,
            "success": False,
            "error": f"Unsupported operation or parse error: {exc}",
            "deterministic": True,
            "backend": {"engine": "SymPy", "status": op_name},
            "status": "error" if is_malformed else "unsupported",
            "result_value": None,
            "provenance": {"engine": "SymPy", "status": op_name},
        }


# ---------------------------------------------------------------------------
# BaseTool Implementation & Aliases
# ---------------------------------------------------------------------------
class MathTool(BaseTool):
    """Deterministic mathematical computation using SymPy.

    Supports arithmetic, differentiation, indefinite and definite integration,
    limits, equation solving, and symbolic simplification without eval().
    """

    name = "math"
    description = (
        "Deterministic mathematical computation using SymPy. Safely evaluates arithmetic, "
        "derivatives, integrals, limits, equations, and formula substitutions without eval()."
    )

    def execute(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute a deterministic mathematical computation.

        Keyword Args:
            expression (str): Expression to evaluate (e.g. '2 + 2', 'diff(x**3, x)', 'integrate(x**2, (x, 0, 3))').
            substitutions (dict | str): Optional dict or JSON mapping variable names to numeric values.
            solve_for (str): Optional variable name to solve an equation for.
            operation (str): Optional explicit operation ('simplify', 'diff', 'integrate', 'limit', 'solve').
            limits (list | tuple): Optional [lower, upper] bounds for definite integrals.
        """
        expression = kwargs.get("expression")
        if expression is None and args:
            expression = args[0]
        if not expression:
            return {
                "operation": "unknown",
                "normalized_input": "",
                "result": None,
                "success": False,
                "error": "Parameter 'expression' is required.",
                "deterministic": True,
                "backend": {"engine": "SymPy"},
                "status": "error",
            }

        substitutions = kwargs.get("substitutions")
        if isinstance(substitutions, str) and substitutions.strip():
            try:
                substitutions = json.loads(substitutions)
            except (json.JSONDecodeError, TypeError):
                substitutions = None

        solve_for = kwargs.get("solve_for")
        if isinstance(solve_for, str) and not solve_for.strip():
            solve_for = None

        operation = kwargs.get("operation")
        limits = kwargs.get("limits")

        return process_formula(
            text=str(expression),
            substitutions=substitutions,
            solve_for=solve_for,
            operation=operation,
            limits=limits,
        )


class SymPyTool(MathTool):
    """Alias for MathTool under name='sympy' for backward compatibility."""

    name = "sympy"
    description = (
        "Deterministic mathematical computation using SymPy. Safely evaluates arithmetic, "
        "derivatives, integrals, limits, equations, and formula substitutions."
    )
