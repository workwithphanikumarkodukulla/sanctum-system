"""Table structure extraction module."""
from __future__ import annotations

import re
from typing import Any


class TableExtractor:
    @staticmethod
    def parse_table_data(text: str | None, raw_data: Any = None) -> dict[str, Any] | None:
        """Parse structured table data into {"headers": [...], "rows": [[...]]}."""
        # 1. Check if raw_data already contains valid structured headers and rows
        if isinstance(raw_data, dict):
            if "headers" in raw_data and "rows" in raw_data and isinstance(raw_data["rows"], list) and raw_data["rows"]:
                return {
                    "headers": [str(h) for h in raw_data["headers"]],
                    "rows": [[str(c) for c in row] for row in raw_data["rows"]],
                }
            html_table = raw_data.get("res", {}).get("html") if isinstance(raw_data.get("res"), dict) else None
            if not html_table and isinstance(raw_data.get("html"), str):
                html_table = raw_data.get("html")
            if html_table:
                parsed_html = TableExtractor._parse_html_table(html_table)
                if parsed_html:
                    return parsed_html

        if not text:
            return None

        # 2. Check for markdown-style tables: | col1 | col2 |
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        pipe_lines = [line for line in lines if line.startswith("|") and line.endswith("|")]
        if len(pipe_lines) >= 2:
            return TableExtractor._parse_markdown_table(pipe_lines)

        # 3. Check for delimiter-separated lines (tabs or multi-spaces)
        delimited_rows: list[list[str]] = []
        for line in lines:
            if "\t" in line:
                cells = [c.strip() for c in line.split("\t") if c.strip()]
            else:
                cells = [c.strip() for c in re.split(r"\s{2,}", line) if c.strip()]
            if len(cells) > 1:
                delimited_rows.append(cells)

        if len(delimited_rows) >= 2:
            return {
                "headers": delimited_rows[0],
                "rows": delimited_rows[1:],
            }

        return None

    @staticmethod
    def _parse_markdown_table(lines: list[str]) -> dict[str, Any] | None:
        rows: list[list[str]] = []
        for line in lines:
            # Skip separator line like |---|---|
            if re.match(r"^\|[\s\-:|]+\|$", line):
                continue
            clean_line = line.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
            cells = [cell.strip() for cell in clean_line.strip("|").split("|")]
            rows.append(cells)

        if not rows:
            return None

        headers = rows[0]
        data_rows = rows[1:]
        return {
            "headers": headers,
            "rows": data_rows,
        }

    @staticmethod
    def _parse_html_table(html: str) -> dict[str, Any] | None:
        try:
            # Simple regex parser for <tr>, <th>, <td> to avoid heavy bs4 overhead
            row_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.IGNORECASE | re.DOTALL)
            parsed_rows: list[list[str]] = []
            for row_html in row_matches:
                cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.IGNORECASE | re.DOTALL)
                clean_cells = [re.sub(r"<[^>]+>", "", cell).strip() for cell in cells]
                if clean_cells:
                    parsed_rows.append(clean_cells)

            if parsed_rows:
                return {
                    "headers": parsed_rows[0],
                    "rows": parsed_rows[1:],
                }
        except Exception:
            pass
        return None


table_extractor = TableExtractor()
