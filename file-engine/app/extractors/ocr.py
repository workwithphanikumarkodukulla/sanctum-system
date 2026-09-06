"""OCR Extractor supporting PaddleOCR (PP-OCRv5) as primary with Tesseract fallback."""
from __future__ import annotations

import logging
import time
from typing import Any
import numpy as np
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

# Attempt to load PaddleOCR (PP-OCRv5)
PADDLE_AVAILABLE = False
PaddleOCRClass = None
try:
    import paddle  # type: ignore
    if hasattr(paddle, "disable_signal_handler"):
        paddle.disable_signal_handler()
    from paddleocr import PaddleOCR  # type: ignore

    PaddleOCRClass = PaddleOCR
    PADDLE_AVAILABLE = True
    logger.info("PaddleOCR (PP-OCRv5) successfully loaded.")
except (ImportError, Exception) as exc:
    logger.warning(
        "PaddleOCR failed to import (%s). "
        "Multimodal Evidence Engine running in Fallback Mode using Tesseract OCR.",
        exc,
    )

# Fallback: Tesseract
TESSERACT_AVAILABLE = False
try:
    import pytesseract  # type: ignore

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    TESSERACT_AVAILABLE = True
except (ImportError, Exception) as exc:
    logger.warning("pytesseract failed to import (%s).", exc)


from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BaseOCRExtractor(Protocol):
    """Protocol for pluggable document and image OCR extractors."""

    def extract(self, image: Image.Image) -> list[dict[str, Any]]:
        """Extract structured document regions (text, table, formula, image)."""
        ...


class OCRExtractor:
    """Primary OCR engine supporting PaddleOCR (PP-OCRv5) and Tesseract fallback."""

    def __init__(self, enable_paddle: bool | None = None) -> None:
        self.paddle_engine = None
        should_enable = settings.ENABLE_PADDLE_OCR if enable_paddle is None else enable_paddle
        if should_enable and PADDLE_AVAILABLE and PaddleOCRClass is not None:
            try:
                self.paddle_engine = PaddleOCRClass(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=True,
                    lang="en",
                )
                logger.info("PaddleOCR (PP-OCRv5) initialized successfully.")
            except Exception as exc:
                logger.warning(
                    "Could not initialize PaddleOCR instance (%s). Defaulting to Tesseract fallback.",
                    exc,
                )
                self.paddle_engine = None

    @property
    def is_paddle_active(self) -> bool:
        return self.paddle_engine is not None

    def extract(self, image: Image.Image) -> list[dict[str, Any]]:
        """Extract structured document regions (text, table, formula, image).

        Returns a list of dicts with keys:
        - type: "text" | "table" | "formula" | "image"
        - bbox: [x1, y1, x2, y2]
        - text: str | None
        - confidence: float
        - extraction_model: str
        - raw: Any (optional table structure, etc.)
        """
        from app.observability.processing_trace import get_current_trace

        trace = get_current_trace()
        if self.is_paddle_active:
            t_paddle = time.perf_counter()
            if trace:
                trace.record_event(
                    stage="VISUAL_EXTRACTION",
                    component="PaddleOCR",
                    event="OCR_STARTED",
                    status="started",
                )
            try:
                results = self._extract_paddle(image)
                dur_ms = (time.perf_counter() - t_paddle) * 1000
                avg_conf = (sum(r.get("confidence", 0.0) for r in results) / len(results)) if results else 0.0
                if trace:
                    trace.record_event(
                        stage="VISUAL_EXTRACTION",
                        component="PaddleOCR",
                        event="OCR_COMPLETED",
                        status="success",
                        duration_ms=dur_ms,
                        metadata={
                            "regions": len(results),
                            "average_confidence": round(avg_conf, 4),
                        },
                    )
                return results
            except Exception as exc:
                dur_ms = (time.perf_counter() - t_paddle) * 1000
                if trace:
                    trace.record_event(
                        stage="VISUAL_EXTRACTION",
                        component="PaddleOCR",
                        event="OCR_FAILED",
                        status="error",
                        duration_ms=dur_ms,
                        error=str(exc),
                    )
                logger.warning("PaddleOCR execution failed (%s). Falling back to Tesseract.", exc)

        # Fallback to Tesseract
        t_tess = time.perf_counter()
        is_fallback = self.is_paddle_active
        if trace:
            trace.record_event(
                stage="VISUAL_EXTRACTION",
                component="Tesseract",
                event="FALLBACK_STARTED" if is_fallback else "OCR_STARTED",
                status="started",
                metadata={"reason": "PaddleOCR failure/fallback" if is_fallback else "PaddleOCR disabled"},
            )

        tess_results = self._extract_tesseract(image)
        dur_ms_tess = (time.perf_counter() - t_tess) * 1000
        avg_conf_tess = (sum(r.get("confidence", 0.0) for r in tess_results) / len(tess_results)) if tess_results else 0.0
        if trace:
            trace.record_event(
                stage="VISUAL_EXTRACTION",
                component="Tesseract",
                event="FALLBACK_COMPLETED" if is_fallback else "OCR_COMPLETED",
                status="success",
                duration_ms=dur_ms_tess,
                metadata={
                    "regions": len(tess_results),
                    "average_confidence": round(avg_conf_tess, 4),
                    "reason": "PaddleOCR failure/fallback" if is_fallback else "PaddleOCR disabled",
                },
            )
        return tess_results

    def _extract_paddle(self, image: Image.Image) -> list[dict[str, Any]]:
        orig_w, orig_h = image.size
        max_dim = max(orig_w, orig_h)
        if max_dim > 1200:
            scale = 1200.0 / max_dim
            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))
            proc_img = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
            scale_x = orig_w / new_w
            scale_y = orig_h / new_h
        else:
            proc_img = image
            scale_x = 1.0
            scale_y = 1.0

        img_np = np.array(proc_img.convert("RGB"))
        results = list(self.paddle_engine.predict(img_np))
        extracted: list[dict[str, Any]] = []

        for page in results:
            texts = page.get("rec_texts", [])
            scores = page.get("rec_scores", [])
            boxes = page.get("rec_boxes", [])
            for text, score, box in zip(texts, scores, boxes):
                clean_text = str(text or "").strip()
                if not clean_text:
                    continue
                scaled_box = [
                    round(float(box[0] * scale_x), 1),
                    round(float(box[1] * scale_y), 1),
                    round(float(box[2] * scale_x), 1),
                    round(float(box[3] * scale_y), 1),
                ]
                box_list = [round(float(c), 1) for c in (box.tolist() if hasattr(box, "tolist") else box)]
                extracted.append({
                    "type": "text",
                    "bbox": scaled_box,
                    "text": clean_text,
                    "confidence": max(0.0, min(1.0, round(float(score), 4))),
                    "extraction_model": "PaddleOCR-PP-OCRv5",
                    "raw": {"score": float(score), "orig_box": box_list},
                })

        return extracted

    def _extract_tesseract(self, image: Image.Image) -> list[dict[str, Any]]:
        """Fallback extractor using pytesseract data with line-level block grouping."""
        if not TESSERACT_AVAILABLE:
            # Fallback if neither is available: return full-image single dummy element
            return [{
                "type": "image",
                "bbox": [0.0, 0.0, float(image.width), float(image.height)],
                "text": None,
                "confidence": 0.50,
                "extraction_model": "None (OCR unavailable)",
                "raw": {},
            }]

        try:
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
            )
        except Exception as exc:
            logger.error("Tesseract execution failed: %s", exc)
            return [{
                "type": "text",
                "bbox": [0.0, 0.0, float(image.width), float(image.height)],
                "text": None,
                "confidence": 0.10,
                "extraction_model": "Tesseract (error)",
                "raw": {},
            }]

        n_boxes = len(data["text"])
        blocks: dict[int, list[int]] = {}
        for i in range(n_boxes):
            text = str(data["text"][i]).strip()
            conf = float(data["conf"][i])
            if text and conf >= 0:
                block_num = data["block_num"][i]
                blocks.setdefault(block_num, []).append(i)

        extracted: list[dict[str, Any]] = []

        for block_num, indices in blocks.items():
            words: list[str] = []
            confs: list[float] = []
            x_min = float("inf")
            y_min = float("inf")
            x_max = 0.0
            y_max = 0.0

            for idx in indices:
                words.append(data["text"][idx])
                conf_val = max(0.0, min(100.0, float(data["conf"][idx])))
                confs.append(conf_val / 100.0)

                left = float(data["left"][idx])
                top = float(data["top"][idx])
                width = float(data["width"][idx])
                height = float(data["height"][idx])

                x_min = min(x_min, left)
                y_min = min(y_min, top)
                x_max = max(x_max, left + width)
                y_max = max(y_max, top + height)

            combined_text = " ".join(words).strip()
            if not combined_text:
                continue

            avg_conf = sum(confs) / len(confs) if confs else 0.80

            # Simple heuristic detection for table vs formula vs text
            elem_type = "text"
            has_pipe_structure = (combined_text.count("|") >= 2 and "|" in combined_text.strip()[:2] and "|" in combined_text.strip()[-2:]) or ("\n" in combined_text and combined_text.count("|") >= 4)
            has_tab_structure = len(indices) > 6 and avg_conf > 0.6 and "\t" in combined_text
            if has_pipe_structure or has_tab_structure:
                elem_type = "table"
            elif any(sym in combined_text for sym in ["\\sum", "\\int", "\\frac", "∑", "∫", "±", "√"]):
                elem_type = "formula"

            extracted.append({
                "type": elem_type,
                "bbox": [x_min, y_min, x_max, y_max],
                "text": combined_text,
                "confidence": round(avg_conf, 4),
                "extraction_model": "Tesseract-Fallback",
                "raw": {"block_num": block_num, "word_count": len(words)},
            })

        if not extracted:
            # Fallback if image contains no text words detected by Tesseract
            extracted.append({
                "type": "image",
                "bbox": [0.0, 0.0, float(image.width), float(image.height)],
                "text": None,
                "confidence": 0.70,
                "extraction_model": "Tesseract-Fallback",
                "raw": {},
            })

        return extracted


ocr_extractor = OCRExtractor()
