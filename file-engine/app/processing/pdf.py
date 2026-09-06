"""PDF processing module: digital text extraction, scanned page detection, and high-res rendering."""
from __future__ import annotations

import io
import logging
from typing import Any
import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Provides page inspection, digital text extraction, and page image rendering."""

    @staticmethod
    def inspect_page(page: fitz.Page) -> dict[str, Any]:
        """Check if a PDF page contains digitally readable text or is scanned/image-only.

        A page is digital if it contains alphanumeric text and either:
        - has at least 20 characters of text, or
        - contains digital text blocks and no full-page raster images.
        """
        text = page.get_text("text").strip()
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        images = page.get_images()

        has_alphanumeric = any(c.isalnum() for c in text)
        is_digital = False

    @classmethod
    def reconstruct_page_tables(
        cls,
        page: fitz.Page,
        page_num: int = 1,
        prev_headers: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[tuple[float, float, float, float]], list[str] | None]:
        """Detect and reconstruct structured tables preserving multi-line cells, headers, and continued rows."""
        detected_tables: list[Any] = []
        try:
            tabs = page.find_tables()
            if tabs and getattr(tabs, "tables", None):
                detected_tables = list(tabs.tables)
            if not detected_tables:
                tabs_text = page.find_tables(strategy="text")
                if tabs_text and getattr(tabs_text, "tables", None):
                    detected_tables = list(tabs_text.tables)
        except Exception as exc:
            logger.debug("Table detection error on page %d: %s", page_num, exc)

        table_elements: list[dict[str, Any]] = []
        valid_table_bboxes: list[tuple[float, float, float, float]] = []
        page_headers: list[str] | None = None

        for tbl in detected_tables:
            try:
                raw_data = tbl.extract()
                if not raw_data or len(raw_data) < 2:
                    continue

                t_bbox = [float(tbl.bbox[0]), float(tbl.bbox[1]), float(tbl.bbox[2]), float(tbl.bbox[3])]
                valid_table_bboxes.append(tbl.bbox)

                # Clean cells and flatten inner newlines into single lines
                cleaned_rows: list[list[str]] = []
                for r in raw_data:
                    c_row = [c.replace("\n", " ").strip() if c else "" for c in r]
                    if any(c_row):
                        cleaned_rows.append(c_row)

                if len(cleaned_rows) < 2:
                    continue

                col_count = max(len(r) for r in cleaned_rows)
                for r in cleaned_rows:
                    while len(r) < col_count:
                        r.append("")

                header_indices: set[int] = set()
                detected_headers: list[str] | None = None
                banner_text = ""

                # 1. Check for single-cell banner title at top of table
                first_row_filled = [c for c in cleaned_rows[0] if c]
                if len(first_row_filled) == 1 and col_count >= 3:
                    header_indices.add(0)
                    banner_text = first_row_filled[0]
                    # On page 1, create a heading element for this document/table title
                    if page_num == 1:
                        banner_bbox = list(t_bbox)
                        if hasattr(tbl, "rows") and tbl.rows:
                            banner_bbox = [float(c) for c in tbl.rows[0].bbox]
                        table_elements.append({
                            "type": "heading",
                            "bbox": banner_bbox,
                            "text": banner_text,
                            "confidence": 0.98,
                            "extraction_model": "PyMuPDF-Direct",
                            "raw": {"is_heading": True, "level": 1, "page": page_num},
                        })

                # 2. Identify main column headers
                h_idx = 1 if 0 in header_indices and len(cleaned_rows) > 1 else 0
                if len(cleaned_rows) > h_idx:
                    cand_h = cleaned_rows[h_idx]
                    non_empty = [c for c in cand_h if c]
                    # Candidate header should have multiple labels and not start with numeric row ID
                    if len(non_empty) >= 2 and not (cand_h[0] and cand_h[0].isdigit()):
                        header_indices.add(h_idx)
                        # Check for compound sub-header row (e.g. State / District under Location)
                        sub_idx = h_idx + 1
                        if len(cleaned_rows) > sub_idx:
                            cand_sub = cleaned_rows[sub_idx]
                            sub_non_empty = [c for c in cand_sub if c]
                            if 0 < len(sub_non_empty) < col_count and not (cand_sub[0] and cand_sub[0].isdigit()):
                                header_indices.add(sub_idx)
                                merged: list[str] = []
                                for c_h, c_s in zip(cand_h, cand_sub):
                                    if c_h and c_s and c_h != c_s:
                                        merged.append(f"{c_h} - {c_s}")
                                    elif c_h:
                                        merged.append(c_h)
                                    elif c_s:
                                        merged.append(c_s)
                                    else:
                                        merged.append("")
                                detected_headers = merged
                            else:
                                detected_headers = list(cand_h)
                        else:
                            detected_headers = list(cand_h)

                # Fallback to previous page headers if table continues
                if not detected_headers:
                    if prev_headers and len(prev_headers) == col_count:
                        detected_headers = list(prev_headers)
                    else:
                        detected_headers = [f"Col {i+1}" for i in range(col_count)]

                page_headers = detected_headers

                # 3. Exclude repeated headers at top of page on continued table pages
                if page_num > 1:
                    for check_idx in range(min(4, len(cleaned_rows))):
                        row_vals = cleaned_rows[check_idx]
                        non_empty_r = [c for c in row_vals if c]
                        joined_r = " ".join(non_empty_r).lower()
                        # Matches banner or column header names or sub-headers
                        if (
                            (len(non_empty_r) == 1 and col_count >= 3)
                            or (row_vals == detected_headers)
                            or (any(kw in joined_r for kw in ["sl no", "sl.no", "serial", "name of", "item from", "schedule vii"]) and not (row_vals[0] and row_vals[0].isdigit()))
                            or (any(kw in joined_r for kw in ["state", "district"]) and not (row_vals[0] and row_vals[0].isdigit()) and len(non_empty_r) <= 3)
                        ):
                            header_indices.add(check_idx)

                # Filter data rows
                data_rows = [r for idx, r in enumerate(cleaned_rows) if idx not in header_indices]

                # Build clean markdown table representation without inner newlines
                pipe_lines = [
                    "| " + " | ".join(detected_headers) + " |",
                    "| " + " | ".join("---" for _ in range(col_count)) + " |",
                ]
                for d_row in data_rows:
                    pipe_lines.append("| " + " | ".join(d_row) + " |")
                table_text = "\n".join(pipe_lines)

                # Diagnostic output
                logger.info(
                    "PAGE %d\n  detected table: true\n  rows reconstructed: %d\n  columns detected: %d",
                    page_num,
                    len(data_rows),
                    col_count,
                )

                table_meta = {
                    "headers": detected_headers,
                    "rows": data_rows,
                    "table_bbox": t_bbox,
                    "num_rows": len(data_rows),
                    "num_cols": col_count,
                    "is_continued": page_num > 1,
                    "page": page_num,
                    "banner_text": banner_text,
                }

                table_elements.append({
                    "type": "table",
                    "bbox": t_bbox,
                    "text": table_text,
                    "confidence": 0.98,
                    "extraction_model": "PyMuPDF-Tables",
                    "table_data": {"headers": detected_headers, "rows": data_rows},
                    "raw": table_meta,
                })

            except Exception as tbl_err:
                logger.debug("Could not extract table on page %d: %s", page_num, tbl_err)

        return table_elements, valid_table_bboxes, page_headers

    @classmethod
    def inspect_page(
        cls,
        page: fitz.Page,
        page_num: int = 1,
        prev_headers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Check if a PDF page contains digitally readable text or is scanned/image-only,
        and reconstruct structured tables and text blocks.
        """
        text = page.get_text("text").strip()
        blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        images = page.get_images()

        has_alphanumeric = any(c.isalnum() for c in text)
        is_digital = False

        if has_alphanumeric:
            if len(text) >= 20 or len(images) == 0:
                is_digital = True

        elements_direct: list[dict[str, Any]] = []
        detected_headers: list[str] | None = None

        if is_digital:
            # 1. Detect and reconstruct structured tables
            table_elements, valid_table_bboxes, detected_headers = cls.reconstruct_page_tables(
                page=page,
                page_num=page_num,
                prev_headers=prev_headers,
            )

            # 2. Extract remaining non-table blocks
            text_elements: list[dict[str, Any]] = []
            for b in blocks:
                b_text = b[4].strip()
                if not b_text:
                    continue
                bx0, by0, bx1, by1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])

                # Check if this text block is inside an extracted table
                inside_table = False
                for tb in valid_table_bboxes:
                    if bx0 >= tb[0] - 5 and by0 >= tb[1] - 5 and bx1 <= tb[2] + 5 and by1 <= tb[3] + 5:
                        inside_table = True
                        break
                if inside_table:
                    continue

                bbox = [bx0, by0, bx1, by1]
                elem_type = "text"
                if "|" in b_text or "\t" in b_text:
                    elem_type = "table"
                elif any(sym in b_text for sym in ["\\sum", "\\int", "∑", "∫", "±", "√", "E = m", "t_min ="]):
                    elem_type = "formula"

                text_elements.append({
                    "type": elem_type,
                    "bbox": bbox,
                    "text": b_text,
                    "confidence": 0.98,
                    "extraction_model": "PyMuPDF-Direct",
                    "raw": {"block_no": b[5], "block_type": b[6], "page": page_num},
                })

            # 3. Combine and sort in visual reading order (top-to-bottom, left-to-right)
            all_direct = table_elements + text_elements
            elements_direct = sorted(all_direct, key=lambda e: (round(e["bbox"][1], 1), round(e["bbox"][0], 1)))

        return {
            "is_digital": is_digital,
            "raw_text": text,
            "elements": elements_direct,
            "image_count": len(images),
            "detected_headers": detected_headers,
        }

    @staticmethod
    def render_page_to_image(page: fitz.Page, dpi: int = 200) -> Image.Image:
        """Render a PDF page to a high-resolution PIL Image for OCR and vision processing."""
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        return Image.open(io.BytesIO(img_bytes)).convert("RGB")

    @staticmethod
    def load_pdf(pdf_bytes: bytes) -> fitz.Document:
        """Load PDF bytes safely with input validation."""
        if not pdf_bytes:
            raise ValueError("Uploaded PDF file is empty (0 bytes).")
        try:
            return fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(f"Invalid or corrupted PDF file: {exc}")


pdf_processor = PDFProcessor()
