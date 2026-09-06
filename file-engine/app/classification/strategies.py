"""Modular classification strategies for document regions and content elements."""
from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable
from PIL import Image

from app.classification.models import ClassificationResult, ContentType
from app.extractors.handwriting import HandwritingClassification, handwriting_classifier


@runtime_checkable
class ClassificationStrategy(Protocol):
    """Protocol for pluggable content classification strategies."""

    strategy_name: str

    def can_classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> bool:
        """Return True if this strategy has sufficient signals to evaluate."""
        ...

    def classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> ClassificationResult | None:
        """Classify the input region or element into a ClassificationResult."""
        ...


class MetadataClassificationStrategy:
    """Classifies regions using deterministic native parser and DOM metadata."""

    strategy_name: str = "metadata_strategy"

    def can_classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> bool:
        return bool(metadata)

    def classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> ClassificationResult | None:
        if not metadata:
            return None

        # 1. Native table detection
        if (
            metadata.get("is_table")
            or metadata.get("table_data") is not None
            or metadata.get("source") in ("docx_table", "pptx_table", "xlsx", "csv")
            or metadata.get("total_rows") is not None
        ):
            return ClassificationResult(
                content_type=ContentType.TABLE,
                confidence=1.0,
                reason="Native spreadsheet or structured table metadata from parser DOM.",
                metadata={"strategy": self.strategy_name, "parser_source": metadata.get("source")},
            )

        # 2. Native formula detection
        if (
            metadata.get("is_formula")
            or metadata.get("formula_latex") is not None
            or metadata.get("formula_variables") is not None
            or (text and text.strip().startswith("=") and len(text.strip()) > 1)
        ):
            return ClassificationResult(
                content_type=ContentType.FORMULA,
                confidence=1.0,
                reason="Native spreadsheet formula or parsed LaTeX expression in metadata.",
                metadata={"strategy": self.strategy_name, "formula_expr": text},
            )

        # 3. Native image shape / figure
        shape_type = str(metadata.get("shape_type", "")).upper()
        if (
            "PICTURE" in shape_type
            or metadata.get("is_image")
            or metadata.get("source") in ("pptx_image", "image")
            or metadata.get("elem_type") == "image"
        ):
            return ClassificationResult(
                content_type=ContentType.IMAGE,
                confidence=1.0,
                reason="Native embedded picture shape or raster element from document DOM.",
                metadata={"strategy": self.strategy_name, "shape_type": shape_type},
            )

        # 4. Native heading / title
        if metadata.get("is_heading") or metadata.get("is_title") or metadata.get("heading_level") is not None:
            return ClassificationResult(
                content_type=ContentType.TEXT,
                confidence=1.0,
                reason="Native document heading element with defined style level.",
                metadata={"strategy": self.strategy_name, "heading_level": metadata.get("heading_level"), "is_heading": True},
            )

        # 5. Native list element
        if metadata.get("is_list"):
            return ClassificationResult(
                content_type=ContentType.TEXT,
                confidence=1.0,
                reason="Native bulleted or numbered list element from document DOM.",
                metadata={"strategy": self.strategy_name, "is_list": True},
            )

        return None


class TextPatternClassificationStrategy:
    """Classifies regions using deterministic textual syntax, math tokens, and layout patterns."""

    strategy_name: str = "text_pattern_strategy"

    # Regex patterns
    LATEX_KEYWORDS = {
        "\\frac", "\\sqrt", "\\sum", "\\int", "\\partial", "\\begin{equation}",
        "\\cdot", "\\pm", "\\alpha", "\\beta", "\\theta", "\\gamma", "\\sigma",
        "\\mu", "\\times", "\\le", "\\ge", "\\ne", "\\infty", "\\Delta", "\\nabla"
    }
    MATH_UNICODE_SYMBOLS = {"∑", "∫", "∏", "√", "±", "≠", "≤", "≥", "≈", "∈", "∉", "∂", "∇", "λ", "θ", "π"}
    PID_TAG_PATTERN = re.compile(
        r"\b(?:FCV|PCV|TCV|LCV|PT|TT|LT|FT|PI|TI|LI|FI|MOV|XV|PSV|RV|P|TK|HEX|E)-[0-9]{2,4}[A-Z]?\b"
    )
    DIAGRAM_KEYWORDS = [
        "p&id", "piping and instrumentation", "process flow diagram",
        "schematic", "circuit diagram", "single line diagram", "isa-5.1"
    ]

    def can_classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> bool:
        return bool(text and text.strip())

    def classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> ClassificationResult | None:
        if not text or not text.strip():
            return None

        cleaned = text.strip()
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        # 1. Spreadsheet formula check (e.g. =SUM(B2:B10) or =A1+B1)
        if cleaned.startswith("=") and len(cleaned) > 1 and re.match(r"^=[A-Za-z0-9_]+", cleaned):
            return ClassificationResult(
                content_type=ContentType.FORMULA,
                confidence=0.98,
                reason="Spreadsheet formula syntax detected.",
                metadata={"strategy": self.strategy_name, "formula_expr": cleaned},
            )

        # 2. Table detection: Markdown pipes or tab-delimited structures
        pipe_lines = [l for l in lines if l.startswith("|") and l.endswith("|") and l.count("|") >= 2]
        if len(pipe_lines) >= 2:
            return ClassificationResult(
                content_type=ContentType.TABLE,
                confidence=0.95,
                reason="Markdown pipe table structure detected across multiple lines.",
                metadata={"strategy": self.strategy_name, "pipe_row_count": len(pipe_lines)},
            )

        tab_lines = [l for l in lines if "\t" in l and len(l.split("\t")) >= 2]
        if len(tab_lines) >= 2:
            return ClassificationResult(
                content_type=ContentType.TABLE,
                confidence=0.90,
                reason="Tab-delimited tabular rows detected across multiple lines.",
                metadata={"strategy": self.strategy_name, "tab_row_count": len(tab_lines)},
            )

        # Multi-space aligned columns (at least 3 lines with 2+ columns separated by 2+ spaces)
        space_col_lines = [l for l in lines if len(re.split(r"\s{2,}", l)) >= 2]
        if len(space_col_lines) >= 3 and len(lines) <= len(space_col_lines) + 1:
            return ClassificationResult(
                content_type=ContentType.TABLE,
                confidence=0.82,
                reason="Multi-column whitespace-aligned rows detected.",
                metadata={"strategy": self.strategy_name, "aligned_row_count": len(space_col_lines)},
            )

        # 3. Formula detection: multi-signal analysis (LaTeX, Unicode math, calculus, polynomial equations)
        has_latex = any(kw in cleaned for kw in self.LATEX_KEYWORDS) or (cleaned.startswith("$") and cleaned.endswith("$"))
        math_symbol_count = sum(1 for sym in self.MATH_UNICODE_SYMBOLS if sym in cleaned)

        # Detect clear calculus patterns:
        # e.g. "d/dx (x³ + 2x² - 5x + 1)", "d/dx(...)", "∫ x² dx", "lim_{x->0}"
        has_calculus = (
            bool(re.search(r"\b(?:d/d[a-z]|d[a-z]/d[a-z])\s*[\(\[]", cleaned))
            or bool(re.search(r"∫\s*[^;\n]+\s*d[a-z]", cleaned))
            or bool(re.search(r"\b(?:lim|limit)\s*[\{\(]?[a-z]\s*(?:->|\\to)", cleaned, re.IGNORECASE))
        )

        # Detect mathematical equation patterns:
        # e.g. "x² - 5x + 6 = 0", "F = m*a", "2 * 150 + 50", "a^2 + b^2 = c^2"
        # Superscript exponents e.g. x², x³
        has_superscript_math = bool(re.search(r"[a-zA-Z][⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+", cleaned))

        has_equation_structure = (
            # Variable equated to arithmetic expression: e.g. F = m*a, y = 2x + 1
            bool(re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*=\s*[^=\n]*[\+\-\*\/\^][^=\n]*", cleaned))
            # Polynomial equated to 0 or number: e.g. x^2 - 5x + 6 = 0, x² - 5x + 6 = 0
            or bool(re.search(r"(?:[a-zA-Z][\^²³⁴⁵⁶⁷⁸⁹0-9]*\s*[\+\-]\s*)+[a-zA-Z0-9\s\*\/\^²³⁴⁵⁶⁷⁸⁹\.]+\s*=\s*[-+]?\d+", cleaned))
            # Variable assigned to numbers/operations: e.g. x = 5, A = 100
            or bool(re.search(r"\b[A-Za-z]\s*=\s*[\d\.\-+*/\(\)]+", cleaned))
            # Standalone arithmetic expression: e.g. 2 * 150 + 50, 10 + 20 / 2
            or bool(re.match(r"^\s*[-+]?\d+(?:\.\d+)?(?:\s*[\+\-\*\/\^]\s*[-+]?\d+(?:\.\d+)?)+\s*$", cleaned))
        )

        # Guard against ordinary technical prose (e.g. "The pressure was 120 MPa", "Flow rate was 450 gpm")
        # and ordinary prose with math words (e.g. "Please solve the equation tomorrow", "We will differentiate the products")
        is_pure_technical_spec = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:MPa|kPa|psi|bar|gpm|kg|lb|m/s|kW|MW|Hz|V|A|C|K)\b", cleaned)) and not (has_latex or has_calculus or "=" in cleaned)
        is_prose_sentence = bool(re.search(r"\b(?:please|tomorrow|meeting|yesterday|welcome|thank|regards|sincerely|review|report)\b", cleaned, re.IGNORECASE)) and not (has_latex or "=" in cleaned or has_calculus)

        is_formula = (
            not is_pure_technical_spec
            and not is_prose_sentence
            and (
                has_latex
                or has_calculus
                or (has_superscript_math and ("=" in cleaned or any(op in cleaned for op in ("+", "-", "*", "/"))))
                or math_symbol_count >= 2
                or (math_symbol_count >= 1 and has_equation_structure)
                or has_equation_structure
            )
        )

        if is_formula:
            # Deterministic, signal-based confidence scoring
            signal_score = 0.85
            if has_latex:
                signal_score += 0.10
            if has_calculus:
                signal_score += 0.08
            if math_symbol_count >= 2:
                signal_score += 0.05
            if "=" in cleaned:
                signal_score += 0.04
            formula_conf = min(0.99, max(0.85, round(signal_score, 4)))

            return ClassificationResult(
                content_type=ContentType.FORMULA,
                confidence=formula_conf,
                reason="LaTeX syntax, calculus operator, Unicode math symbol, or equation structure detected.",
                metadata={
                    "strategy": self.strategy_name,
                    "latex_detected": has_latex,
                    "calculus_detected": has_calculus,
                    "math_symbol_count": math_symbol_count,
                    "has_equation": "=" in cleaned,
                },
            )

        # 4. Technical Drawing / P&ID Diagram check
        lower_text = cleaned.lower()
        pid_matches = self.PID_TAG_PATTERN.findall(cleaned)
        has_diagram_kw = any(kw in lower_text for kw in self.DIAGRAM_KEYWORDS)

        if has_diagram_kw or len(pid_matches) >= 2:
            return ClassificationResult(
                content_type=ContentType.DIAGRAM,
                confidence=0.92 if (has_diagram_kw and pid_matches) else 0.85,
                reason="Technical drawing, schematic keyword, or P&ID instrumentation tag detected.",
                metadata={
                    "strategy": self.strategy_name,
                    "pid_tags": pid_matches,
                    "diagram_keywords": [kw for kw in self.DIAGRAM_KEYWORDS if kw in lower_text],
                },
            )

        # Check if region is verified native digital text (from PPTX, DOCX, digital PDF DOM)
        is_native_digital = bool(
            metadata
            and (
                metadata.get("is_native_text")
                or metadata.get("source") == "pptx"
                or metadata.get("parser_source") == "pptx"
                or metadata.get("extraction_model") == "python-pptx"
                or (metadata.get("is_digital") and image is None and metadata.get("elem_type") != "handwriting")
            )
            and not (metadata.get("elem_type") == "handwriting" or metadata.get("type") == "handwriting")
        )

        # 5. Handwriting artifact detection via HandwritingClassifier
        # CRITICAL: Native digital text has already been extracted digitally from document DOM
        # and MUST NOT be subjected to OCR substitution heuristics (e.g. CamelCase, dashes).
        if not is_native_digital:
            ocr_confidence = float((metadata or {}).get("confidence", 1.0))
            hw_decision = handwriting_classifier.classify_region(
                crop=image,
                text=cleaned,
                confidence=ocr_confidence,
                metadata=metadata,
            )

            if (
                hw_decision.classification == HandwritingClassification.HANDWRITTEN
                or (metadata or {}).get("elem_type") == "handwriting"
                or (metadata or {}).get("type") == "handwriting"
                or (metadata or {}).get("consensus") == "conflicted"
                or (metadata or {}).get("handwriting_checked") is True
            ):
                return ClassificationResult(
                    content_type=ContentType.HANDWRITING,
                    confidence=hw_decision.confidence,
                    reason=hw_decision.reason,
                    metadata={
                        "strategy": self.strategy_name,
                        "handwriting_decision": hw_decision.to_dict(),
                        "ocr_confidence": ocr_confidence,
                    },
                )

            # 6. Degraded / faint print or uncertain handwriting signal
            if (
                hw_decision.classification == HandwritingClassification.UNCERTAIN
                or (metadata or {}).get("uncertain_handwriting")
            ):
                return ClassificationResult(
                    content_type=ContentType.TEXT,
                    confidence=hw_decision.confidence,
                    reason=hw_decision.reason,
                    metadata={
                        "strategy": self.strategy_name,
                        "handwriting_decision": hw_decision.to_dict(),
                        "uncertain_handwriting": True,
                        "ocr_confidence": ocr_confidence,
                        "line_count": len(lines),
                    },
                )

        # 7. Default natural text: calibrate confidence dynamically based on OCR quality, alphabetic ratio, and text structure
        ocr_conf = float((metadata or {}).get("confidence", 1.0))
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in cleaned) / max(1, len(cleaned))
        length_factor = min(0.04, len(cleaned) / 2500.0)
        calibrated_conf = 1.0 if is_native_digital else min(0.99, max(0.85, round(0.88 * ocr_conf + 0.08 * alpha_ratio + length_factor, 4)))

        return ClassificationResult(
            content_type=ContentType.TEXT,
            confidence=calibrated_conf,
            reason="Native digital presentation text." if is_native_digital else f"Standard natural language prose ({len(lines)} lines, {len(cleaned)} chars, {round(alpha_ratio*100, 1)}% alphabetic).",
            metadata={
                "strategy": self.strategy_name,
                "line_count": len(lines),
                "ocr_confidence": ocr_conf,
                "alpha_ratio": round(alpha_ratio, 3),
                "is_native_digital": is_native_digital,
            },
        )


class VisualRegionClassificationStrategy:
    """Classifies raster crops using visual/pixel characteristics and layout metadata."""

    strategy_name: str = "visual_region_strategy"

    def can_classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> bool:
        return image is not None or bool((metadata or {}).get("image_width"))

    def classify(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
    ) -> ClassificationResult | None:
        # If text is already extracted and substantial, prefer text/pattern strategy
        if text and len(text.strip()) > 30 and (metadata or {}).get("confidence", 0.0) > 0.80:
            return None

        if image is not None:
            w, h = image.size
            if w <= 0 or h <= 0:
                return None

            try:
                import numpy as np
                img_gray = image.convert("L")
                arr = np.array(img_gray)
                std_dev = float(np.std(arr))
                mean_val = float(np.mean(arr))

                # Technical drawing / schematic line art: high white background (mean > 200) with low variance
                # and sharp edges, or predominantly black-and-white
                if mean_val > 210 and 15 < std_dev < 60:
                    return ClassificationResult(
                        content_type=ContentType.DIAGRAM,
                        confidence=0.82,
                        reason="High-contrast monochromatic line art on light background indicates technical drawing/diagram.",
                        metadata={"strategy": self.strategy_name, "mean_intensity": mean_val, "std_dev": std_dev},
                    )

                # High variance image / photo
                if std_dev >= 60 or mean_val < 200:
                    return ClassificationResult(
                        content_type=ContentType.IMAGE,
                        confidence=0.85,
                        reason="High pixel variance and continuous tone indicates photograph or graphic image.",
                        metadata={"strategy": self.strategy_name, "std_dev": std_dev, "mean_intensity": mean_val},
                    )
            except Exception:
                pass

        # If metadata indicates an image without text
        if not text and (metadata or {}).get("image_format"):
            return ClassificationResult(
                content_type=ContentType.IMAGE,
                confidence=0.80,
                reason="Raster image region with no readable text detected.",
                metadata={"strategy": self.strategy_name},
            )

        return None
