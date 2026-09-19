"""Canonical normalization layer transforming parser-specific outputs into EvidenceElements."""
from __future__ import annotations

import logging
from typing import Any, Sequence

from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement

logger = logging.getLogger(__name__)


class EvidenceNormalizer:
    """Normalizes parser-specific parsing structures into the canonical EvidenceElement format."""

    @classmethod
    def normalize(
        cls,
        parser_result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        """Convert parser output into a list of canonical EvidenceElements with provenance.

        Args:
            parser_result: Output from any supported native or visual parser.
            document_id: Unique document identifier.
            file_hash: SHA-256 hash of the input file.

        Returns:
            list of validated EvidenceElement models.
        """
        # 1. DOCX parsing result normalization
        from app.parsers.docx import DocxParagraph, DocxParseResult, DocxTable
        if isinstance(parser_result, DocxParseResult):
            return cls._normalize_docx(parser_result, document_id, file_hash)

        # 2. PPTX parsing result normalization
        from app.parsers.pptx import (
            PptxImageItem,
            PptxParseResult,
            PptxTableItem,
            PptxTextItem,
        )
        if isinstance(parser_result, PptxParseResult):
            return cls._normalize_pptx(parser_result, document_id, file_hash)

        # 3. XLSX parsing result normalization
        from app.parsers.xlsx import XlsxParseResult
        if isinstance(parser_result, XlsxParseResult):
            return cls._normalize_xlsx(parser_result, document_id, file_hash)

        # 4. CSV parsing result normalization
        from app.parsers.csv import CsvParseResult
        if isinstance(parser_result, CsvParseResult):
            return cls._normalize_csv(parser_result, document_id, file_hash)

        # 5. TXT parsing result normalization
        from app.parsers.txt import TxtParseResult
        if isinstance(parser_result, TxtParseResult):
            return cls._normalize_txt(parser_result, document_id, file_hash)

        # 6. Image parsing result normalization
        from app.parsers.image import ImageParseResult
        if isinstance(parser_result, ImageParseResult):
            return cls._normalize_image(parser_result, document_id, file_hash)

        # 7. PDF parsing result normalization
        from app.parsers.pdf import PdfParseResult
        if isinstance(parser_result, PdfParseResult):
            return cls._normalize_pdf(parser_result, document_id, file_hash)

        # 8. Direct list of EvidenceElements or object with .elements attribute
        if isinstance(parser_result, list) and all(isinstance(e, EvidenceElement) for e in parser_result):
            return [
                cls._normalize_fallback_element(elem, idx, document_id, file_hash)
                for idx, elem in enumerate(parser_result, start=1)
            ]

        if hasattr(parser_result, "to_evidence_elements") and callable(parser_result.to_evidence_elements):
            elements = parser_result.to_evidence_elements(document_id=document_id, file_hash=file_hash)
            return [
                cls._normalize_fallback_element(elem, idx, document_id, file_hash)
                for idx, elem in enumerate(elements, start=1)
            ]

        if hasattr(parser_result, "elements") and isinstance(parser_result.elements, list):
            return [
                cls._normalize_fallback_element(elem, idx, document_id, file_hash)
                for idx, elem in enumerate(parser_result.elements, start=1)
            ]

        logger.warning("Unrecognized parser result type: %s. Returning empty elements.", type(parser_result).__name__)
        return []

    @classmethod
    def _normalize_docx(
        cls,
        result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        from app.parsers.docx import DocxParagraph, DocxTable
        elements: list[EvidenceElement] = []

        for idx, item in enumerate(result.items, start=1):
            reading_order = getattr(item, "reading_order", idx)
            if isinstance(item, DocxParagraph):
                # Classify type: heading vs list vs text
                elem_type = "text"
                if item.is_heading:
                    elem_type = "heading"
                elif (
                    item.style.lower().startswith("list")
                    or item.style.lower().startswith("bullet")
                    or item.text.strip().startswith(("•", "-", "*", "–", "—"))
                ):
                    elem_type = "list"

                elem = EvidenceBuilder.build_element(
                    element_idx=idx,
                    document_id=document_id,
                    page=1,
                    elem_type=elem_type,
                    text=item.text,
                    bbox=[0.0, 0.0, 0.0, 0.0],
                    confidence=1.0,
                    extraction_model="python-docx",
                    file_hash=file_hash,
                    reading_order=reading_order,
                    provenance={
                        "source": "docx",
                        "document": item.source_document,
                        "paragraph_index": item.index,
                        "style": item.style,
                        "reading_order": reading_order,
                    },
                    metadata={
                        "source_document": item.source_document,
                        "paragraph_index": item.index,
                        "reading_order": reading_order,
                        "style": item.style,
                        "is_heading": item.is_heading,
                        "heading_level": item.heading_level,
                    },
                )
                elements.append(elem)

            elif isinstance(item, DocxTable):
                elem = EvidenceBuilder.build_element(
                    element_idx=idx,
                    document_id=document_id,
                    page=1,
                    elem_type="table",
                    text=item.text,
                    table_data={"headers": item.headers, "rows": item.rows},
                    bbox=[0.0, 0.0, 0.0, 0.0],
                    confidence=1.0,
                    extraction_model="python-docx",
                    file_hash=file_hash,
                    reading_order=reading_order,
                    provenance={
                        "source": "docx",
                        "document": item.source_document,
                        "table_index": item.index,
                        "reading_order": reading_order,
                    },
                    metadata={
                        "source_document": item.source_document,
                        "table_index": item.index,
                        "reading_order": reading_order,
                        "num_rows": item.num_rows,
                        "num_cols": item.num_cols,
                    },
                )
                elements.append(elem)

        return elements

    @classmethod
    def _normalize_pptx(
        cls,
        result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        from app.parsers.pptx import (
            PptxImageItem,
            PptxTableItem,
            PptxTextItem,
        )
        elements: list[EvidenceElement] = []
        elem_idx = 1

        for slide in result.slides:
            for item in slide.items:
                reading_order = getattr(item, "reading_order", elem_idx)
                prov = {
                    "source": "pptx",
                    "document_id": document_id,
                    "slide": item.slide_number,
                    "shape_name": item.shape_name,
                    "shape_id": item.shape_id,
                    "reading_order": reading_order,
                    "bbox": item.bbox,
                    "extraction_model": "python-pptx",
                    "file_hash": file_hash,
                }

                if isinstance(item, PptxTextItem):
                    is_bullet = getattr(item, "is_bullet_list", False) or any(
                        line.strip().startswith(("•", "-", "*", "–", "—"))
                        for line in item.text.splitlines()
                        if line.strip()
                    )
                    elem_type = "heading" if item.is_title else ("list" if is_bullet else "text")

                    elem = EvidenceBuilder.build_element(
                        element_idx=elem_idx,
                        document_id=document_id,
                        page=item.slide_number,
                        elem_type=elem_type,
                        text=item.text,
                        bbox=item.bbox,
                        confidence=1.0,
                        extraction_model="python-pptx",
                        file_hash=file_hash,
                        slide=item.slide_number,
                        reading_order=reading_order,
                        provenance=prov,
                        metadata={
                            "is_title": item.is_title,
                            "is_heading": item.is_title,
                            "is_list": is_bullet,
                            "is_native_text": True,
                            "is_digital": True,
                            "shape_name": item.shape_name,
                            "shape_id": item.shape_id,
                            "reading_order": reading_order,
                            "source": "pptx",
                        },
                    )
                    elements.append(elem)
                    elem_idx += 1

                elif isinstance(item, PptxTableItem):
                    elem = EvidenceBuilder.build_element(
                        element_idx=elem_idx,
                        document_id=document_id,
                        page=item.slide_number,
                        elem_type="table",
                        text=item.text,
                        table_data={"headers": item.headers, "rows": item.rows},
                        bbox=item.bbox,
                        confidence=1.0,
                        extraction_model="python-pptx",
                        file_hash=file_hash,
                        slide=item.slide_number,
                        reading_order=reading_order,
                        provenance=prov,
                        metadata={
                            "shape_name": item.shape_name,
                            "shape_id": item.shape_id,
                            "num_rows": item.num_rows,
                            "num_cols": item.num_cols,
                            "total_rows": item.num_rows,
                            "reading_order": reading_order,
                            "is_table": True,
                            "is_digital": True,
                            "source": "pptx_table",
                        },
                    )
                    elements.append(elem)
                    elem_idx += 1

                elif isinstance(item, PptxImageItem):
                    elem = EvidenceBuilder.build_element(
                        element_idx=elem_idx,
                        document_id=document_id,
                        page=item.slide_number,
                        elem_type="image",
                        text=None,
                        bbox=item.bbox,
                        confidence=1.0,
                        extraction_model="python-pptx",
                        file_hash=file_hash,
                        slide=item.slide_number,
                        reading_order=reading_order,
                        provenance=prov,
                        metadata={
                            "shape_name": item.shape_name,
                            "shape_id": item.shape_id,
                            "content_type": item.content_type,
                            "size_bytes": item.size_bytes,
                            "reading_order": reading_order,
                            "is_image": True,
                            "source": "pptx_image",
                            "image_bytes": getattr(item, "image_bytes", None),
                        },
                    )
                    elements.append(elem)
                    elem_idx += 1

        return elements

    @classmethod
    def _normalize_xlsx(
        cls,
        result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        elements: list[EvidenceElement] = []
        elem_idx = 1

        for ws in result.worksheets:
            # 1. Grid table element
            if ws.headers or ws.data_rows:
                elem = EvidenceBuilder.build_element(
                    element_idx=elem_idx,
                    document_id=document_id,
                    page=ws.sheet_index,
                    elem_type="table",
                    text=ws.text,
                    table_data={"headers": ws.headers, "rows": ws.data_rows},
                    bbox=[0.0, 0.0, 0.0, 0.0],
                    confidence=1.0,
                    extraction_model="openpyxl",
                    file_hash=file_hash,
                    sheet=ws.name,
                    reading_order=elem_idx,
                    provenance={
                        "source": "xlsx",
                        "sheet": ws.name,
                        "sheet_index": ws.sheet_index,
                    },
                    metadata={
                        "sheet": ws.name,
                        "num_rows": len(ws.rows),
                        "num_cols": ws.max_column,
                        "merged_ranges": ws.merged_cells,
                    },
                )
                elements.append(elem)
                elem_idx += 1

            # 2. Formula elements
            for fc in ws.formula_cells:
                elem = EvidenceBuilder.build_element(
                    element_idx=elem_idx,
                    document_id=document_id,
                    page=ws.sheet_index,
                    elem_type="formula",
                    text=fc.formula,
                    formula_latex=fc.formula,
                    bbox=[0.0, 0.0, 0.0, 0.0],
                    confidence=1.0,
                    extraction_model="openpyxl",
                    file_hash=file_hash,
                    sheet=ws.name,
                    row=fc.row,
                    column=fc.column,
                    reading_order=elem_idx,
                    provenance={
                        "source": "xlsx",
                        "sheet": ws.name,
                        "cell_coordinate": fc.coordinate,
                        "row": fc.row,
                        "column": fc.column,
                    },
                    metadata={
                        "sheet": ws.name,
                        "cell_coordinate": fc.coordinate,
                        "is_formula": True,
                    },
                )
                elements.append(elem)
                elem_idx += 1

        return elements

    @classmethod
    def _normalize_csv(
        cls,
        result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        if not result.all_rows:
            return []

        elem = EvidenceBuilder.build_element(
            element_idx=1,
            document_id=document_id,
            page=1,
            elem_type="table",
            text=result.text,
            table_data={"headers": result.headers, "rows": result.rows},
            bbox=[0.0, 0.0, 0.0, 0.0],
            confidence=1.0,
            extraction_model="csv",
            file_hash=file_hash,
            reading_order=1,
            provenance={
                "source": "csv",
                "source_document": result.source_document,
                "delimiter": result.delimiter,
                "total_rows": result.num_rows,
                "total_columns": result.num_cols,
            },
            metadata={
                "source_document": result.source_document,
                "delimiter": result.delimiter,
                "total_rows": result.num_rows,
                "total_columns": result.num_cols,
                "has_header": result.has_header,
            },
        )
        return [elem]

    @classmethod
    def _normalize_txt(
        cls,
        result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        elements: list[EvidenceElement] = []
        elem_idx = 1

        for block in result.blocks:
            lines = [line.strip() for line in block.text.splitlines() if line.strip()]
            elem_type = "text"
            if lines and all(l.startswith(("•", "-", "*", "–", "—")) or (len(l) > 2 and l[0].isdigit() and l[1] == ".") for l in lines):
                elem_type = "list"
            elif len(lines) == 1 and (lines[0].startswith("#") or lines[0].isupper() and len(lines[0]) < 80):
                elem_type = "heading"

            elem = EvidenceBuilder.build_element(
                element_idx=elem_idx,
                document_id=document_id,
                page=1,
                elem_type=elem_type,
                text=block.text,
                bbox=[0.0, 0.0, 0.0, 0.0],
                confidence=1.0,
                extraction_model="text",
                file_hash=file_hash,
                row=block.start_line,
                reading_order=elem_idx,
                provenance={
                    "source": "txt",
                    "start_line": block.start_line,
                    "end_line": block.end_line,
                    "encoding": result.metadata.get("encoding", "utf-8"),
                },
                metadata={
                    "start_line": block.start_line,
                    "end_line": block.end_line,
                    "line_count": block.line_count,
                    "encoding": result.metadata.get("encoding", "utf-8"),
                },
            )
            elements.append(elem)
            elem_idx += 1

        return elements

    @classmethod
    def _normalize_image(
        cls,
        result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        elements: list[EvidenceElement] = []

        for reg in result.extracted_regions:
            elem = EvidenceBuilder.build_element(
                element_idx=reg.region_index,
                document_id=document_id,
                page=1,
                elem_type=reg.type,
                text=reg.text,
                bbox=reg.bbox,
                confidence=reg.confidence,  # Preserves OCR confidence
                extraction_model=reg.extraction_model,
                file_hash=file_hash,
                reading_order=reg.region_index,
                provenance={
                    "source": "image_ocr",
                    "source_document": result.source_document,
                    "region_index": reg.region_index,
                    "model": reg.extraction_model,
                },
                metadata={
                    "source_document": result.source_document,
                    "image_width": result.image_width,
                    "image_height": result.image_height,
                    "image_format": result.image_format,
                    **reg.raw,
                },
            )
            elements.append(elem)

        return elements

    @classmethod
    def _normalize_pdf(
        cls,
        result: Any,
        document_id: str,
        file_hash: str,
    ) -> list[EvidenceElement]:
        elements: list[EvidenceElement] = []
        elem_idx = 1

        # If result contains structured pages, normalize page by page
        if getattr(result, "pages", None):
            for page_res in result.pages:
                method = page_res.extraction_method
                for elem in page_res.elements:
                    updated_dict: dict[str, Any] = {
                        "document_id": document_id,
                        "file_hash": file_hash,
                        "reading_order": elem.reading_order if elem.reading_order is not None else elem_idx,
                    }
                    if elem.provenance is None:
                        updated_dict["provenance"] = {
                            "source": "pdf",
                            "page": page_res.page_number,
                            "extraction_method": method,
                        }
                    norm_elem = elem.model_copy(update=updated_dict)
                    elements.append(norm_elem)
                    elem_idx += 1
            return elements

        # Otherwise normalize direct elements
        for elem in getattr(result, "elements", []):
            updated_dict = {
                "document_id": document_id,
                "file_hash": file_hash,
                "reading_order": elem.reading_order if elem.reading_order is not None else elem_idx,
            }
            if elem.provenance is None:
                updated_dict["provenance"] = {
                    "source": "pdf",
                    "page": elem.page,
                    "extraction_model": elem.extraction_model,
                }
            norm_elem = elem.model_copy(update=updated_dict)
            elements.append(norm_elem)
            elem_idx += 1

        return elements

    @classmethod
    def _normalize_fallback_element(
        cls,
        elem: EvidenceElement,
        idx: int,
        document_id: str,
        file_hash: str,
    ) -> EvidenceElement:
        updated: dict[str, Any] = {
            "document_id": document_id,
            "file_hash": file_hash,
        }
        if elem.reading_order is None:
            updated["reading_order"] = idx
        if elem.provenance is None:
            updated["provenance"] = {
                "source": "generic",
                "extraction_model": elem.extraction_model,
                "page": elem.page,
            }
        return elem.model_copy(update=updated)


normalizer = EvidenceNormalizer()
