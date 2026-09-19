"""Native image parser leveraging image preprocessing and replaceable OCR extractors."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Sequence
from PIL import Image

from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement
from app.extractors.handwriting import HandwritingClassification, handwriting_classifier
from app.extractors.ocr import BaseOCRExtractor, ocr_extractor
from app.parsers.base import BaseParser, ParseResult
from app.parsers.ocr_enricher import region_enricher
from app.processing.image import image_processor

logger = logging.getLogger(__name__)


@dataclass
class ImageRegion:
    """Represents a localized OCR region in an image with bounding coordinates and confidence."""
    region_index: int
    type: str  # "text", "table", "formula", "image"
    bbox: list[float]  # [x1, y1, x2, y2]
    text: str | None
    confidence: float
    extraction_model: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageParseResult:
    """Structured result of image OCR parsing."""
    parser_name: str = "image_parser"
    source_document: str = ""
    image_width: int = 0
    image_height: int = 0
    image_format: str = ""
    extracted_regions: list[ImageRegion] = field(default_factory=list)
    full_text: str = ""
    elements: list[EvidenceElement] = field(default_factory=list)
    total_pages: int = 1
    parser_used: str = "image-Tesseract"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_evidence_elements(
        self,
        document_id: str = "doc_img",
        file_hash: str = "",
    ) -> list[EvidenceElement]:
        """Convert extracted regions into canonical EvidenceElements."""
        elements: list[EvidenceElement] = []

        for reg in self.extracted_regions:
            elem_meta = dict(reg.raw or {})
            elem_meta.update({
                "source_document": self.source_document,
                "image_width": self.image_width,
                "image_height": self.image_height,
                "image_format": self.image_format,
            })
            elem = EvidenceBuilder.build_element(
                element_idx=reg.region_index,
                document_id=document_id,
                page=1,
                elem_type=reg.type,
                text=reg.text,
                bbox=reg.bbox,
                confidence=reg.confidence,
                extraction_model=reg.extraction_model,
                file_hash=file_hash,
                metadata=elem_meta,
            )
            elements.append(elem)

        return elements


class ImageParser(BaseParser):
    """Parses raster images (PNG, JPEG, WEBP, TIFF) into structured text regions using an OCR extractor."""

    def __init__(self, extractor: BaseOCRExtractor | None = None) -> None:
        self.extractor: BaseOCRExtractor = extractor or ocr_extractor

    @classmethod
    def _load_image_safely(cls, input_data: bytes | BinaryIO | str | Path | Image.Image) -> tuple[Image.Image, bytes, str]:
        """Load and validate image input into a PIL Image and raw bytes."""
        if isinstance(input_data, Image.Image):
            buf = io.BytesIO()
            input_data.save(buf, format="PNG")
            return input_data.convert("RGB"), buf.getvalue(), input_data.format or "PNG"

        if hasattr(input_data, "read"):
            data = input_data.read()
        elif isinstance(input_data, (str, Path)):
            with open(input_data, "rb") as f:
                data = f.read()
        elif isinstance(input_data, bytes):
            data = input_data
        elif isinstance(input_data, (bytearray, memoryview)):
            data = bytes(input_data)
        else:
            raise TypeError(f"Expected bytes, Path, or Image.Image, got {type(input_data).__name__}")

        if not data:
            raise ValueError("Uploaded image file is empty (0 bytes).")

        try:
            # Validate format with PIL and apply orientation correction
            raw_img = Image.open(io.BytesIO(data))
            detected_format = raw_img.format or "IMAGE"
            loaded_img = image_processor.load_image(data)
            return loaded_img, data, detected_format
        except Exception as exc:
            raise ValueError(f"Invalid or unreadable image file: {exc}")

    async def parse(
        self,
        file_bytes: bytes | BinaryIO | str | Path | Image.Image,
        filename: str = "",
        document_id: str = "doc_img",
        file_hash: str = "",
        call_vlm: bool = False,
        **kwargs: Any,
    ) -> ImageParseResult:
        """Execute image processing flow: validation -> preprocessing -> OCR extraction -> structured result."""
        source_doc = filename or "image.png"

        # 1. Image validation & loading
        image, raw_bytes, img_format = self._load_image_safely(file_bytes)
        img_w, img_h = image.size

        # 2. Preprocessing for OCR (contrast & sharpening)
        preprocessed = image_processor.preprocess_for_ocr(image)

        # 3. OCR extractor (Tesseract or injected engine, no VLM by default)
        raw_regions = self.extractor.extract(preprocessed)

        # 4. Document-level handwriting context analysis (Pass 1)
        hw_signals = 0
        text_count = 0
        for r in raw_regions:
            t = r.get("text", "")
            c = float(r.get("confidence", 0.80))
            b = r.get("bbox")
            reg_crop_p1 = image_processor.crop_region(image, b) if b else None
            if t and t.strip():
                text_count += 1
                eval_dec = handwriting_classifier.classify_region(
                    crop=reg_crop_p1,
                    text=t,
                    confidence=c,
                    metadata=r.get("raw"),
                )
                if eval_dec.classification == HandwritingClassification.HANDWRITTEN:
                    hw_signals += 1

        all_ocr_text = " ".join(r.get("text", "") for r in raw_regions)
        has_math_or_formula = (
            any(k in all_ocr_text.lower() for k in ("dy/dx", "d/dx", "diff", "\\frac", "log", "lim", "int", "sin", "cos", "tan", "sqrt", "^", "=", "+", "*"))
            or any(k in source_doc.lower() for k in ("diff", "problem", "math", "eq", "calc", "formula"))
        )
        is_sparse_or_problem = text_count <= 4 and (has_math_or_formula or hw_signals >= 1 or not all_ocr_text.strip())

        is_doc_handwritten = (
            (text_count >= 2 and hw_signals >= 2)
            or (text_count > 0 and (hw_signals / text_count) >= 0.25)
            or (hw_signals >= 1 and text_count <= 2)
            or is_sparse_or_problem
            or ("handwritten" in source_doc.lower())
        )

        model_name = "PaddleOCR" if getattr(self.extractor, "is_paddle_active", False) else "Tesseract"

        # 5. Assemble structured extraction result (Pass 2)
        regions: list[ImageRegion] = []
        text_parts: list[str] = []
        vlm_invoked_any = False

        if is_doc_handwritten:
            # ------------------------------------------------------------------
            # WHOLE-IMAGE HANDWRITING VLM (ONE IMAGE -> ONE VLM TRANSCRIPTION)
            # OCR boxes do NOT fracture the handwritten document into independent
            # VLM transcription units. VLM receives full visual context.
            # ------------------------------------------------------------------
            from app.core.config import settings
            from app.extractors.handwriting import validate_handwriting_vlm_output
            from app.models.vision_client import vision_client
            from app.observability.processing_trace import get_current_trace

            trace = get_current_trace()
            if trace:
                trace.record_event(
                    stage="CONTENT_CLASSIFICATION",
                    component="HandwritingClassifier",
                    event="HANDWRITING_DETECTED",
                    status="success",
                    metadata={"document_has_handwriting": True, "hw_signals": hw_signals},
                )
                trace.record_event(
                    stage="CONFIDENCE_GATE",
                    component="ConfidenceGate",
                    event="HANDWRITING_OVERRIDE",
                    status="success",
                    metadata={"reason": "Handwriting detected: overriding OCR fragmentation for whole-image VLM", "decision": "ESCALATE"},
                )
                trace.record_event(
                    stage="VLM_ESCALATION",
                    component="Local VLM",
                    event="VLM_FULL_IMAGE_ESCALATION",
                    status="started",
                    metadata={"scope": "full_image", "model": settings.OLLAMA_VISION_MODEL},
                )
                trace.record_event(
                    stage="VLM_ESCALATION",
                    component="Local VLM",
                    event="ESCALATION_STARTED",
                    status="started",
                    metadata={"model": settings.OLLAMA_VISION_MODEL},
                )
                trace.record_event(
                    stage="VLM_ESCALATION",
                    component="Local VLM",
                    event="VLM_STARTED",
                    status="started",
                    metadata={"model": settings.OLLAMA_VISION_MODEL},
                )

            # Preserve full OCR text as supporting candidate and fallback
            ocr_text_parts = [r.get("text", "").strip() for r in raw_regions if r.get("text", "").strip()]
            full_ocr_text = "\n".join(ocr_text_parts).strip()
            full_ocr_conf = (
                sum(r.get("confidence", 0.0) for r in raw_regions) / len(raw_regions)
                if raw_regions
                else 0.0
            )

            # Whole-image VLM handwriting transcription
            vlm_text, vlm_conf, _ = await vision_client.transcribe_handwriting(image)
            is_valid, cleaned_vlm_text, rejection_reason = validate_handwriting_vlm_output(vlm_text)

            if is_valid and cleaned_vlm_text:
                final_text = cleaned_vlm_text
                authoritative_source = "vlm"
                final_conf = vlm_conf or 0.95
                final_model = settings.OLLAMA_VISION_MODEL
                vlm_succeeded = True
                if trace:
                    trace.record_event(
                        stage="VLM_RESULT",
                        component="Local VLM",
                        event="ESCALATION_COMPLETED",
                        status="success",
                        metadata={"model": settings.OLLAMA_VISION_MODEL, "char_count": len(final_text)},
                    )
                    trace.record_event(
                        stage="VLM_RESULT",
                        component="Local VLM",
                        event="VLM_COMPLETED",
                        status="success",
                        metadata={"model": settings.OLLAMA_VISION_MODEL, "char_count": len(final_text)},
                    )
                    trace.record_event(
                        stage="VLM_RESULT",
                        component="Local VLM",
                        event="VLM_OUTPUT_VALIDATED",
                        status="success",
                        metadata={"is_valid": True},
                    )
                    trace.record_event(
                        stage="RECONCILIATION",
                        component="EvidenceReconciler",
                        event="HANDWRITING_VLM_AUTHORITY",
                        status="success",
                        metadata={"authoritative_source": "vlm", "requires_human_review": False},
                    )
            else:
                # Safe fallback to OCR without fabricating text
                final_text = full_ocr_text
                authoritative_source = "ocr_fallback"
                final_conf = full_ocr_conf
                final_model = f"{model_name}-fallback"
                vlm_succeeded = False
                if trace:
                    trace.record_event(
                        stage="VLM_RESULT",
                        component="Local VLM",
                        event="VLM_COMPLETED" if vlm_text else "VLM_FAILED",
                        status="rejected" if vlm_text else "unavailable",
                        metadata={"rejection_reason": rejection_reason or "vlm_empty_or_failed"},
                    )
                    if rejection_reason:
                        trace.record_event(
                            stage="VLM_RESULT",
                            component="Local VLM",
                            event="VLM_OUTPUT_REJECTED",
                            status="rejected",
                            metadata={"reason": rejection_reason},
                        )
                    trace.record_event(
                        stage="RECONCILIATION",
                        component="EvidenceReconciler",
                        event="OCR_FALLBACK",
                        status="fallback",
                        metadata={"authoritative_source": "ocr_fallback", "requires_human_review": False},
                    )

            reg_raw = {
                "is_handwriting": True,
                "handwriting_classification": "handwritten",
                "authoritative_source": authoritative_source,
                "ocr_candidate": full_ocr_text or None,
                "vlm_candidate": cleaned_vlm_text if (is_valid and cleaned_vlm_text) else None,
                "ocr_confidence": full_ocr_conf,
                "raw_ocr_confidence": full_ocr_conf,
                "suspicion_signals": ["handwriting_content_type", "document_has_handwriting"],
                "requires_human_review": False,
                "vlm_invoked": True,
                "vlm_model": settings.OLLAMA_VISION_MODEL,
                "ocr_engine": model_name,
                "full_image_vlm": True,
                "document_has_handwriting": True,
            }
            if not vlm_succeeded:
                reg_raw["vlm_rejection_reason"] = rejection_reason or "vlm_empty_or_failed"

            regions.append(
                ImageRegion(
                    region_index=1,
                    type="handwriting",
                    bbox=[0.0, 0.0, float(img_w), float(img_h)],
                    text=final_text,
                    confidence=final_conf,
                    extraction_model=final_model,
                    raw=reg_raw,
                )
            )
            vlm_invoked_any = True
            if final_text:
                text_parts.append(final_text)
        else:
            for idx, reg in enumerate(raw_regions, start=1):
                reg_type = reg.get("type", "text")
                reg_bbox = reg.get("bbox", [0.0, 0.0, float(img_w), float(img_h)])
                reg_text = reg.get("text")
                reg_conf = float(reg.get("confidence", 0.80))
                reg_model = reg.get("extraction_model", "Tesseract-Fallback")

                # Crop region for potential vision checks
                reg_crop = image_processor.crop_region(image, reg_bbox)

                reg_raw = dict(reg.get("raw", {}))

                # Evaluate modular handwriting decision with document context
                hw_decision = handwriting_classifier.classify_region(
                    crop=reg_crop,
                    text=reg_text,
                    confidence=reg_conf,
                    metadata=reg_raw,
                )
                reg_raw["handwriting_decision"] = hw_decision.to_dict()
                reg_raw["handwriting_classification"] = hw_decision.classification.value

                if hw_decision.classification == HandwritingClassification.HANDWRITTEN:
                    reg_type = "handwriting"
                elif hw_decision.classification == HandwritingClassification.UNCERTAIN:
                    reg_raw["uncertain_handwriting"] = True

                # If this is a non-text image region and VLM is not forced, skip VLM enrichment
                if reg_type == "image" and not call_vlm:
                    regions.append(
                        ImageRegion(
                            region_index=idx,
                            type=reg_type,
                            bbox=reg_bbox,
                            text=reg_text,
                            confidence=reg_conf,
                            extraction_model=reg_model,
                            raw=reg_raw,
                        )
                    )
                    continue

                # Reusable region-level enrichment (confidence-gated)
                enrichment = await region_enricher.enrich_region(
                    crop=reg_crop,
                    ocr_text=reg_text,
                    ocr_confidence=reg_conf,
                    content_type=reg_type,
                    metadata=reg_raw,
                    model_name=reg_model,
                    force_vlm=call_vlm,
                )

                final_text = enrichment.final_text
                final_conf = enrichment.confidence
                final_model = enrichment.extraction_method
                reg_raw.update(enrichment.metadata)
                if enrichment.vlm_invoked:
                    reg_raw["enrichment_provenance"] = enrichment.provenance
                    vlm_invoked_any = True

                if final_text:
                    text_parts.append(final_text)

                regions.append(
                    ImageRegion(
                        region_index=idx,
                        type=reg_type,
                        bbox=reg_bbox,
                        text=final_text,
                        confidence=final_conf,
                        extraction_model=final_model,
                        raw=reg_raw,
                    )
                )

        full_text = "\n".join(text_parts).strip()


        meta = {
            "source_document": source_doc,
            "image_width": img_w,
            "image_height": img_h,
            "image_format": img_format,
            "total_regions": len(regions),
            "ocr_engine": model_name,
            "vlm_invoked": vlm_invoked_any,
        }

        result = ImageParseResult(
            parser_name="image_parser",
            source_document=source_doc,
            image_width=img_w,
            image_height=img_h,
            image_format=img_format,
            extracted_regions=regions,
            full_text=full_text,
            total_pages=1,
            parser_used=f"image-{model_name}",
            metadata=meta,
        )
        result.elements = result.to_evidence_elements(document_id=document_id, file_hash=file_hash)
        return result


image_parser = ImageParser()
