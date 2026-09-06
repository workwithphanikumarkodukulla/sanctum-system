"""Handwriting detection, classification decision layer, and OCR-vs-VLM routing."""
from __future__ import annotations

import logging
import re
import string
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)


class HandwritingClassification(str, Enum):
    """Classification states for document text regions."""
    PRINTED = "printed"
    HANDWRITTEN = "handwritten"
    UNCERTAIN = "uncertain"


class HandwritingDecision(BaseModel):
    """Decision output detailing classification, calibrated confidence, and heuristic signals."""
    classification: HandwritingClassification
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the classification decision")
    reason: str = Field(description="Auditable explanation of signals and criteria (heuristic-based)")
    signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw feature signals: OCR confidence, irregular character frequency, dictionary ratios",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "signals": self.signals,
        }


class HandwritingClassifier:
    """Modular rule-based decision layer classifying text/crops as printed, handwritten, or uncertain.

    Note: This uses signal-based heuristics (OCR confidence, character fragmentation, and glyph regularity)
    rather than a heavy trained deep learning neural network.
    """

    # Cursive stroke artifacts and atypical OCR substitution glyphs
    CURSIVE_CHAR_PATTERN = re.compile(r"[~`^_{}\[\]|\\«»‘’“”¢§©®°±—–]")
    HANDWRITING_KEYWORD_PATTERN = re.compile(
        r"\b(?:signature|signed|sign here|handwritten|initials|author[s]? signature|dea[rk]\s+[a-z]+|kind regards|warm regards|sincerely|notes)\b",
        re.IGNORECASE,
    )
    # Mid-word casing jumps: lowercase followed directly by uppercase (e.g. InSightS, CommuUny, pRcg, CULies)
    MID_WORD_CAPS_PATTERN = re.compile(r"[a-z][A-Z]")
    # Erratic mid-phrase punctuation attached to stop words or between words (e.g. "the, concep", "the. Subject")
    ERRATIC_PUNCT_PATTERN = re.compile(
        r"\b(?:the|a|an|of|in|to|for|is|our|we|and|with|on)[.,:]\s+[a-zA-Z]{2,}|\b[a-zA-Z]{2,}[.,][a-zA-Z]{2,}\b",
        re.IGNORECASE,
    )
    # Isolated single capital letters inside lowercase text (e.g. "P ofpesivg", "students O cetual")
    ISOLATED_CAPS_PATTERN = re.compile(r"(?<=\s)[A-Z](?=\s)")
    # Characteristic cursive handwriting OCR misreadings (e.g. 'r' misread as 'k', 'l' as 'd', 'for' as 'fer')
    CURSIVE_OCR_CONFUSIONS = re.compile(
        r"\b(?:deak|ouk|youk|auk|fer|daw|expekience|teak|yeak|1bl-program|erik)\b",
        re.IGNORECASE,
    )

    @classmethod
    def classify_region(
        cls,
        crop: Image.Image | None = None,
        text: str | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> HandwritingDecision:
        """Evaluate region signals to decide between printed, handwritten, or uncertain.

        Args:
            crop: Rendered or cropped visual snippet of the region.
            text: Text extracted by OCR engine.
            confidence: OCR engine confidence (0.0 to 1.0).
            metadata: Existing parser or layout metadata.

        Returns:
            HandwritingDecision model with honest heuristic score and provenance.
        """
        cleaned_text = (text or "").strip()
        # In markdown tables, '|' is a column delimiter, not a cursive handwriting stroke
        eval_text = cleaned_text
        if eval_text.count("|") >= 2 and ("---" in eval_text or "\n" in eval_text or (metadata or {}).get("is_table")):
            eval_text = eval_text.replace("|", " ")
        cursive_chars = len(cls.CURSIVE_CHAR_PATTERN.findall(eval_text))
        # Strip known engineering units (kPa, MPa, GPa, etc.) before evaluating mid-word capitalization
        caps_eval_text = re.sub(r"\b(?:kPa|MPa|GPa|kHz|MHz|GHz|mL|mbar|mcg|rpm|pH)\b", "", cleaned_text)
        mid_word_caps = len(cls.MID_WORD_CAPS_PATTERN.findall(caps_eval_text))
        erratic_punct = len(cls.ERRATIC_PUNCT_PATTERN.findall(cleaned_text))
        isolated_caps = len(cls.ISOLATED_CAPS_PATTERN.findall(cleaned_text))
        has_hw_keyword = bool(cls.HANDWRITING_KEYWORD_PATTERN.search(cleaned_text))
        has_cursive_confusion = bool(cls.CURSIVE_OCR_CONFUSIONS.search(cleaned_text))

        # Check visual signals if crop is available
        has_high_visual_variance = False
        is_visual_handwriting = False
        joined_cc_count = 0
        max_cc_aspect_ratio = 0.0

        if crop is not None:
            try:
                import numpy as np
                arr = np.array(crop.convert("L"))
                # Low text pixel fill on light background with variable stroke density
                std_dev = float(np.std(arr))
                has_high_visual_variance = std_dev > 45.0

                # Analyze connected components for cursive stroke connectivity
                if arr.shape[0] >= 15 and arr.shape[1] >= 40:
                    import cv2
                    _, thresh = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh)
                    if num_labels > 1:
                        crop_h = arr.shape[0]
                        widths = [s[cv2.CC_STAT_WIDTH] for s in stats[1:] if 10 <= s[cv2.CC_STAT_HEIGHT] <= 0.85 * crop_h and s[cv2.CC_STAT_AREA] > 15]
                        heights = [s[cv2.CC_STAT_HEIGHT] for s in stats[1:] if 10 <= s[cv2.CC_STAT_HEIGHT] <= 0.85 * crop_h and s[cv2.CC_STAT_AREA] > 15]
                        if widths and heights:
                            ars = [w / max(1, h) for w, h in zip(widths, heights)]
                            joined_cc_count = sum(1 for ar in ars if ar >= 2.2)
                            max_cc_aspect_ratio = max(ars) if ars else 0.0
                            # In cursive script, multiple letters connect into wide aspect ratio components
                            if joined_cc_count >= 3 or (joined_cc_count >= 2 and max_cc_aspect_ratio >= 3.5):
                                is_visual_handwriting = True
            except Exception as ex:
                logger.debug("Visual handwriting analysis error: %s", ex)

        # Contextual document-level signal: has document or page been flagged as containing handwriting?
        context_hw = bool(
            (metadata or {}).get("document_has_handwriting")
            or (metadata or {}).get("is_handwritten_document")
        )

        hw_score = (
            (cursive_chars * 2.0)
            + (mid_word_caps * 2.0)
            + (erratic_punct * 1.5)
            + (isolated_caps * 1.0)
            + (3.0 if has_cursive_confusion else 0.0)
            + (3.0 if is_visual_handwriting else 0.0)
            + (2.5 if has_hw_keyword else 0.0)
            + (1.0 if has_high_visual_variance else 0.0)
        )

        signals = {
            "ocr_confidence": round(confidence, 4),
            "text_length": len(cleaned_text),
            "cursive_char_count": cursive_chars,
            "irregular_char_count": cursive_chars,  # Backward-compatible alias
            "mid_word_caps_count": mid_word_caps,
            "erratic_punct_count": erratic_punct,
            "isolated_caps_count": isolated_caps,
            "hw_feature_score": round(hw_score, 2),
            "has_handwriting_keyword": has_hw_keyword,
            "has_cursive_confusion": has_cursive_confusion,
            "has_high_visual_variance": has_high_visual_variance,
            "is_visual_handwriting": is_visual_handwriting,
            "joined_cc_count": joined_cc_count,
            "max_cc_aspect_ratio": round(max_cc_aspect_ratio, 2),
            "document_has_handwriting": context_hw,
            "heuristic_method": "signal_analysis_v2",
        }

        # 1. Clear Printed Text
        # High confidence, no irregular OCR distortion, standard alphanumeric distribution, no cursive visual features
        if (
            confidence >= settings.HANDWRITING_PRINTED_THRESHOLD
            and hw_score == 0
            and not has_hw_keyword
            and not has_cursive_confusion
            and not is_visual_handwriting
            and not context_hw
        ):
            return HandwritingDecision(
                classification=HandwritingClassification.PRINTED,
                confidence=0.95,
                reason=(
                    f"High OCR confidence ({confidence:.2f} >= {settings.HANDWRITING_PRINTED_THRESHOLD}) "
                    "with standard typographic glyphs indicates printed text (heuristic rule)."
                ),
                signals=signals,
            )

        # 2. Suspected Handwritten Text
        # Note: OCR confidence on cursive script can be deceptively high (0.88-0.99) while being systematically wrong.
        # Therefore, handwriting classification must be driven by visual/textual features, not gated behind low OCR confidence alone!
        is_low_conf = confidence < settings.HANDWRITING_SUSPECTED_THRESHOLD

        is_handwritten = False
        hw_reason = ""

        # Case A: Visual cursive stroke connectivity detected from crop
        if is_visual_handwriting and hw_score >= 3.0:
            is_handwritten = True
            hw_reason = (
                f"Visual cursive stroke connectivity detected (joined components: {joined_cc_count}, "
                f"max aspect ratio: {max_cc_aspect_ratio:.2f}) indicates cursive handwriting (visual heuristic)."
            )
        # Case B: Cursive confusion keywords or distortion features present regardless of raw OCR confidence
        elif (has_cursive_confusion or mid_word_caps >= 1 or cursive_chars >= 1) and hw_score >= 2.0:
            is_handwritten = True
            hw_reason = (
                f"Cursive handwriting characteristics / typographic artifacts detected (score: {hw_score:.1f}) "
                "indicate handwritten script despite raw OCR confidence (heuristic signal)."
            )
        # Case C: Low OCR confidence combined with cursive artifacts/distortion
        elif is_low_conf and hw_score >= 1.5:
            is_handwritten = True
            hw_reason = (
                f"Low OCR confidence ({confidence:.2f} < {settings.HANDWRITING_SUSPECTED_THRESHOLD}) "
                f"and cursive distortion score ({hw_score:.1f}) suggest handwriting / handwritten script (heuristic signal)."
            )
        # Case D: Document-level handwriting context where region belongs to handwritten body
        elif context_hw and (hw_score >= 1.0 or is_visual_handwriting or has_hw_keyword or is_low_conf):
            is_handwritten = True
            hw_reason = (
                f"Document-level handwriting context confirmed: region in handwritten document "
                f"(score: {hw_score:.1f}, conf: {confidence:.2f}) belongs to handwritten body (heuristic signal)."
            )
        # Case E: Explicit signature/handwriting keyword cues
        elif has_hw_keyword and (is_low_conf or confidence < 0.85 or hw_score >= 2.0):
            is_handwritten = True
            hw_reason = (
                f"Handwriting/signature cue detected with non-authoritative signal ({confidence:.2f}) "
                "suggests handwritten content (heuristic signal)."
            )

        if is_handwritten:
            return HandwritingDecision(
                classification=HandwritingClassification.HANDWRITTEN,
                confidence=0.85,
                reason=hw_reason,
                signals=signals,
            )

        # 3. Degraded / Faint Printed text or Uncertain / Ambiguous
        # Low OCR confidence alone WITHOUT cursive/handwriting features suggests faint/blurred print
        if is_low_conf and hw_score == 0 and not context_hw:
            return HandwritingDecision(
                classification=HandwritingClassification.UNCERTAIN,
                confidence=0.60,
                reason=(
                    f"Low OCR confidence ({confidence:.2f} < {settings.HANDWRITING_SUSPECTED_THRESHOLD}) "
                    "without cursive artifacts suggests degraded/faint printed text or poor scan quality (heuristic signal)."
                ),
                signals=signals,
            )

        # Intermediate confidence (between SUSPECTED and PRINTED thresholds) or ambiguous signals
        if is_low_conf or (settings.HANDWRITING_SUSPECTED_THRESHOLD <= confidence < settings.HANDWRITING_PRINTED_THRESHOLD):
            return HandwritingDecision(
                classification=HandwritingClassification.UNCERTAIN,
                confidence=0.60,
                reason=(
                    f"Intermediate OCR confidence ({confidence:.2f}) or conflicting typographic signals; "
                    "classification is uncertain and requires confidence-gated evaluation (heuristic signal)."
                ),
                signals=signals,
            )

        # Default fallback to printed if confidence is moderate-high and text is clean
        return HandwritingDecision(
            classification=HandwritingClassification.PRINTED,
            confidence=0.85,
            reason="Clean character structure and acceptable OCR confidence indicate printed text (heuristic rule).",
            signals=signals,
        )


class HandwritingChecker:
    """Consensus checking and routing engine between primary OCR and local vision models."""

    @staticmethod
    def normalize_text(text: str | None) -> str:
        if not text:
            return ""
        # Lowercase, strip punctuation, collapse whitespace
        text = text.lower()
        text = text.translate(str.maketrans("", "", string.punctuation))
        return " ".join(text.split())

    @staticmethod
    def is_suspected_handwritten(
        crop: Image.Image | None,
        text: str | None,
        confidence: float,
    ) -> bool:
        """Backward-compatible boolean check querying the modular HandwritingClassifier."""
        decision = HandwritingClassifier.classify_region(
            crop=crop,
            text=text,
            confidence=confidence,
        )
        return decision.classification == HandwritingClassification.HANDWRITTEN

    @staticmethod
    def compare_consensus(
        ocr_text: str | None,
        vision_text: str | None,
    ) -> tuple[bool, str, float, dict[str, Any]]:
        """Compare primary OCR reading against VLM reading for handwriting.

        Handwriting Rule:
        - VLM is authoritative when available and non-empty.
        - OCR is preserved as provenance and serves as fallback if VLM fails.
        - Disagreement between OCR and VLM on handwriting does NOT require human review.
        """
        from app.reconciliation import ExtractionResult, evidence_reconciler

        res_a = ExtractionResult(
            text=ocr_text,
            confidence=0.80,
            extraction_method="Tesseract",
            provenance={"source": "ocr", "model": "Tesseract"},
        )
        res_b = ExtractionResult(
            text=vision_text,
            confidence=settings.RECHECK_CONFIDENCE,
            extraction_method=settings.OLLAMA_VISION_MODEL,
            provenance={"source": "vlm", "model": settings.OLLAMA_VISION_MODEL},
        )

        recon = evidence_reconciler.reconcile(res_a, res_b, is_handwritten=True)

        norm_a = HandwritingChecker.normalize_text(ocr_text)
        norm_b = HandwritingChecker.normalize_text(vision_text)
        is_exact_or_norm_match = bool(norm_a and norm_a == norm_b)

        if vision_text and vision_text.strip():
            final_text = vision_text.strip()
            conf = settings.CONSENSUS_HIGH_CONFIDENCE if is_exact_or_norm_match else settings.RECHECK_CONFIDENCE
            consensus_status = "matched" if is_exact_or_norm_match else "vlm_authoritative"
            reconciliation_key = "consensus_agreement" if is_exact_or_norm_match else "handwriting_vlm_authoritative"
            return (
                True,
                final_text,
                conf,
                {
                    "handwriting_checked": True,
                    "consensus": consensus_status,
                    "requires_human_review": False,
                    "authoritative_source": "vlm",
                    "agreement_status": recon.agreement_status.value,
                    "ocr_candidate": ocr_text,
                    "vlm_candidate": vision_text,
                    "provenance": {
                        "ocr_model": "Tesseract",
                        "vlm_model": settings.OLLAMA_VISION_MODEL,
                        "reconciliation": reconciliation_key,
                        "authoritative_source": "vlm",
                        "reason": "handwriting_vlm_authoritative",
                    },
                },
            )
        elif ocr_text and ocr_text.strip():
            final_text = ocr_text.strip()
            return (
                False,
                final_text,
                0.75,
                {
                    "handwriting_checked": True,
                    "consensus": "ocr_fallback",
                    "requires_human_review": False,
                    "authoritative_source": "ocr_fallback",
                    "agreement_status": "ocr_fallback",
                    "ocr_candidate": ocr_text,
                    "vlm_candidate": None,
                    "provenance": {
                        "ocr_model": "Tesseract",
                        "vlm_model": settings.OLLAMA_VISION_MODEL,
                        "reconciliation": "ocr_fallback_after_vlm_empty",
                        "authoritative_source": "ocr_fallback",
                        "reason": "vlm_empty_ocr_fallback",
                    },
                },
            )
        else:
            return (
                False,
                "",
                0.0,
                {
                    "handwriting_checked": True,
                    "consensus": "unresolved",
                    "requires_human_review": False,
                    "authoritative_source": "none",
                    "ocr_candidate": None,
                    "vlm_candidate": None,
                    "provenance": {
                        "reconciliation": "unresolved_empty",
                    },
                },
            )



def validate_handwriting_vlm_output(text: str | None) -> tuple[bool, str, str | None]:
    """Deterministically validates and cleans VLM handwriting transcription output.

    Detects degenerative repetition loops, excessive repeated lines, and strips conversational wrappers.
    Does NOT invent replacement text or alter legitimate handwriting content.

    Returns:
        (is_valid: bool, cleaned_text: str, rejection_reason: str | None)
    """
    if text is None:
        return False, "", "empty_output"

    cleaned = text.strip()
    if not cleaned:
        return False, "", "empty_output"

    # 1. Strip full markdown code block wrappers if present (e.g. ```markdown ... ```)
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:-1]).strip()

    # 2. Strip conversational intro wrappers
    wrapper_patterns = [
        r"^(?:Here is the (?:faithful )?transcription(?:\s+of the (?:handwriting|image|handwritten (?:note|text)))?:?)\s*",
        r"^(?:Sure, here is (?:the transcription|the handwritten text):?)\s*",
        r"^(?:Transcription:?)\s*",
        r"^(?:Analysis:?)\s*",
        r"^(?:The (?:visible )?handwritten text (?:in the image )?says:?)\s*",
    ]
    for pat in wrapper_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()

    # Strip conversational sign-offs
    cleaned = re.sub(
        r"\s*(?:Let me know if you need (?:any further help|anything else)\.?|Hope this helps\.?)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    if not cleaned:
        return False, "", "empty_after_stripping_wrappers"

    # 3. Check A & C: Repetition loop detection (3+ word n-grams repeating consecutively 3+ times)
    words = cleaned.split()
    total_words = len(words)

    # Check for consecutive phrase loops of length n (from 3 to 12 words)
    for n in range(3, min(13, (total_words // 3) + 1)):
        for i in range(total_words - (3 * n) + 1):
            phrase1 = [w.lower() for w in words[i : i + n]]
            phrase2 = [w.lower() for w in words[i + n : i + (2 * n)]]
            phrase3 = [w.lower() for w in words[i + (2 * n) : i + (3 * n)]]
            if phrase1 == phrase2 == phrase3:
                return False, cleaned, "repetitive_phrase_loop"

    # 4. Check B: Excessive repeated lines
    raw_lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if raw_lines:
        # Check consecutive identical lines (length >= 4 chars repeating 3+ times)
        consec_count = 1
        for idx in range(1, len(raw_lines)):
            if len(raw_lines[idx]) >= 4 and raw_lines[idx].lower() == raw_lines[idx - 1].lower():
                consec_count += 1
                if consec_count >= 3:
                    return False, cleaned, "excessive_repeated_lines"
            else:
                consec_count = 1

        # Check if any single line dominates > 40% of all lines in long documents
        if len(raw_lines) >= 6:
            line_counts: dict[str, int] = {}
            for line in raw_lines:
                if len(line) >= 6:
                    k = line.lower()
                    line_counts[k] = line_counts.get(k, 0) + 1
            for k, count in line_counts.items():
                if count >= 4 and (count / len(raw_lines)) >= 0.40:
                    return False, cleaned, "excessive_repeated_lines"

    # 5. Low-entropy degenerative loop check (e.g. model stuck generating same 2 words 50 times)
    if total_words >= 30:
        unique_words = len(set(w.lower() for w in words))
        if (unique_words / total_words) < 0.20:
            return False, cleaned, "degenerative_low_entropy_loop"

    return True, cleaned, None


handwriting_classifier = HandwritingClassifier()
handwriting_checker = HandwritingChecker()

