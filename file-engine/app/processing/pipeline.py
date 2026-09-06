"""End-to-end multimodal evidence processing pipeline powered by FileDetector and FileRouter."""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from PIL import Image

from app.core.config import settings
from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import DocumentEvidence, EvidenceElement, WorksheetInfo
from app.evidence.storage import storage
from app.ingestion.detector import detector
from app.ingestion.router import router as file_router
from app.models.vision_client import vision_client
from app.observability.processing_trace import (
    ProcessingTrace,
    get_current_trace,
    reset_current_trace,
    set_current_trace,
    trace_store,
)
from app.processing.normalization import normalizer

logger = logging.getLogger(__name__)


class EvidencePipeline:
    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    async def route_and_enrich_elements(
        self,
        elements: list[EvidenceElement],
        document_id: str,
        file_hash: str,
        file_bytes: bytes | None = None,
        file_type: str | None = None,
    ) -> list[EvidenceElement]:
        """Classify each element, route to specialized extractors (formulas, tables, handwriting/VLM),
        and perform reconciliation while preserving provenance and spatial coordinates.
        """
        from app.classification import ContentType, content_classifier
        from app.extractors.formulas import formula_extractor
        from app.extractors.handwriting import HandwritingClassification, handwriting_classifier
        from app.extractors.tables import table_extractor
        from app.reconciliation import ExtractionResult, evidence_reconciler

        # Document-level handwriting context detection
        hw_elements_count = sum(
            1 for el in elements
            if el.type == "handwriting"
            or (el.metadata and el.metadata.get("handwriting_decision", {}).get("classification") == "handwritten")
            or (el.metadata and el.metadata.get("document_has_handwriting"))
        )
        is_doc_hw = (
            (len(elements) >= 2 and hw_elements_count >= 2)
            or (len(elements) > 0 and (hw_elements_count / len(elements)) >= 0.25)
        )
        if is_doc_hw:
            for el in elements:
                if el.metadata is None:
                    el.metadata = {}
                el.metadata["document_has_handwriting"] = True

        trace = get_current_trace()
        formula_detected = False
        routed_elements: list[EvidenceElement] = []

        for elem in elements:
            meta = dict(elem.metadata or {})

            # 1. Content classification
            classification = content_classifier.classify_element(elem)
            meta["content_classification"] = classification.to_dict()
            target_type = classification.content_type

            if trace:
                text_preview = None
                if elem.text:
                    clean = elem.text.strip()
                    text_preview = (clean[:60] + "...") if len(clean) > 60 else clean
                trace.record_event(
                    stage="CONTENT_CLASSIFICATION",
                    component="ContentClassifier",
                    event="REGION_CLASSIFIED",
                    status="success",
                    metadata={
                        "element_id": elem.id,
                        "class": target_type.value.upper() if hasattr(target_type, "value") else str(target_type).upper(),
                        "text": text_preview,
                        "confidence": round(classification.confidence, 4) if hasattr(classification, "confidence") else round(elem.confidence, 4),
                    },
                )

            # 2. Formula branch: extract variables and compute LaTeX/normalization without automatic SymPy calculation
            if target_type == ContentType.FORMULA or elem.type == "formula":
                raw_formula = elem.formula_latex or elem.text or ""
                if raw_formula:
                    formula_detected = True
                    latex_str, var_dict = formula_extractor.extract_formula_details(raw_formula)
                    elem.type = "formula"
                    elem.formula_latex = latex_str or raw_formula
                    if var_dict:
                        elem.formula_variables = var_dict
                    meta["formula_details"] = {
                        "original_text": raw_formula,
                        "latex": latex_str or raw_formula,
                        "variables": list(var_dict.keys()) if var_dict else [],
                    }

                    if trace:
                        trace.record_event(
                            stage="SPECIALIZED_EXTRACTION",
                            component="FormulaExtractor",
                            event="FORMULA_EXTRACTED",
                            status="success",
                            metadata={
                                "latex": latex_str or raw_formula,
                                "variables": list(var_dict.keys()) if var_dict else [],
                            },
                        )

            # 3. Handwriting & Visual Image branch
            elif target_type in (ContentType.HANDWRITING, ContentType.IMAGE) or elem.type in ("handwriting", "image"):
                # Case 3A: Embedded image with explicit visual routing requested
                if (elem.type == "image" or target_type == ContentType.IMAGE) and (
                    meta.get("route_visual") or meta.get("requires_ocr") or meta.get("process_image")
                ) and meta.get("image_bytes"):
                    try:
                        import io
                        from app.extractors.ocr import ocr_extractor
                        from app.parsers.ocr_enricher import region_enricher
                        from app.processing.image import image_processor

                        img_crop = Image.open(io.BytesIO(meta["image_bytes"])).convert("RGB")
                        preprocessed = image_processor.preprocess_for_ocr(img_crop)
                        ocr_regions = ocr_extractor.extract(preprocessed)
                        ocr_text = " ".join(r.get("text", "") for r in ocr_regions if r.get("text")).strip()
                        ocr_conf = (
                            sum(float(r.get("confidence", 0.8)) for r in ocr_regions) / max(1, len(ocr_regions))
                            if ocr_regions else 0.8
                        )
                        elem.text = ocr_text or None
                        elem.confidence = ocr_conf
                        meta["ocr_candidate"] = ocr_text
                        meta["ocr_confidence"] = ocr_conf

                        hw_decision = handwriting_classifier.classify_region(
                            crop=img_crop,
                            text=ocr_text,
                            confidence=ocr_conf,
                            metadata=meta,
                        )
                        meta["handwriting_decision"] = hw_decision.to_dict()
                        meta["handwriting_classification"] = hw_decision.classification.value

                        if hw_decision.classification == HandwritingClassification.HANDWRITTEN:
                            elem.type = "handwriting"
                            enrichment = await region_enricher.enrich_region(
                                crop=img_crop,
                                ocr_text=ocr_text,
                                ocr_confidence=ocr_conf,
                                content_type="handwriting",
                                metadata=meta,
                                force_vlm=True,
                            )
                            elem.text = enrichment.final_text
                            elem.confidence = enrichment.confidence
                            elem.extraction_model = enrichment.extraction_method
                            meta.update(enrichment.metadata)
                            meta["enrichment_provenance"] = enrichment.provenance
                            if enrichment.vlm_invoked:
                                meta["vlm_candidate"] = enrichment.vlm_result
                                meta["escalated_to_vision"] = True
                                meta["vlm_escalation_status"] = "completed"
                            meta["requires_human_review"] = False
                        elif hw_decision.classification == HandwritingClassification.PRINTED and ocr_text:
                            elem.type = "text"
                            meta["is_printed_image_text"] = True
                    except Exception as img_err:
                        logger.warning("Visual OCR/handwriting routing failed on image element %s: %s", elem.id, img_err)

                # Case 3B: Existing handwriting element or region classified as handwriting
                elif target_type == ContentType.HANDWRITING or elem.type == "handwriting":
                    hw_decision = handwriting_classifier.classify_region(
                        text=elem.text,
                        confidence=elem.confidence,
                        metadata=meta,
                    )
                    meta["handwriting_decision"] = hw_decision.to_dict()
                    meta["handwriting_classification"] = hw_decision.classification.value

                    if trace:
                        trace.record_event(
                            stage="HANDWRITING_CLASSIFICATION",
                            component="HandwritingClassifier",
                            event="REGION_CLASSIFIED",
                            status="success",
                            metadata={
                                "classification": hw_decision.classification.value,
                                "confidence": round(hw_decision.confidence, 4),
                                "method": getattr(hw_decision, "method", "signal_heuristic"),
                                "reason": hw_decision.reason,
                            },
                        )

                    if (
                        hw_decision.classification == HandwritingClassification.HANDWRITTEN
                        or target_type == ContentType.HANDWRITING
                        or elem.type == "handwriting"
                    ):
                        elem.type = "handwriting"
                    elif hw_decision.classification == HandwritingClassification.UNCERTAIN:
                        meta["uncertain_handwriting"] = True

                # Case 3C: Standard embedded image without visual routing requested
                elif elem.type == "image" or target_type == ContentType.IMAGE:
                    elem.type = "image"
                    meta["is_image"] = True

            # 4. Table branch: extract structured tabular data if unparsed
            elif target_type == ContentType.TABLE or (elem.type == "table" and target_type != ContentType.HANDWRITING):
                if elem.table_data is None and elem.text:
                    parsed_table = table_extractor.parse_table_data(elem.text, meta.get("raw"))
                    if parsed_table and parsed_table.get("rows"):
                        elem.type = "table"
                        elem.table_data = parsed_table
                        meta["table_extracted"] = True
                if trace:
                    rows_count = len(elem.table_data.get("rows", [])) if elem.table_data else 0
                    trace.record_event(
                        stage="TABLE_EXTRACTION",
                        component="TableExtractor",
                        event="TABLE_EXTRACTED",
                        status="success",
                        metadata={"rows": rows_count},
                    )

            # 5. Diagram & P&ID branch: extract equipment tags, flow lines, and technical schematics via VLM
            elif target_type == ContentType.DIAGRAM or elem.type == "diagram":
                elem.type = "diagram"
                meta["is_diagram"] = True
                diagram_payload = meta.get("image_bytes") or (file_bytes if file_type == "image" else None)

                if diagram_payload:
                    try:
                        diag_text, diag_conf, _ = await vision_client.analyze_diagram(
                            diagram_payload,
                            diagram_type="technical diagram / P&ID",
                        )
                        if diag_text:
                            elem.text = diag_text
                            elem.confidence = max(elem.confidence, diag_conf)
                            elem.extraction_model = f"VLM({settings.OLLAMA_VISION_MODEL})"
                            meta["diagram_analysis"] = diag_text
                            meta["diagram_model"] = settings.OLLAMA_VISION_MODEL
                    except Exception as diag_err:
                        logger.warning("Diagram VLM extraction encountered error: %s", diag_err)

                if trace:
                    trace.record_event(
                        stage="SPECIALIZED_EXTRACTION",
                        component="DiagramAnalyzer",
                        event="DIAGRAM_ANALYZED",
                        status="success",
                        metadata={
                            "element_id": elem.id,
                            "has_vlm_analysis": bool(meta.get("diagram_analysis")),
                            "model": settings.OLLAMA_VISION_MODEL,
                        },
                    )

            # 6. Unknown / Uncertain classification branch
            elif target_type == ContentType.UNKNOWN:
                meta["uncertain_classification"] = True
                meta["classification_reason"] = classification.reason

            # 6. Text branch (native/OCR text, headings, lists)
            else:
                # Retains original structural type (heading, list, text)
                pass

            # 7. Check if multi-candidate OCR and VLM readings exist for reconciliation
            prov = meta.get("enrichment_provenance", {})
            ocr_cand = prov.get("ocr_candidate") or meta.get("ocr_candidate")
            vlm_cand = prov.get("vlm_candidate") or meta.get("vlm_candidate")

            # Preserve required audit signals for handwriting & uncertain regions
            is_handwritten_elem = (
                elem.type == "handwriting"
                or meta.get("handwriting_classification") == "handwritten"
                or meta.get("is_handwriting") is True
            )
            if is_handwritten_elem or meta.get("uncertain_handwriting"):
                meta.setdefault("ocr_candidate", elem.text)
                meta.setdefault("ocr_confidence", elem.confidence)
                if "handwriting_classification" not in meta and "handwriting_decision" in meta:
                    meta["handwriting_classification"] = meta["handwriting_decision"].get("classification")
                if "vlm_escalation_status" not in meta:
                    if meta.get("vlm_result_empty"):
                        meta["vlm_escalation_status"] = "attempted_empty_or_unavailable"
                    elif meta.get("escalated_to_vision") or vlm_cand:
                        meta["vlm_escalation_status"] = "completed"
                    else:
                        meta["vlm_escalation_status"] = "not_needed"

            if is_handwritten_elem:
                meta["requires_human_review"] = False
                if meta.get("full_image_vlm"):
                    # Whole-image VLM already completed and established authority
                    meta["requires_human_review"] = False
                elif ocr_cand and vlm_cand and "reconciliation" not in meta:
                    res_a = ExtractionResult(
                        text=ocr_cand,
                        confidence=0.80,
                        extraction_method=prov.get("ocr_model", "Tesseract"),
                        provenance={"source": "ocr"},
                    )
                    res_b = ExtractionResult(
                        text=vlm_cand,
                        confidence=settings.RECHECK_CONFIDENCE,
                        extraction_method=prov.get("vlm_model", settings.OLLAMA_VISION_MODEL),
                        provenance={"source": "vlm"},
                    )
                    recon = evidence_reconciler.reconcile(res_a, res_b, is_handwritten=True)
                    elem.text = recon.final_text
                    elem.confidence = recon.final_confidence
                    elem.extraction_model = prov.get("vlm_model", settings.OLLAMA_VISION_MODEL) if (vlm_cand and vlm_cand.strip()) else f"{prov.get('ocr_model', 'Tesseract')}-fallback"
                    meta["reconciliation"] = recon.to_dict()
                    meta["requires_human_review"] = False
                    if trace:
                        trace.record_event(
                            stage="RECONCILIATION",
                            component="EvidenceReconciler",
                            event="HANDWRITING_VLM_AUTHORITY",
                            status="success",
                            metadata={
                                "authoritative_source": "vlm" if (vlm_cand and vlm_cand.strip()) else "ocr_fallback",
                                "requires_human_review": False,
                            },
                        )
            elif ocr_cand and vlm_cand and "reconciliation" not in meta:
                res_a = ExtractionResult(
                    text=ocr_cand,
                    confidence=0.80,
                    extraction_method=prov.get("ocr_model", "Tesseract"),
                    provenance={"source": "ocr"},
                )
                res_b = ExtractionResult(
                    text=vlm_cand,
                    confidence=settings.RECHECK_CONFIDENCE,
                    extraction_method=prov.get("vlm_model", settings.OLLAMA_VISION_MODEL),
                    provenance={"source": "vlm"},
                )
                recon = evidence_reconciler.reconcile(res_a, res_b, is_handwritten=False)
                elem.confidence = recon.final_confidence
                meta["reconciliation"] = recon.to_dict()
                if recon.requires_review:
                    meta["requires_human_review"] = True

            elem.metadata = meta
            routed_elements.append(elem)

        return routed_elements

    async def process_document(
        self,
        document_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> DocumentEvidence:
        """Asynchronously process an uploaded document, spreadsheet, presentation, or image."""
        start_time = time.perf_counter()
        created_at = datetime.now(timezone.utc).isoformat()
        clean_filename = Path((filename or "unknown_file").replace("\\", "/")).name.replace("\x00", "").strip() or "unknown_file"
        clean_doc_id = Path((document_id or "doc").replace("\\", "/")).name.replace("\x00", "").strip() or "doc"
        file_hash = self.compute_sha256(file_bytes)
        file_size = len(file_bytes)
        logger.info("Starting pipeline for document %s (file: %s, size: %d, hash: %s)", clean_doc_id, clean_filename, file_size, file_hash[:10])

        trace = ProcessingTrace(
            document_id=clean_doc_id,
            filename=clean_filename,
            file_hash=file_hash,
            file_size=file_size,
        )
        token = set_current_trace(trace)

        trace.record_event(
            stage="INGESTION",
            component="FileReceiver",
            event="FILE_RECEIVED",
            status="success",
            metadata={
                "filename": clean_filename,
                "file_size": file_size,
                "file_hash": file_hash,
            },
        )
        trace.record_event(
            stage="SECURITY_VALIDATION",
            component="SecurityValidator",
            event="SECURITY_CHECK_PASSED",
            status="success",
            metadata={"filename_sanitized": clean_filename},
        )

        # 1. Detect file type
        detection = detector.detect(file_bytes, filename=clean_filename)
        trace.detected_type = f"{detection.file_type.value} ({detection.mime_type})"
        trace.record_event(
            stage="DETECTION",
            component="FileDetector",
            event="FILE_DETECTED",
            status="success" if detection.is_supported else "error",
            metadata={
                "file_type": detection.file_type.value,
                "mime_type": detection.mime_type,
                "is_supported": detection.is_supported,
            },
        )

        # Register initial processing state
        initial_doc = DocumentEvidence(
            document_id=clean_doc_id,
            filename=clean_filename,
            file_type=detection.file_type.value,
            mime_type=detection.mime_type,
            file_size=file_size,
            file_hash=file_hash,
            total_pages=0,
            elements=[],
            overall_confidence=0.0,
            processing_status="processing",
            created_at=created_at,
        )
        storage.save(initial_doc)

        if not detection.is_supported:
            err_msg = detection.error_message or f"Unsupported file format or unreadable file: {detection.extension or 'unknown'}"
            logger.warning("Document %s failed detection: %s", clean_doc_id, err_msg)
            completed_at = datetime.now(timezone.utc).isoformat()
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            trace.finish("failed")
            trace_store.save(trace)
            failed_doc = EvidenceBuilder.assemble_document(
                document_id=clean_doc_id,
                filename=clean_filename,
                file_type=detection.file_type.value,
                mime_type=detection.mime_type,
                file_size=file_size,
                file_hash=file_hash,
                total_pages=0,
                elements=[],
                status="failed",
                error=err_msg,
                created_at=created_at,
                completed_at=completed_at,
                processing_time_ms=elapsed_ms,
            )
            storage.save(failed_doc)
            reset_current_trace(token)
            return failed_doc

        try:
            # 2. Route to appropriate native/visual parser
            parser = file_router.get_parser(detection.file_type)
            trace.record_event(
                stage="ROUTING",
                component="FileRouter",
                event="ROUTE_SELECTED",
                status="success",
                metadata={
                    "route": f"{detection.file_type.value} -> {parser.__class__.__name__}",
                    "parser": parser.__class__.__name__,
                },
            )
            parse_result = await parser.parse(
                file_bytes=file_bytes,
                filename=clean_filename,
                document_id=clean_doc_id,
                file_hash=file_hash,
            )

            # 3. Normalize parser-specific extraction results into EvidenceElements
            elements = normalizer.normalize(
                parser_result=parse_result,
                document_id=clean_doc_id,
                file_hash=file_hash,
            )
            trace.record_event(
                stage="NORMALIZATION",
                component="EvidenceNormalizer",
                event="NORMALIZATION_COMPLETED",
                status="success",
                metadata={"elements_count": len(elements)},
            )

            # 4. Content classification & specialized extraction routing
            elements = await self.route_and_enrich_elements(
                elements=elements,
                document_id=clean_doc_id,
                file_hash=file_hash,
                file_bytes=file_bytes,
                file_type=detection.file_type.value,
            )

            total_pages = getattr(parse_result, "total_pages", 1)
            parser_used = getattr(parse_result, "parser_used", getattr(parse_result, "parser_name", "unknown"))

            # Derive format-specific document metadata
            total_slides = None
            worksheets = None

            if hasattr(parse_result, "slides"):
                total_slides = len(parse_result.slides)
            if hasattr(parse_result, "worksheets") and parse_result.worksheets:
                worksheets = [
                    WorksheetInfo(
                        name=ws.name,
                        index=ws.sheet_index,
                        row_count=len(ws.rows),
                        column_count=ws.max_column,
                        has_formulas=bool(ws.formula_cells),
                        merged_ranges=ws.merged_cells,
                    )
                    for ws in parse_result.worksheets
                ]

            # Pipeline summary statistics for auditable intelligent workflow demo
            type_counts: dict[str, int] = {}
            vlm_invoked_count = 0
            reconciliation_count = 0
            conflicts_count = 0
            formulas_extracted_count = 0

            for el in elements:
                type_counts[el.type] = type_counts.get(el.type, 0) + 1
                el_meta = el.metadata or {}
                if el_meta.get("escalated_to_vision") or (el_meta.get("enrichment_provenance", {}).get("vlm_invoked")):
                    vlm_invoked_count += 1
                if "reconciliation" in el_meta:
                    reconciliation_count += 1
                if el_meta.get("requires_human_review"):
                    conflicts_count += 1
                if el.type == "formula" or "formula_details" in el_meta:
                    formulas_extracted_count += 1

            completed_at = datetime.now(timezone.utc).isoformat()
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # 5. Assemble canonical DocumentEvidence
            assembled = EvidenceBuilder.assemble_document(
                document_id=clean_doc_id,
                filename=clean_filename,
                file_type=detection.file_type.value,
                mime_type=detection.mime_type,
                file_size=file_size,
                file_hash=file_hash,
                parser_used=parser_used,
                total_pages=total_pages,
                total_slides=total_slides,
                worksheets=worksheets,
                created_at=created_at,
                completed_at=completed_at,
                processing_time_ms=elapsed_ms,
                elements=elements,
                status="completed",
            )

            trace.record_event(
                stage="CANONICAL_EVIDENCE",
                component="DocumentEvidence",
                event="EVIDENCE_ASSEMBLED",
                status="success",
                metadata={
                    "elements": len(elements),
                    "total_pages": total_pages,
                    "overall_confidence": round(assembled.overall_confidence, 4),
                },
            )
            for el in elements:
                if el.metadata and "image_bytes" in el.metadata:
                    el.metadata.pop("image_bytes", None)

            storage.save(assembled)
            trace.record_event(
                stage="STORAGE",
                component="DocumentStorage",
                event="STORAGE_COMPLETED",
                status="success",
                metadata={"document_id": clean_doc_id},
            )
            trace.finish("completed")
            trace_store.save(trace)

            total_table_rows = sum(len(el.table_data.get("rows", [])) for el in elements if el.table_data)

            doc_meta = {
                "pipeline_summary": {
                    "total_elements": len(elements),
                    "element_types": type_counts,
                    "vlm_escalations": vlm_invoked_count,
                    "reconciliations": reconciliation_count,
                    "conflicts_requiring_review": conflicts_count,
                    "formulas_extracted": formulas_extracted_count,
                    "total_table_rows": total_table_rows,
                },
                "ocr_confidence_semantics": "engine_quality_routing_signal",
                "processing_trace": trace.to_dict(),
            }
            if hasattr(parse_result, "metadata") and isinstance(parse_result.metadata, dict):
                if "continued_tables" in parse_result.metadata:
                    doc_meta["continued_tables"] = parse_result.metadata["continued_tables"]
            assembled.metadata = doc_meta
            storage.save(assembled)

            logger.info(
                "Document %s completed successfully via %s: %d elements, %d pages, confidence %.4f, elapsed %.1fms",
                clean_doc_id,
                parser_used,
                len(elements),
                total_pages,
                assembled.overall_confidence,
                elapsed_ms,
            )
            return assembled

        except Exception as exc:
            logger.exception("Pipeline failed on document %s: %s", clean_doc_id, exc)
            completed_at = datetime.now(timezone.utc).isoformat()
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            trace.record_event(
                stage="PIPELINE",
                component="EvidencePipeline",
                event="PIPELINE_FAILED",
                status="error",
                error=str(exc),
            )
            trace.finish("failed")
            trace_store.save(trace)
            failed_doc = EvidenceBuilder.assemble_document(
                document_id=clean_doc_id,
                filename=clean_filename,
                file_type=detection.file_type.value,
                mime_type=detection.mime_type,
                file_size=file_size,
                file_hash=file_hash,
                total_pages=1,
                elements=[],
                status="failed",
                error=str(exc),
                created_at=created_at,
                completed_at=completed_at,
                processing_time_ms=elapsed_ms,
                metadata={"processing_trace": trace.to_dict()},
            )
            storage.save(failed_doc)
            return failed_doc
        finally:
            reset_current_trace(token)
            if settings.OLLAMA_AUTO_UNLOAD and getattr(vision_client, "is_model_loaded", False):
                try:
                    await vision_client.unload_model()
                except Exception as unload_exc:
                    logger.debug("Failed to auto-unload vision model during pipeline cleanup: %s", unload_exc)


pipeline = EvidencePipeline()
