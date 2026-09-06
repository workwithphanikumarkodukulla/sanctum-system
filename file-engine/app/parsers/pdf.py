"""PDF parser leveraging PyMuPDF with digital extraction and scanned OCR fallback."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Sequence

from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement
from app.extractors.ocr import ocr_extractor
from app.observability.processing_trace import get_current_trace
from app.parsers.base import BaseParser, ParseResult
from app.parsers.ocr_enricher import ocr_enricher
from app.processing.image import image_processor
from app.processing.pdf import pdf_processor

logger = logging.getLogger(__name__)


@dataclass
class PdfPageResult:
    """Structured extraction result for a single PDF page."""
    page_number: int
    is_digital: bool
    text: str
    extraction_method: str  # "PyMuPDF-Direct" or "PyMuPDF+OCR"
    elements: list[EvidenceElement] = field(default_factory=list)


@dataclass
class PdfParseResult(ParseResult):
    """Structured result of PDF parsing across all pages."""
    parser_name: str = "pdf_parser"
    source_document: str = ""
    pages: list[PdfPageResult] = field(default_factory=list)
    full_text: str = ""


class PDFParser(BaseParser):
    """Parses PDF documents with automatic digital extraction and scanned image/OCR fallback."""

    @classmethod
    def _read_bytes(cls, input_data: bytes | BinaryIO | str | Path) -> bytes:
        if hasattr(input_data, "read"):
            return input_data.read()
        if isinstance(input_data, (str, Path)):
            with open(input_data, "rb") as f:
                return f.read()
        if isinstance(input_data, bytes):
            return input_data
        if isinstance(input_data, (bytearray, memoryview)):
            return bytes(input_data)
        raise TypeError(f"Expected bytes, Path, or file stream, got {type(input_data).__name__}")

    async def parse(
        self,
        file_bytes: bytes | BinaryIO | str | Path,
        filename: str = "",
        document_id: str = "doc_pdf",
        file_hash: str = "",
        **kwargs: Any,
    ) -> PdfParseResult:
        """Execute PDF parsing: inspect each page, extract digitally or fallback to OCR, and assemble elements."""
        raw_bytes = self._read_bytes(file_bytes)
        source_doc = filename or "document.pdf"

        if not raw_bytes:
            raise ValueError("Uploaded PDF file is empty (0 bytes).")

        doc = None
        all_elements: list[EvidenceElement] = []
        page_results: list[PdfPageResult] = []
        total_pages = 0
        digital_pages = 0
        scanned_pages = 0

        running_headers: list[str] | None = None

        try:
            doc = pdf_processor.load_pdf(raw_bytes)
            total_pages = len(doc)

            for page_idx in range(total_pages):
                page_num = page_idx + 1
                page = doc[page_idx]

                trace = get_current_trace()
                # 1. Inspect page for digital text vs scanned image and reconstruct tables
                inspection = pdf_processor.inspect_page(
                    page=page,
                    page_num=page_num,
                    prev_headers=running_headers,
                )
                is_digital = inspection["is_digital"]
                if inspection.get("detected_headers"):
                    running_headers = inspection["detected_headers"]

                if trace:
                    trace.record_event(
                        stage="NATIVE_EXTRACTION",
                        component="PyMuPDF",
                        event="PAGE_INSPECTED",
                        status="success",
                        metadata={"page": page_num, "is_digital": is_digital},
                    )

                if is_digital:
                    logger.info("Page %d is digitally readable; extracting directly via PyMuPDF.", page_num)
                    digital_pages += 1
                    raw_elements = inspection["elements"]
                    method = "PyMuPDF-Direct"
                    page_text = inspection["raw_text"]

                    if trace:
                        trace.record_event(
                            stage="NATIVE_EXTRACTION",
                            component="PyMuPDF",
                            event="TEXT_EXTRACTED",
                            status="success",
                            metadata={
                                "page": page_num,
                                "characters": len(page_text),
                                "elements": len(raw_elements),
                            },
                        )

                    page_elements: list[EvidenceElement] = []
                    for idx, r in enumerate(raw_elements, start=1):
                        t_data = r.get("table_data")
                        raw_meta = dict(r.get("raw") or {})
                        elem = EvidenceBuilder.build_element(
                            element_idx=idx,
                            document_id=document_id,
                            page=page_num,
                            elem_type=r.get("type", "text"),
                            text=r.get("text"),
                            table_data=t_data,
                            bbox=r.get("bbox"),
                            confidence=float(r.get("confidence", 0.98)),
                            extraction_model=r.get("extraction_model", "PyMuPDF-Direct"),
                            file_hash=file_hash,
                            provenance={
                                "source": "pdf",
                                "page": page_num,
                                "extraction_method": method,
                            },
                            metadata=raw_meta if raw_meta else None,
                        )
                        page_elements.append(elem)

                else:
                    logger.info("Page %d is scanned/image-only; rendering to image for OCR.", page_num)
                    scanned_pages += 1
                    page_image = pdf_processor.render_page_to_image(page)

                    if trace:
                        trace.record_event(
                            stage="VISUAL_EXTRACTION",
                            component="PyMuPDF",
                            event="PAGE_RENDERED_FOR_OCR",
                            status="success",
                            metadata={"page": page_num, "reason": "Scanned page / no digital text"},
                        )

                    preprocessed = image_processor.preprocess_for_ocr(page_image)
                    raw_elements = ocr_extractor.extract(preprocessed)

                    page_elements = await ocr_enricher.enrich_and_build_elements(
                        raw_elements=raw_elements,
                        page_image=page_image,
                        page_num=page_num,
                        document_id=document_id,
                        file_hash=file_hash,
                    )
                    ocr_name = "PaddleOCR" if ocr_extractor.is_paddle_active else "Tesseract"
                    method = f"PyMuPDF+OCR({ocr_name})"
                    page_text = "\n".join(e.text for e in page_elements if e.text)

                p_res = PdfPageResult(
                    page_number=page_num,
                    is_digital=is_digital,
                    text=page_text,
                    extraction_method=method,
                    elements=page_elements,
                )
                page_results.append(p_res)
                all_elements.extend(page_elements)

        finally:
            if doc is not None:
                doc.close()

        full_doc_text = "\n\n".join(p.text for p in page_results if p.text).strip()

        # Multi-page table continuation summary across document
        table_elements_all = [el for el in all_elements if el.type == "table" and el.table_data]
        continued_tables_summary = []
        if len(table_elements_all) > 1:
            total_rows_all = sum(len(el.table_data.get("rows", [])) for el in table_elements_all)
            project_rows_count = sum(
                1 for el in table_elements_all for r in el.table_data.get("rows", [])
                if r and r[0] and str(r[0]).strip().isdigit()
            )
            common_headers = table_elements_all[0].table_data.get("headers", [])
            continued_tables_summary.append({
                "table_id": "continued_table_1",
                "start_page": table_elements_all[0].page,
                "end_page": table_elements_all[-1].page,
                "total_pages": len(set(el.page for el in table_elements_all)),
                "headers": common_headers,
                "total_rows": total_rows_all,
                "project_rows_count": project_rows_count,
            })

        meta = {
            "source_document": source_doc,
            "total_pages": total_pages,
            "digital_pages": digital_pages,
            "scanned_pages": scanned_pages,
            "total_elements": len(all_elements),
            "continued_tables": continued_tables_summary,
        }

        return PdfParseResult(
            elements=all_elements,
            total_pages=max(1, total_pages),
            parser_used="PyMuPDF",
            parser_name="pdf_parser",
            source_document=source_doc,
            pages=page_results,
            full_text=full_doc_text,
            metadata=meta,
        )


pdf_parser = PDFParser()
