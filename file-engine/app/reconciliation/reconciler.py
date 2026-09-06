"""Engine-agnostic evidence reconciliation layer for comparing multi-candidate extractions."""
from __future__ import annotations

import difflib
import logging
import re
from typing import Any

from app.reconciliation.models import (
    AgreementStatus,
    DisagreementCategory,
    DisagreementDetail,
    ExtractionResult,
    ReconciliationResult,
)

logger = logging.getLogger(__name__)


class EvidenceReconciler:
    """Reconciles extraction candidates from OCR, VLM, or multiple parsers.

    Independent of OCR/VLM implementations. Normalizes text without destroying
    meaningful values, detects exact matches, formatting/OCR typos, and semantic
    conflicts (numbers, units, dates, names, formulas).
    """

    # Regex patterns for semantic extraction
    NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])")
    
    UNIT_PATTERN = re.compile(
        r"\b(?:kPa|MPa|GPa|Pa|psi|bar|mbar|kg|g|mg|mcg|lb|lbs|oz|m|cm|mm|km|ft|in|yd|mi|"
        r"s|sec|min|h|hr|hrs|L|mL|gal|°C|°F|K|V|mV|kV|A|mA|kA|W|kW|MW|Hz|kHz|MHz|GHz|"
        r"dB|rpm|%)\b",
        re.IGNORECASE,
    )

    DATE_PATTERN = re.compile(
        r"\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|"
        r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|"
        r"\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?,?\s+\d{4})\b",
        re.IGNORECASE,
    )

    FORMULA_OPERATOR_PATTERN = re.compile(r"[=><~≈≠≤≥\^√∫∑∏]|\b(?:sin|cos|tan|log|ln|exp|sqrt)\b")

    NAME_HONORIFIC_PATTERN = re.compile(
        r"\b(?:Dr|Mr|Mrs|Ms|Prof|Eng|Sir|Dame|Rev)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
    )
    NAME_ATTRIBUTION_PATTERN = re.compile(
        r"\b(?:by|signed by|authorized by|approved by|witnessed by|author[:]?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_text(cls, text: str | None) -> str:
        """Normalize whitespace and Unicode variants without stripping semantic characters."""
        if not text:
            return ""
        # Standardize curly quotes and unicode dashes
        cleaned = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        cleaned = cleaned.replace("—", "-").replace("–", "-")
        # Replace non-breaking and special spaces
        cleaned = cleaned.replace("\u00a0", " ").replace("\u200b", "")
        # Collapse multiple whitespace characters to single spaces, strip edges
        return " ".join(cleaned.split())

    @classmethod
    def _extract_numbers(cls, text: str) -> list[str]:
        """Extract canonical number representations from text."""
        raw_nums = cls.NUMBER_PATTERN.findall(text)
        canonical = []
        for n in raw_nums:
            try:
                # Normalize 450.0 to 450 if float matches int
                f = float(n)
                if f.is_integer():
                    canonical.append(str(int(f)))
                else:
                    canonical.append(str(f))
            except ValueError:
                canonical.append(n)
        return canonical

    @classmethod
    def _extract_units(cls, text: str) -> list[str]:
        """Extract units from text normalized to lowercase."""
        return [u.lower() for u in cls.UNIT_PATTERN.findall(text)]

    @classmethod
    def _extract_dates(cls, text: str) -> list[str]:
        """Extract date strings from text normalized."""
        return [d.strip().lower() for d in cls.DATE_PATTERN.findall(text)]

    @classmethod
    def _extract_names(cls, text: str) -> list[str]:
        """Extract capitalized person/entity names from text with honorifics or attributions."""
        names: list[str] = []
        for match in cls.NAME_HONORIFIC_PATTERN.finditer(text):
            names.append(match.group(0).strip())
        for match in cls.NAME_ATTRIBUTION_PATTERN.finditer(text):
            val = match.group(1).strip()
            if val not in names:
                names.append(val)
        return names

    @classmethod
    def _extract_formulas(cls, text: str) -> list[str]:
        """Extract mathematical formula tokens and equations."""
        return [op.strip() for op in cls.FORMULA_OPERATOR_PATTERN.findall(text)]

    @classmethod
    def detect_disagreements(
        cls, text_a: str, text_b: str
    ) -> list[DisagreementDetail]:
        """Identify specific semantic differences between two text candidates."""
        details: list[DisagreementDetail] = []

        # 1. Number Disagreement Check
        nums_a = cls._extract_numbers(text_a)
        nums_b = cls._extract_numbers(text_b)
        if sorted(nums_a) != sorted(nums_b):
            details.append(
                DisagreementDetail(
                    category=DisagreementCategory.NUMBER_MISMATCH,
                    field_name="numbers",
                    candidate_a_value=nums_a,
                    candidate_b_value=nums_b,
                    description=f"Candidate A numbers {nums_a} conflict with Candidate B numbers {nums_b}",
                )
            )

        # 2. Unit Disagreement Check
        units_a = cls._extract_units(text_a)
        units_b = cls._extract_units(text_b)
        if sorted(units_a) != sorted(units_b):
            details.append(
                DisagreementDetail(
                    category=DisagreementCategory.UNIT_MISMATCH,
                    field_name="units",
                    candidate_a_value=units_a,
                    candidate_b_value=units_b,
                    description=f"Candidate A units {units_a} conflict with Candidate B units {units_b}",
                )
            )

        # 3. Date Disagreement Check
        dates_a = cls._extract_dates(text_a)
        dates_b = cls._extract_dates(text_b)
        if sorted(dates_a) != sorted(dates_b):
            details.append(
                DisagreementDetail(
                    category=DisagreementCategory.DATE_MISMATCH,
                    field_name="dates",
                    candidate_a_value=dates_a,
                    candidate_b_value=dates_b,
                    description=f"Candidate A dates {dates_a} conflict with Candidate B dates {dates_b}",
                )
            )

        # 4. Formula Disagreement Check
        formulas_a = cls._extract_formulas(text_a)
        formulas_b = cls._extract_formulas(text_b)
        # Check if the only difference is ':' vs '=' as key-value delimiter
        is_delimiter_diff = (
            set(formulas_a) ^ set(formulas_b) == {"="}
            and (":" in text_a or ":" in text_b)
        )
        if sorted(formulas_a) != sorted(formulas_b) and not is_delimiter_diff:
            details.append(
                DisagreementDetail(
                    category=DisagreementCategory.FORMULA_MISMATCH,
                    field_name="formulas",
                    candidate_a_value=formulas_a,
                    candidate_b_value=formulas_b,
                    description=f"Candidate A formula operators {formulas_a} conflict with Candidate B {formulas_b}",
                )
            )

        # 5. Name Disagreement Check
        names_a = cls._extract_names(text_a)
        names_b = cls._extract_names(text_b)
        if names_a and names_b and sorted(names_a) != sorted(names_b):
            # Check if difference is just a minor typo or distinct names
            sim = difflib.SequenceMatcher(None, " ".join(names_a), " ".join(names_b)).ratio()
            if sim < 0.85:
                details.append(
                    DisagreementDetail(
                        category=DisagreementCategory.NAME_MISMATCH,
                        field_name="names",
                        candidate_a_value=names_a,
                        candidate_b_value=names_b,
                        description=f"Candidate A names {names_a} conflict with Candidate B names {names_b}",
                    )
                )

        return details

    @classmethod
    def reconcile(
        cls,
        result_a: ExtractionResult | dict[str, Any] | None = None,
        result_b: ExtractionResult | dict[str, Any] | None = None,
        *,
        ocr_result: ExtractionResult | dict[str, Any] | None = None,
        vlm_result: ExtractionResult | dict[str, Any] | None = None,
        is_handwritten: bool = False,
    ) -> ReconciliationResult:
        """Reconcile two extraction results with confidence calibration and disagreement audit.

        When is_handwritten is True:
        - If VLM candidate is non-empty, VLM is authoritative (requires_review=False).
        - If VLM candidate is empty/fails, OCR candidate is used as fallback (requires_review=False).
        - OCR and VLM candidates are both preserved for audit/provenance.
        """
        res_a = result_a or ocr_result
        res_b = result_b or vlm_result

        if res_a is None or res_b is None:
            raise ValueError("Reconciliation requires two candidate results to compare.")

        if isinstance(res_a, dict):
            res_a = ExtractionResult(
                text=res_a.get("text", ""),
                confidence=float(res_a.get("confidence", 0.0)),
                extraction_method=res_a.get("extraction_method", "unknown"),
                provenance=res_a.get("provenance", {}),
            )
        if isinstance(res_b, dict):
            res_b = ExtractionResult(
                text=res_b.get("text", ""),
                confidence=float(res_b.get("confidence", 0.0)),
                extraction_method=res_b.get("extraction_method", "unknown"),
                provenance=res_b.get("provenance", {}),
            )

        result_a = res_a
        result_b = res_b
        raw_a = res_a.text or ""
        raw_b = res_b.text or ""

        norm_a = cls.normalize_text(raw_a)
        norm_b = cls.normalize_text(raw_b)

        # Base confidence scores
        conf_a = float(res_a.confidence)
        conf_b = float(res_b.confidence)
        higher_conf_result = res_a if conf_a >= conf_b else res_b

        # ── Dedicated Handwriting Branch: VLM Authoritative ──────────────────
        if is_handwritten:
            if raw_b and raw_b.strip():
                # VLM candidate is authoritative; retain OCR as provenance
                is_exact = raw_a == raw_b
                is_norm = bool(norm_a and norm_a == norm_b)
                status = (
                    AgreementStatus.EXACT_MATCH
                    if is_exact
                    else (AgreementStatus.WHITESPACE_DIFFERENCE if is_norm else AgreementStatus.MATERIAL_DISAGREEMENT)
                )
                final_conf = conf_b if conf_b > 0 else 0.90
                return ReconciliationResult(
                    final_text=raw_b.strip(),
                    final_confidence=final_conf,
                    agreement_status=status,
                    disagreement_details=[],
                    requires_review=False,
                    candidate_a=result_a,
                    candidate_b=result_b,
                    provenance={
                        "reconciliation_type": "handwriting_vlm_authoritative",
                        "authoritative_source": "vlm",
                        "reason": "handwriting_vlm_authoritative",
                        "ocr_candidate": raw_a,
                        "vlm_candidate": raw_b,
                        "method_a": result_a.extraction_method,
                        "method_b": result_b.extraction_method,
                        "requires_human_review": False,
                    },
                    metadata={
                        "consensus": "matched" if is_exact or is_norm else "vlm_authoritative",
                        "authoritative_source": "vlm",
                        "requires_human_review": False,
                        "ocr_candidate": raw_a,
                        "vlm_candidate": raw_b,
                    },
                )
            elif raw_a and raw_a.strip():
                # VLM unavailable or empty; OCR is fallback
                return ReconciliationResult(
                    final_text=raw_a.strip(),
                    final_confidence=conf_a if conf_a > 0 else 0.75,
                    agreement_status=AgreementStatus.MATERIAL_DISAGREEMENT,
                    disagreement_details=[],
                    requires_review=False,
                    candidate_a=result_a,
                    candidate_b=result_b,
                    provenance={
                        "reconciliation_type": "ocr_fallback_after_vlm_empty",
                        "authoritative_source": "ocr_fallback",
                        "reason": "vlm_empty_ocr_fallback",
                        "ocr_candidate": raw_a,
                        "vlm_candidate": None,
                        "method_a": result_a.extraction_method,
                        "method_b": result_b.extraction_method,
                        "requires_human_review": False,
                    },
                    metadata={
                        "consensus": "ocr_fallback",
                        "authoritative_source": "ocr_fallback",
                        "requires_human_review": False,
                        "ocr_candidate": raw_a,
                        "vlm_candidate": None,
                    },
                )
            else:
                # Both unavailable/empty
                return ReconciliationResult(
                    final_text="",
                    final_confidence=0.0,
                    agreement_status=AgreementStatus.MATERIAL_DISAGREEMENT,
                    disagreement_details=[],
                    requires_review=False,
                    candidate_a=result_a,
                    candidate_b=result_b,
                    provenance={
                        "reconciliation_type": "unresolved_empty",
                        "authoritative_source": "none",
                        "reason": "both_candidates_empty",
                        "requires_human_review": False,
                    },
                    metadata={
                        "consensus": "unresolved",
                        "requires_human_review": False,
                    },
                )

        # 1. Exact character-for-character match
        if raw_a == raw_b:
            boosted_conf = min(0.99, round(max(conf_a, conf_b) + 0.10, 4))
            return ReconciliationResult(
                final_text=raw_a,
                final_confidence=boosted_conf,
                agreement_status=AgreementStatus.EXACT_MATCH,
                disagreement_details=[],
                requires_review=False,
                candidate_a=result_a,
                candidate_b=result_b,
                provenance={
                    "reconciliation_type": "exact_match",
                    "method_a": result_a.extraction_method,
                    "method_b": result_b.extraction_method,
                    "confidence_boosted": True,
                },
                metadata={
                    "consensus": "exact_match",
                    "similarity_ratio": 1.0,
                },
            )

        # 2. Pure whitespace variation
        if norm_a and norm_a == norm_b:
            boosted_conf = min(0.98, round(max(conf_a, conf_b) + 0.08, 4))
            return ReconciliationResult(
                final_text=higher_conf_result.text,
                final_confidence=boosted_conf,
                agreement_status=AgreementStatus.WHITESPACE_DIFFERENCE,
                disagreement_details=[],
                requires_review=False,
                candidate_a=result_a,
                candidate_b=result_b,
                provenance={
                    "reconciliation_type": "whitespace_difference",
                    "method_a": result_a.extraction_method,
                    "method_b": result_b.extraction_method,
                },
                metadata={
                    "consensus": "whitespace_variation",
                    "similarity_ratio": 1.0,
                },
            )

        # 3. Check for semantic disagreements (numbers, units, dates, names, formulas)
        semantic_disagreements = cls.detect_disagreements(raw_a, raw_b)

        # 4. Calculate lexical similarity
        sim_ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

        # If similarity is very low, also record text divergence
        if sim_ratio < 0.60:
            semantic_disagreements.append(
                DisagreementDetail(
                    category=DisagreementCategory.TEXT_DIVERGENCE,
                    field_name="full_text",
                    candidate_a_value=raw_a,
                    candidate_b_value=raw_b,
                    description=f"Candidates diverge substantially with low lexical similarity ({sim_ratio:.2f})",
                )
            )

        # Check pure whitespace variations
        no_space_a = re.sub(r"\s+", "", raw_a)
        no_space_b = re.sub(r"\s+", "", raw_b)
        is_whitespace_only = no_space_a == no_space_b and not semantic_disagreements

        # Check pure punctuation differences
        no_punct_a = re.sub(r"[^\w\s]", "", norm_a)
        no_punct_b = re.sub(r"[^\w\s]", "", norm_b)
        is_punctuation_only = no_punct_a == no_punct_b and not semantic_disagreements

        # 4. Handle Semantic Disagreements
        if semantic_disagreements:
            # If one candidate has unreadable/corrupted glyphs '?' and the other is clean, prefer the clean candidate
            chosen_candidate = higher_conf_result
            if "?" in raw_a and "?" not in raw_b:
                chosen_candidate = result_b
            elif "?" in raw_b and "?" not in raw_a:
                chosen_candidate = result_a

            discounted_conf = max(0.20, round(min(conf_a, conf_b) * 0.5, 4))
            return ReconciliationResult(
                final_text=chosen_candidate.text,
                final_confidence=discounted_conf,
                agreement_status=AgreementStatus.MATERIAL_DISAGREEMENT,
                disagreement_details=semantic_disagreements,
                requires_review=True,
                candidate_a=result_a,
                candidate_b=result_b,
                provenance={
                    "reconciliation_type": "material_disagreement",
                    "method_a": result_a.extraction_method,
                    "method_b": result_b.extraction_method,
                    "conflict_categories": [d.category.value for d in semantic_disagreements],
                },
                metadata={
                    "consensus": "conflicted",
                    "requires_human_review": True,
                    "similarity_ratio": round(sim_ratio, 4),
                    "disagreements": [d.to_dict() for d in semantic_disagreements],
                },
            )

        # 5. Handle Whitespace Differences
        if is_whitespace_only:
            boosted_conf = min(0.98, round(max(conf_a, conf_b) + 0.08, 4))
            return ReconciliationResult(
                final_text=higher_conf_result.text,
                final_confidence=boosted_conf,
                agreement_status=AgreementStatus.WHITESPACE_DIFFERENCE,
                disagreement_details=[],
                requires_review=False,
                candidate_a=result_a,
                candidate_b=result_b,
                provenance={
                    "reconciliation_type": "whitespace_difference",
                    "method_a": result_a.extraction_method,
                    "method_b": result_b.extraction_method,
                },
                metadata={
                    "consensus": "whitespace_variation",
                    "similarity_ratio": round(sim_ratio, 4),
                },
            )

        # 6. Handle Punctuation Differences
        if is_punctuation_only:
            boosted_conf = min(0.97, round(max(conf_a, conf_b) + 0.05, 4))
            return ReconciliationResult(
                final_text=higher_conf_result.text,
                final_confidence=boosted_conf,
                agreement_status=AgreementStatus.PUNCTUATION_DIFFERENCE,
                disagreement_details=[],
                requires_review=False,
                candidate_a=result_a,
                candidate_b=result_b,
                provenance={
                    "reconciliation_type": "punctuation_difference",
                    "method_a": result_a.extraction_method,
                    "method_b": result_b.extraction_method,
                },
                metadata={
                    "consensus": "punctuation_variation",
                    "similarity_ratio": round(sim_ratio, 4),
                },
            )

        # 7. Minor OCR Typo / High-similarity word variations without semantic divergence
        if sim_ratio >= 0.75:
            # Minor OCR typo detected, no semantic clash
            boosted_conf = min(0.96, round(max(conf_a, conf_b) + 0.04, 4))
            return ReconciliationResult(
                final_text=higher_conf_result.text,
                final_confidence=boosted_conf,
                agreement_status=AgreementStatus.MINOR_OCR_DIFFERENCE,
                disagreement_details=[],
                requires_review=False,
                candidate_a=result_a,
                candidate_b=result_b,
                provenance={
                    "reconciliation_type": "minor_ocr_difference",
                    "method_a": result_a.extraction_method,
                    "method_b": result_b.extraction_method,
                },
                metadata={
                    "consensus": "minor_typo_accepted",
                    "similarity_ratio": round(sim_ratio, 4),
                },
            )

        # 8. Complete Text Divergence
        text_divergence_detail = DisagreementDetail(
            category=DisagreementCategory.TEXT_DIVERGENCE,
            field_name="full_text",
            candidate_a_value=raw_a,
            candidate_b_value=raw_b,
            description=f"Candidates diverge substantially with low lexical similarity ({sim_ratio:.2f})",
        )
        discounted_conf = max(0.15, round(min(conf_a, conf_b) * 0.4, 4))
        return ReconciliationResult(
            final_text=higher_conf_result.text,
            final_confidence=discounted_conf,
            agreement_status=AgreementStatus.MATERIAL_DISAGREEMENT,
            disagreement_details=[text_divergence_detail],
            requires_review=True,
            candidate_a=result_a,
            candidate_b=result_b,
            provenance={
                "reconciliation_type": "complete_text_divergence",
                "method_a": result_a.extraction_method,
                "method_b": result_b.extraction_method,
                "conflict_categories": ["text_divergence"],
            },
            metadata={
                "consensus": "conflicted",
                "requires_human_review": True,
                "similarity_ratio": round(sim_ratio, 4),
                "disagreements": [text_divergence_detail.to_dict()],
            },
        )


evidence_reconciler = EvidenceReconciler()
