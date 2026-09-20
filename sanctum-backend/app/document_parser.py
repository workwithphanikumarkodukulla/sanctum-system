"""Document parsing engine for Sanctum Sovereign Platform.
Extracts structured visual and semantic data from PDF, Word (.docx), PowerPoint (.pptx),
Excel (.xlsx / .csv), and image files.
"""

import base64
import csv
import io
import os
from pathlib import Path
from typing import Union, Dict, Any, List

from app.logger import logger

def get_file_bytes(source: Union[str, Path, bytes, io.BytesIO]) -> bytes:
    if isinstance(source, (str, Path)):
        with open(source, "rb") as f:
            return f.read()
    elif isinstance(source, io.BytesIO):
        return source.getvalue()
    elif isinstance(source, bytes):
        return source
    else:
        raise ValueError("Unsupported source type for document parser.")


def parse_pdf(source: Union[str, Path, bytes, io.BytesIO], filename: str) -> Dict[str, Any]:
    try:
        import fitz
    except ImportError:
        try:
            import pymupdf as fitz
        except ImportError:
            return {"type": "pdf", "filename": filename, "error": "PyMuPDF is not installed."}

    raw_bytes = get_file_bytes(source)
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    total_pages = len(doc)
    pages = []
    
    first_page_b64 = ""
    for idx, page in enumerate(doc):
        txt = page.get_text()
        rect = page.rect
        pages.append({
            "page": idx + 1,
            "text": txt.strip(),
            "width": rect.width,
            "height": rect.height,
        })
        if idx == 0:
            try:
                pix = page.get_pixmap(dpi=110)
                png_data = pix.tobytes("png")
                first_page_b64 = f"data:image/png;base64,{base64.b64encode(png_data).decode('utf-8')}"
            except Exception as e:
                logger.warning(f"Failed to generate first page pixmap for {filename}: {e}")

    return {
        "type": "pdf",
        "filename": filename,
        "total_pages": total_pages,
        "pages": pages,
        "first_page_preview": first_page_b64,
    }


def render_pdf_page_image(source: Union[str, Path, bytes, io.BytesIO], page_num: int = 1, dpi: int = 130) -> bytes:
    try:
        import fitz
    except ImportError:
        import pymupdf as fitz

    raw_bytes = get_file_bytes(source)
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    if page_num < 1 or page_num > len(doc):
        raise ValueError(f"Page number {page_num} is out of bounds (1..{len(doc)}).")
    page = doc[page_num - 1]
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")


def parse_docx(source: Union[str, Path, bytes, io.BytesIO], filename: str) -> Dict[str, Any]:
    try:
        import docx
    except ImportError:
        return {"type": "docx", "filename": filename, "error": "python-docx is not installed."}

    raw_bytes = get_file_bytes(source)
    stream = io.BytesIO(raw_bytes)
    doc = docx.Document(stream)

    title = ""
    sections: List[Dict[str, Any]] = []
    total_words = 0
    markdown_parts: List[str] = []

    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        total_words += len(txt.split())
        style_name = (p.style.name or "").lower()

        sec_type = "paragraph"
        if "title" in style_name:
            sec_type = "title"
            if not title:
                title = txt
            markdown_parts.append(f"# {txt}\n")
        elif "heading 1" in style_name:
            sec_type = "heading_1"
            markdown_parts.append(f"\n## {txt}\n")
        elif "heading 2" in style_name:
            sec_type = "heading_2"
            markdown_parts.append(f"\n### {txt}\n")
        elif "heading 3" in style_name:
            sec_type = "heading_3"
            markdown_parts.append(f"\n#### {txt}\n")
        elif "list" in style_name or "bullet" in style_name:
            sec_type = "list_item"
            markdown_parts.append(f"- {txt}")
        else:
            sec_type = "paragraph"
            markdown_parts.append(f"{txt}\n")

        # Capture run styles (bold, italic)
        runs_data = []
        for r in p.runs:
            if r.text:
                runs_data.append({
                    "text": r.text,
                    "bold": bool(r.bold),
                    "italic": bool(r.italic),
                    "underline": bool(r.underline),
                })

        sections.append({
            "type": sec_type,
            "style": p.style.name,
            "text": txt,
            "runs": runs_data,
        })

    # Tables
    for t in doc.tables:
        rows_data = []
        for r_idx, row in enumerate(t.rows):
            cell_texts = [cell.text.strip() for cell in row.cells]
            rows_data.append(cell_texts)
        if rows_data:
            sections.append({
                "type": "table",
                "rows": rows_data,
            })
            # Add table to markdown
            if len(rows_data) > 0:
                header = rows_data[0]
                markdown_parts.append("\n| " + " | ".join(header) + " |")
                markdown_parts.append("| " + " | ".join(["---"] * len(header)) + " |")
                for r in rows_data[1:]:
                    markdown_parts.append("| " + " | ".join(r) + " |")
                markdown_parts.append("\n")

    if not title:
        # Check first heading or first section
        for s in sections:
            if s["type"] in ("title", "heading_1"):
                title = s["text"]
                break
        if not title and sections:
            title = sections[0]["text"][:60]
        if not title:
            title = Path(filename).stem

    return {
        "type": "docx",
        "filename": filename,
        "title": title,
        "stats": {
            "words": total_words,
            "paragraphs": len(doc.paragraphs),
            "tables": len(doc.tables),
        },
        "sections": sections,
        "markdown": "\n".join(markdown_parts),
    }


def parse_pptx(source: Union[str, Path, bytes, io.BytesIO], filename: str) -> Dict[str, Any]:
    try:
        import pptx
        from pptx.enum.shapes import MSO_SHAPE_TYPE
    except ImportError:
        return {"type": "pptx", "filename": filename, "error": "python-pptx is not installed."}

    raw_bytes = get_file_bytes(source)
    stream = io.BytesIO(raw_bytes)
    prs = pptx.Presentation(stream)

    slides = []
    deck_title = ""

    for idx, slide in enumerate(prs.slides):
        slide_num = idx + 1
        slide_title = ""
        bullets: List[str] = []
        tables: List[List[List[str]]] = []
        images: List[str] = []

        # Find title shape if present
        try:
            if slide.shapes.title and slide.shapes.title.text.strip():
                slide_title = slide.shapes.title.text.strip()
        except Exception:
            pass

        for shape in slide.shapes:
            # Check for text
            if shape.has_text_frame:
                for p in shape.text_frame.paragraphs:
                    txt = p.text.strip()
                    if not txt:
                        continue
                    if not slide_title and (shape.name.lower().startswith("title") or len(txt) < 80):
                        slide_title = txt
                    elif txt != slide_title:
                        bullets.append(txt)

            # Check for tables
            if shape.has_table:
                table_rows = []
                for row in shape.table.rows:
                    table_rows.append([cell.text.strip() for cell in row.cells])
                tables.append(table_rows)

            # Check for pictures
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    img_blob = shape.image.blob
                    ext = shape.image.ext.lower()
                    mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
                    b64 = base64.b64encode(img_blob).decode("utf-8")
                    images.append(f"data:{mime};base64,{b64}")
                except Exception as e:
                    logger.debug(f"Could not extract slide picture: {e}")

        # Speaker notes
        notes = ""
        try:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            pass

        if not slide_title:
            slide_title = f"Slide {slide_num}"

        if not deck_title and idx == 0:
            deck_title = slide_title

        slides.append({
            "slide_number": slide_num,
            "title": slide_title,
            "bullets": bullets,
            "tables": tables,
            "images": images,
            "notes": notes,
        })

    return {
        "type": "pptx",
        "filename": filename,
        "title": deck_title or Path(filename).stem,
        "total_slides": len(slides),
        "slides": slides,
    }


def parse_spreadsheet(source: Union[str, Path, bytes, io.BytesIO], filename: str) -> Dict[str, Any]:
    raw_bytes = get_file_bytes(source)
    suffix = Path(filename).suffix.lower()

    if suffix == ".csv":
        try:
            text = raw_bytes.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            headers = rows[0] if rows else []
            data_rows = rows[1:] if len(rows) > 1 else []
            return {
                "type": "spreadsheet",
                "filename": filename,
                "sheet_names": ["Sheet1"],
                "sheets": {
                    "Sheet1": {
                        "headers": headers,
                        "rows": data_rows[:1000],  # cap at 1000 rows for smooth UI
                    }
                },
                "total_rows": len(rows),
            }
        except Exception as e:
            return {"type": "spreadsheet", "filename": filename, "error": str(e)}

    # For .xlsx / .xls
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
        sheets_data = {}
        total_rows = 0
        for sname in wb.sheetnames:
            ws = wb[sname]
            all_rows = []
            for r in ws.iter_rows(values_only=True):
                # Format None to empty string
                row_vals = ["" if v is None else str(v) for v in r]
                # Filter completely empty trailing rows
                if any(row_vals):
                    all_rows.append(row_vals)
            headers = all_rows[0] if all_rows else []
            data_rows = all_rows[1:1001] if len(all_rows) > 1 else []
            total_rows += len(all_rows)
            sheets_data[sname] = {
                "headers": headers,
                "rows": data_rows,
                "row_count": len(all_rows),
            }
        return {
            "type": "spreadsheet",
            "filename": filename,
            "sheet_names": wb.sheetnames,
            "sheets": sheets_data,
            "total_rows": total_rows,
        }
    except Exception as e:
        logger.exception(f"Error parsing spreadsheet {filename}: {e}")
        return {"type": "spreadsheet", "filename": filename, "error": str(e)}


def parse_document(source: Union[str, Path, bytes, io.BytesIO], filename: str) -> Dict[str, Any]:
    """Universal document parsing entry point."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(source, filename)
    elif suffix in (".docx", ".doc"):
        return parse_docx(source, filename)
    elif suffix in (".pptx", ".ppt"):
        return parse_pptx(source, filename)
    elif suffix in (".xlsx", ".xls", ".csv"):
        return parse_spreadsheet(source, filename)
    elif suffix in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".bmp"):
        return {
            "type": "image",
            "filename": filename,
            "suffix": suffix,
        }
    else:
        # Default text/code fallback
        try:
            raw = get_file_bytes(source)
            text = raw.decode("utf-8", errors="replace")
            return {
                "type": "text",
                "filename": filename,
                "content": text,
            }
        except Exception as e:
            return {"type": "unknown", "filename": filename, "error": str(e)}
