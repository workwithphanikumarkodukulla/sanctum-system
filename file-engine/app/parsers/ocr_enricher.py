"""Reusable region-level enrichment service connecting OCR with local VLM escalation."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from PIL import Image, ImageStat

from app.core.config import settings
from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement
from app.extractors.formulas import formula_extractor
from app.extractors.handwriting import (
    HandwritingClassification,
    handwriting_checker,
    handwriting_classifier,
)
from app.extractors.tables import table_extractor
from app.models.vision_client import vision_client
from app.observability.processing_trace import get_current_trace
from app.processing.image import image_processor
from app.reconciliation.reconciler import evidence_reconciler

logger = logging.getLogger(__name__)


@dataclass
class RegionEnrichmentResult:
    """Standardized result of confidence-gated region enrichment."""
    final_text: str | None
    confidence: float
    content_type: str
    vlm_invoked: bool
    ocr_result: str | None = None
    vlm_result: str | None = None
    extraction_method: str = "Tesseract"
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_text": self.final_text,
            "confidence": self.confidence,
            "content_type": self.content_type,
            "vlm_invoked": self.vlm_invoked,
            "ocr_result": self.ocr_result,
            "vlm_result": self.vlm_result,
            "extraction_method": self.extraction_method,
            "provenance": self.provenance,
            "metadata": self.metadata,
        }


class RegionEnricher:
    """Reusable service providing confidence-gated OCR-to-VLM enrichment on individual visual crops.

    Works uniformly across:
    - Scanned PDF pages and bounding box crops
    - Standalone raster images (PNG, JPG, WEBP, TIFF)
    - Images and figures embedded in documents (DOCX, PPTX)
    - Suspected handwritten annotations and signature regions

    OCR confidence is treated strictly as an engine-provided quality/routing signal,
    NOT as a statistical guarantee or probability of correctness.
    """

    @classmethod
    def check_region_suspicion(
        cls,
        ocr_text: str | None,
        ocr_confidence: float,
        crop: Image.Image | None = None,
        content_type: str = "text",
    ) -> tuple[bool, list[str]]:
        """Lightweight, deterministic quality and suspicion gate.

        Combines engine confidence with textual and visual anomaly signals.
        OCR confidence is a heuristic routing signal, not a calibrated probability of correctness.

        Returns:
            (is_suspicious, suspicion_reasons)
        """
        reasons: list[str] = []
        clean_text = (ocr_text or "").strip()

        # 1. Substantial visual crop with empty OCR on textual/content regions
        if crop is not None and content_type != "image":
            w, h = crop.size
            if (w >= 40 and h >= 15) and not clean_text:
                reasons.append("empty_ocr_on_non_trivial_crop")

        if clean_text:
            # 2. Excessive unusual characters & punctuation noise (excluding markdown table pipes)
            if content_type != "table" and not (clean_text.startswith("|") and clean_text.endswith("|")):
                noisy_chars = set("~^|\\_§©¢¤`#{}")
                noise_count = sum(1 for c in clean_text if c in noisy_chars)
                if noise_count >= 3 or (len(clean_text) > 5 and (noise_count / len(clean_text)) > 0.15):
                    reasons.append(f"excessive_unusual_characters (count={noise_count})")

                # Repeated punctuation patterns (e.g. ...., ;;;;, ???? )
                if re.search(r"(\.{4,}|;{3,}|\?{3,}|!{3,}|/{3,}|_{4,})", clean_text):
                    reasons.append("repeated_punctuation_noise")

                # Unbalanced brackets in non-code text
                for open_b, close_b in [("(", ")"), ("[", "]"), ("{", "}")]:
                    if clean_text.count(open_b) != clean_text.count(close_b):
                        reasons.append(f"unbalanced_delimiters ({open_b}{close_b})")
                        break

            # 3. Numeric inconsistencies / OCR digit-letter confusions (e.g. 1O0, 5O00, l23)
            if re.search(r"\b\d+[OIl]\d*\b", clean_text) or re.search(r"\b[OIl]\d{2,}\b", clean_text):
                reasons.append("numeric_letter_confusion")

            # Broken decimal points (e.g. 5..00 or 5.,00)
            if re.search(r"\d+\.\.\d+|\d+,\.\d+", clean_text):
                reasons.append("broken_decimal_number")

            # 4. Formula / equation suspicion & corrupted glyph loss
            if (
                re.search(r"[a-zA-Z0-9]\?|\?[a-zA-Z0-9]|\b\?\b", clean_text)
                or ("?" in clean_text and any(sym in clean_text for sym in ["d/dx", "dx", "\\frac", "\\int", "+", "-", "*", "/", "=", "^"]))
            ):
                reasons.append("unrecognized_glyph_question_mark")

            if content_type == "formula" or any(kw in clean_text for kw in ["=", "\\frac", "\\sqrt", "d/dx"]):
                if re.search(r"(\+{2,}|\*{2,}|\/{2,}|\=\*|\+\=)", clean_text):
                    reasons.append("malformed_formula_operator_sequence")

            # 5. Handwriting suspicion
            if content_type in ("handwriting", "uncertain"):
                reasons.append("handwriting_content_type")

        # 6. Visual image quality checks (low contrast / extreme lightness / extreme darkness)
        if crop is not None:
            w, h = crop.size
            if w < 8 or h < 8:
                reasons.append("extreme_small_crop_dimensions")
            elif len(clean_text) < 5:
                try:
                    stat = ImageStat.Stat(crop.convert("L"))
                    std_dev = stat.stddev[0]
                    mean_val = stat.mean[0]
                    if std_dev < 6.0:
                        reasons.append("extremely_low_contrast_image")
                    elif mean_val < 10.0:
                        reasons.append("extremely_underexposed_image")
                    elif mean_val > 248.0 and std_dev < 8.0:
                        reasons.append("blank_or_washed_out_image")
                except Exception as img_err:
                    logger.debug("Image quality check skipped: %s", img_err)

        is_suspicious = len(reasons) > 0
        return is_suspicious, reasons

    @classmethod
    async def enrich_region(
        cls,
        crop: Image.Image | None,
        ocr_text: str | None,
        ocr_confidence: float,
        content_type: str = "text",
        metadata: dict[str, Any] | None = None,
        threshold: float | None = None,
        model_name: str = "Tesseract",
        force_vlm: bool = False,
    ) -> RegionEnrichmentResult:
        """Enrich a single visual region crop using confidence + quality suspicion gating.

        If OCR confidence is above threshold AND region is not suspicious: returns OCR result directly.
        If OCR confidence is below threshold OR region is suspicious: routes ONLY that specific crop to local VLM.
        """
        meta = dict(metadata or {})

        # 1. Determine effective threshold for this region type (configurable)
        if threshold is not None:
            eff_threshold = threshold
        elif content_type in ("handwriting", "uncertain"):
            eff_threshold = settings.HANDWRITING_VLM_REREAD_THRESHOLD
        elif content_type in ("formula", "engineering_spec", "critical_number", "critical_region"):
            eff_threshold = getattr(settings, "CRITICAL_REGION_THRESHOLD", 0.85)
        else:
            eff_threshold = settings.CONFIDENCE_THRESHOLD

        # 2. Evaluate lightweight quality and suspicion signals
        is_suspicious, suspicion_reasons = cls.check_region_suspicion(
            ocr_text=ocr_text,
            ocr_confidence=ocr_confidence,
            crop=crop,
            content_type=content_type,
        )
        if suspicion_reasons:
            meta["suspicion_signals"] = suspicion_reasons
        meta["ocr_confidence_semantics"] = "engine_quality_routing_signal"
        meta["raw_ocr_confidence"] = ocr_confidence
        meta["ocr_candidate"] = ocr_text
        meta["ocr_confidence"] = ocr_confidence
        if "handwriting_classification" not in meta and "handwriting_decision" in meta:
            meta["handwriting_classification"] = meta["handwriting_decision"].get("classification")

        # 3. Decision check:
        # Check if region is classified as handwritten (from content_type, metadata, or layout detection)
        is_handwritten = (
            content_type in ("handwriting", "uncertain")
            or meta.get("handwriting_classification") == "handwritten"
            or meta.get("is_handwriting") is True
            or meta.get("type") == "handwriting"
        )

        trace = get_current_trace()
        is_handwriting_override = False

        # PRINTED regions keep existing confidence-threshold behavior (eff_threshold, default 0.80).
        # HANDWRITTEN regions ALWAYS escalate to VLM if a visual crop is present,
        # regardless of PaddleOCR's reported confidence score.
        if is_handwritten and crop is not None:
            needs_vlm = True
            if ocr_confidence >= eff_threshold:
                is_handwriting_override = True
                meta["handwriting_override"] = True
                meta["vlm_escalation_reason"] = "handwriting_override"
                if trace:
                    trace.record_event(
                        stage="CONFIDENCE_GATE",
                        component="ConfidenceGate",
                        event="HANDWRITING_OVERRIDE",
                        status="success",
                        metadata={
                            "text": (ocr_text[:60] + "...") if ocr_text and len(ocr_text) > 60 else ocr_text,
                            "confidence": round(ocr_confidence, 4),
                            "threshold": eff_threshold,
                            "classification": "HANDWRITTEN",
                            "reason": "Handwriting detected: overriding high OCR confidence gate to mandate VLM verification",
                            "decision": "ESCALATE",
                        },
                    )
        else:
            needs_vlm = force_vlm or (crop is not None and (ocr_confidence < eff_threshold or is_suspicious))

        if not needs_vlm:
            # High confidence and no anomaly on printed text: return primary OCR result directly (VLM NOT called)
            meta["vlm_escalation_status"] = "not_needed"
            if trace:
                trace.record_event(
                    stage="CONFIDENCE_GATE",
                    component="ConfidenceGate",
                    event="CONFIDENCE_EVALUATED",
                    status="success",
                    metadata={
                        "text": (ocr_text[:60] + "...") if ocr_text and len(ocr_text) > 60 else ocr_text,
                        "confidence": round(ocr_confidence, 4),
                        "threshold": eff_threshold,
                        "suspicion": is_suspicious,
                        "decision": "ACCEPT",
                        "vlm": "SKIPPED",
                    },
                )
            return RegionEnrichmentResult(
                final_text=ocr_text,
                confidence=ocr_confidence,
                content_type=content_type,
                vlm_invoked=False,
                ocr_result=ocr_text,
                vlm_result=None,
                extraction_method=model_name,
                provenance={
                    "source": "ocr_direct",
                    "ocr_model": model_name,
                    "raw_ocr_confidence": ocr_confidence,
                    "ocr_confidence_semantics": "engine_quality_routing_signal",
                    "vlm_invoked": False,
                    "ocr_candidate": ocr_text,
                    "vlm_escalation_status": "not_needed",
                },
                metadata=meta,
            )

        if trace:
            trace.record_event(
                stage="CONFIDENCE_GATE",
                component="ConfidenceGate",
                event="CONFIDENCE_EVALUATED",
                status="success",
                metadata={
                    "text": (ocr_text[:60] + "...") if ocr_text and len(ocr_text) > 60 else ocr_text,
                    "confidence": round(ocr_confidence, 4),
                    "threshold": eff_threshold,
                    "suspicion": is_suspicious,
                    "decision": "ESCALATE",
                    "reason": "handwriting_override" if is_handwriting_override else ("low_confidence" if ocr_confidence < eff_threshold else "suspicion"),
                },
            )

        # 4. Escalation path: escalate ONLY this specific crop to local VLM
        if crop is None:
            # Crop unavailable (e.g. bounding box invalid or 0x0)
            meta["vlm_skipped_reason"] = "crop_unavailable"
            meta["vlm_escalation_status"] = "skipped_crop_unavailable"
            return RegionEnrichmentResult(
                final_text=ocr_text,
                confidence=ocr_confidence,
                content_type=content_type,
                vlm_invoked=False,
                ocr_result=ocr_text,
                vlm_result=None,
                extraction_method=model_name,
                provenance={
                    "source": "ocr_direct_fallback",
                    "ocr_model": model_name,
                    "raw_ocr_confidence": ocr_confidence,
                    "ocr_confidence_semantics": "engine_quality_routing_signal",
                    "vlm_invoked": False,
                    "ocr_candidate": ocr_text,
                    "vlm_escalation_status": "skipped_crop_unavailable",
                },
                metadata=meta,
            )

        logger.info(
            "Visual region (%s) confidence %.2f (threshold: %.2f, suspicious: %s); escalating crop to local VLM (%s).",
            content_type,
            ocr_confidence,
            eff_threshold,
            is_suspicious,
            settings.OLLAMA_VISION_MODEL,
        )

        if trace:
            trace.record_event(
                stage="VLM_ESCALATION",
                component="Local VLM",
                event="ESCALATION_STARTED",
                status="started",
                metadata={
                    "reason": "low confidence / suspicion",
                    "scope": "cropped region",
                    "model": settings.OLLAMA_VISION_MODEL,
                },
            )

        vlm_text, vlm_conf = await vision_client.reread_cropped_region(crop)

        if not vlm_text:
            # VLM offline or returned blank: fallback safely to primary OCR without destroying original evidence
            if trace:
                trace.record_event(
                    stage="VLM_RESULT",
                    component="Local VLM",
                    event="ESCALATION_COMPLETED",
                    status="unavailable",
                    metadata={"action": "original OCR preserved"},
                )
            meta["vlm_escalation_attempted"] = True
            meta["vlm_result_empty"] = True
            meta["vlm_escalation_status"] = "attempted_empty_or_unavailable"
            meta["vlm_candidate"] = None
            meta["requires_human_review"] = False
            if is_handwritten:
                meta["authoritative_source"] = "ocr_fallback"
            return RegionEnrichmentResult(
                final_text=ocr_text,
                confidence=ocr_confidence,
                content_type=content_type,
                vlm_invoked=False,
                ocr_result=ocr_text,
                vlm_result=None,
                extraction_method=f"{model_name}-fallback" if is_handwritten else model_name,
                provenance={
                    "source": "ocr_fallback_after_vlm_empty",
                    "authoritative_source": "ocr_fallback",
                    "reason": "vlm_empty_ocr_fallback",
                    "ocr_model": model_name,
                    "vlm_model": settings.OLLAMA_VISION_MODEL,
                    "raw_ocr_confidence": ocr_confidence,
                    "ocr_confidence_semantics": "engine_quality_routing_signal",
                    "vlm_invoked": False,
                    "ocr_candidate": ocr_text,
                    "vlm_candidate": None,
                    "vlm_escalation_status": "attempted_empty_or_unavailable",
                    "requires_human_review": False,
                },
                metadata=meta,
            )

        # 5. Process VLM reading and reconcile with OCR candidate
        if trace:
            trace.record_event(
                stage="VLM_RESULT",
                component="Local VLM",
                event="ESCALATION_COMPLETED",
                status="success",
                metadata={
                    "confidence": round(vlm_conf, 4) if vlm_conf else settings.RECHECK_CONFIDENCE,
                    "model": settings.OLLAMA_VISION_MODEL,
                },
            )
        meta["vlm_escalation_attempted"] = True
        meta["vlm_escalation_status"] = "completed"
        meta["vlm_candidate"] = vlm_text

        if content_type in ("handwriting", "uncertain") or is_handwritten:
            matched, final_text, consensus_conf, hw_meta = handwriting_checker.compare_consensus(
                ocr_text=ocr_text,
                vision_text=vlm_text,
            )
            vlm_succeeded = bool(vlm_text and vlm_text.strip())
            if trace:
                trace.record_event(
                    stage="RECONCILIATION",
                    component="EvidenceReconciler",
                    event="HANDWRITING_VLM_AUTHORITY" if vlm_succeeded else "RECONCILIATION_COMPLETED",
                    status="success",
                    metadata={
                        "authoritative_source": hw_meta.get("authoritative_source", "vlm" if vlm_succeeded else "ocr_fallback"),
                        "requires_human_review": False,
                        "vlm_model": settings.OLLAMA_VISION_MODEL,
                    },
                )
            meta.update(hw_meta)
            meta["reconciliation"] = hw_meta
            meta["requires_human_review"] = False
            if is_handwriting_override:
                meta["handwriting_override"] = True
            final_method = settings.OLLAMA_VISION_MODEL if vlm_succeeded else f"{model_name}-fallback"
            prov = {
                "source": "vlm_handwriting_authoritative" if vlm_succeeded else "ocr_fallback",
                "authoritative_source": "vlm" if vlm_succeeded else "ocr_fallback",
                "reason": "handwriting_vlm_authoritative" if vlm_succeeded else "vlm_empty_ocr_fallback",
                "ocr_candidate": ocr_text,
                "vlm_candidate": vlm_text,
                "raw_ocr_confidence": ocr_confidence,
                "ocr_confidence_semantics": "engine_quality_routing_signal",
                "ocr_model": model_name,
                "vlm_model": settings.OLLAMA_VISION_MODEL,
                "consensus": hw_meta.get("consensus", "vlm_authoritative" if vlm_succeeded else "ocr_fallback"),
                "requires_human_review": False,
                "handwriting_override": is_handwriting_override,
                "suspicion_signals": suspicion_reasons,
                "vlm_escalation_status": "completed" if vlm_succeeded else "attempted_empty_or_unavailable",
                "vlm_invoked": True,
            }
            return RegionEnrichmentResult(
                final_text=final_text,
                confidence=consensus_conf,
                content_type="handwriting" if is_handwritten else content_type,
                vlm_invoked=True,
                ocr_result=ocr_text,
                vlm_result=vlm_text,
                extraction_method=final_method,
                provenance=prov,
                metadata=meta,
            )
        else:
            # Standard visual text / image / formula region escalation & reconciliation
            rec_result = evidence_reconciler.reconcile(
                ocr_result={
                    "text": ocr_text or "",
                    "confidence": ocr_confidence,
                    "extraction_method": model_name,
                    "provenance": {"raw_ocr_confidence": ocr_confidence},
                },
                vlm_result={
                    "text": vlm_text,
                    "confidence": vlm_conf if vlm_conf > 0 else settings.RECHECK_CONFIDENCE,
                    "extraction_method": settings.OLLAMA_VISION_MODEL,
                },
            )

            if trace:
                trace.record_event(
                    stage="RECONCILIATION",
                    component="EvidenceReconciler",
                    event="RECONCILIATION_COMPLETED",
                    status="success",
                    metadata={
                        "result": rec_result.agreement_status.value,
                        "requires_human_review": rec_result.requires_review,
                    },
                )

            meta["escalated_to_vision"] = True
            meta["reconciliation"] = rec_result.to_dict()
            if rec_result.requires_review:
                meta["requires_human_review"] = True
                meta["disagreement_details"] = [d.to_dict() for d in rec_result.disagreement_details]

            final_method = f"{model_name}+{settings.OLLAMA_VISION_MODEL}"
            prov = {
                "source": "vlm_visual_escalation",
                "ocr_candidate": ocr_text,
                "vlm_candidate": vlm_text,
                "raw_ocr_confidence": ocr_confidence,
                "ocr_confidence_semantics": "engine_quality_routing_signal",
                "ocr_model": model_name,
                "vlm_model": settings.OLLAMA_VISION_MODEL,
                "agreement_status": rec_result.agreement_status.value,
                "requires_review": rec_result.requires_review,
                "disagreements": [d.to_dict() for d in rec_result.disagreement_details],
                "suspicion_signals": suspicion_reasons,
                "reconciled_confidence": rec_result.final_confidence,
                "vlm_invoked": True,
            }

            final_conf = vlm_conf if vlm_conf > 0 else settings.RECHECK_CONFIDENCE

            return RegionEnrichmentResult(
                final_text=rec_result.final_text,
                confidence=final_conf,
                content_type=content_type,
                vlm_invoked=True,
                ocr_result=ocr_text,
                vlm_result=vlm_text,
                extraction_method=final_method,
                provenance=prov,
                metadata=meta,
            )

    @classmethod
    async def enrich_embedded_image(
        cls,
        image: Image.Image,
        content_type: str = "image",
        threshold: float | None = None,
        extractor: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegionEnrichmentResult:
        """Enrich an image embedded in a document (e.g. DOCX/PPTX shape) with OCR and confidence gating."""
        from app.extractors.ocr import ocr_extractor
        active_extractor = extractor or ocr_extractor
        preprocessed = image_processor.preprocess_for_ocr(image)
        extracted = active_extractor.extract(preprocessed)
        if extracted:
            primary = extracted[0]
            ocr_text = primary.get("text")
            ocr_conf = float(primary.get("confidence", 0.0))
            model_name = primary.get("extraction_model", "Tesseract")
        else:
            ocr_text = None
            ocr_conf = 0.0
            model_name = "Tesseract"

        return await cls.enrich_region(
            crop=image,
            ocr_text=ocr_text,
            ocr_confidence=ocr_conf,
            content_type=content_type,
            threshold=threshold,
            model_name=model_name,
            metadata=metadata,
        )


region_enricher = RegionEnricher()


class OCREnricher:
    """High-level enricher assembling canonical EvidenceElements across pages/regions."""

    @classmethod
    async def enrich_and_build_elements(
        cls,
        raw_elements: list[dict[str, Any]],
        page_image: Image.Image,
        page_num: int,
        document_id: str,
        file_hash: str,
        start_idx: int = 1,
    ) -> list[EvidenceElement]:
        elements: list[EvidenceElement] = []

        # Pass 1: Context analysis across page regions to detect predominant handwriting
        hw_signals = 0
        text_count = 0
        for r in raw_elements:
            t = r.get("text", "")
            c = float(r.get("confidence", 0.85))
            if t and t.strip():
                text_count += 1
                eval_dec = handwriting_classifier.classify_region(
                    text=t,
                    confidence=c,
                    metadata=r.get("raw"),
                )
                if eval_dec.classification == HandwritingClassification.HANDWRITTEN:
                    hw_signals += 1

        is_page_handwritten = (
            (text_count >= 2 and hw_signals >= 2)
            or (text_count > 0 and (hw_signals / text_count) >= 0.25)
        )

        for idx, raw in enumerate(raw_elements, start=start_idx):
            elem_type = raw.get("type", "text")
            bbox = raw.get("bbox", [0.0, 0.0, float(page_image.width), float(page_image.height)])
            text = raw.get("text")
            confidence = float(raw.get("confidence", 0.85))
            model_used = raw.get("extraction_model", "Tesseract")
            metadata: dict[str, Any] = {}

            # Crop region for potential vision checks
            region_crop = image_processor.crop_region(page_image, bbox)

            # Pass contextual handwriting signal
            raw_meta = dict(raw.get("raw") or {})
            if is_page_handwritten:
                raw_meta["document_has_handwriting"] = True
                metadata["document_has_handwriting"] = True

            # 1. Modular handwriting classification decision
            hw_decision = handwriting_classifier.classify_region(
                crop=region_crop,
                text=text,
                confidence=confidence,
                metadata=raw_meta,
            )
            metadata["handwriting_decision"] = hw_decision.to_dict()
            metadata["handwriting_classification"] = hw_decision.classification.value

            if hw_decision.classification == HandwritingClassification.HANDWRITTEN:
                elem_type = "handwriting"
            elif hw_decision.classification == HandwritingClassification.UNCERTAIN:
                metadata["uncertain_handwriting"] = True

            # 2. General region-level enrichment (handles handwriting, printed low-conf, uncertain)
            enrichment = await region_enricher.enrich_region(
                crop=region_crop,
                ocr_text=text,
                ocr_confidence=confidence,
                content_type=elem_type,
                metadata=metadata,
                model_name=model_used,
            )

            text = enrichment.final_text
            confidence = enrichment.confidence
            model_used = enrichment.extraction_method
            metadata.update(enrichment.metadata)
            metadata["enrichment_provenance"] = enrichment.provenance

            # 3. Extract specialized structures on enriched text
            table_data = None
            formula_latex = None
            formula_variables = None

            if elem_type == "table":
                table_data = table_extractor.parse_table_data(text, raw.get("raw"))
            elif elem_type == "formula":
                latex_str, var_dict = formula_extractor.extract_formula_details(text)
                formula_latex = latex_str or text
                formula_variables = var_dict
                metadata["formula_details"] = {
                    "original_text": text,
                    "latex": latex_str or text,
                    "variables": list(var_dict.keys()) if var_dict else [],
                }

            element = EvidenceBuilder.build_element(
                element_idx=idx,
                document_id=document_id,
                page=page_num,
                elem_type=elem_type,
                text=text,
                table_data=table_data,
                formula_latex=formula_latex,
                formula_variables=formula_variables,
                bbox=bbox,
                confidence=confidence,
                extraction_model=model_used,
                file_hash=file_hash,
                metadata=metadata if metadata else None,
            )
            elements.append(element)

        if settings.OLLAMA_AUTO_UNLOAD and getattr(vision_client, "is_model_loaded", False):
            try:
                await vision_client.unload_model()
            except Exception as unload_exc:
                logger.debug("Failed to auto-unload vision model after enrich_document_elements: %s", unload_exc)

        return elements


ocr_enricher = OCREnricher()
