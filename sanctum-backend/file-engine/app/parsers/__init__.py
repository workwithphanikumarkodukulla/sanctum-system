"""Parsers package exporting native and visual document parsers."""
from app.parsers.base import BaseParser, ParseResult
from app.parsers.csv import csv_parser
from app.parsers.docx import docx_parser
from app.parsers.image import image_parser
from app.parsers.pdf import pdf_parser
from app.parsers.pptx import pptx_parser
from app.parsers.txt import txt_parser
from app.parsers.xlsx import xlsx_parser

__all__ = [
    "BaseParser",
    "ParseResult",
    "pdf_parser",
    "image_parser",
    "docx_parser",
    "pptx_parser",
    "xlsx_parser",
    "csv_parser",
    "txt_parser",
]
