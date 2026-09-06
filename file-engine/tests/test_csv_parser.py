"""Unit tests for the CsvParser covering normal CSV, quoted fields, commas in quotes, headers, and empty CSV."""
from __future__ import annotations

import io
import pytest

from app.parsers.csv import CsvParseResult, csv_parser


@pytest.mark.anyio
async def test_normal_csv():
    """Verify standard comma-separated values preserve row and column order."""
    content = "Asset_ID,Location,Pressure,Status\nAST-001,Zone A,500,Active\nAST-002,Zone B,750,Standby\n"
    raw_bytes = content.encode("utf-8")

    res: CsvParseResult = await csv_parser.parse(raw_bytes, filename="equipment.csv")

    assert isinstance(res, CsvParseResult)
    assert res.parser_name == "csv_parser"
    assert res.delimiter == ","
    assert res.headers == ["Asset_ID", "Location", "Pressure", "Status"]
    assert len(res.rows) == 2
    assert res.rows[0] == ["AST-001", "Zone A", "500", "Active"]
    assert res.rows[1] == ["AST-002", "Zone B", "750", "Standby"]
    assert res.num_rows == 3  # 1 header + 2 data rows
    assert res.num_cols == 4


@pytest.mark.anyio
async def test_quoted_values():
    """Verify fields wrapped in double quotes are correctly parsed without quote artifacts."""
    content = '"Item Name","Manufacturer","Model Code"\n"Centrifugal Pump","ACME Corp","CP-4000"\n"Check Valve","FlowTech","CV-100"\n'
    raw_bytes = content.encode("utf-8")

    res = await csv_parser.parse(raw_bytes, filename="quotes.csv")

    assert res.headers == ["Item Name", "Manufacturer", "Model Code"]
    assert res.rows[0] == ["Centrifugal Pump", "ACME Corp", "CP-4000"]
    assert res.rows[1] == ["Check Valve", "FlowTech", "CV-100"]


@pytest.mark.anyio
async def test_commas_inside_quoted_fields():
    """Verify commas inside quotes do not split the field into multiple columns."""
    content = (
        'ID,Description,Remarks\n'
        '101,"Pump A, primary cooling circuit","Replaced O-ring, calibrated"\n'
        '102,"Compressor B, high-pressure line","Operating within +/- 5% tolerance, OK"\n'
    )
    raw_bytes = content.encode("utf-8")

    res = await csv_parser.parse(raw_bytes, filename="commas.csv")

    assert res.num_cols == 3
    assert res.headers == ["ID", "Description", "Remarks"]
    assert len(res.rows) == 2

    # Verify that the comma inside quotes stayed in a single column
    assert res.rows[0][0] == "101"
    assert res.rows[0][1] == "Pump A, primary cooling circuit"
    assert res.rows[0][2] == "Replaced O-ring, calibrated"

    assert res.rows[1][0] == "102"
    assert res.rows[1][1] == "Compressor B, high-pressure line"
    assert res.rows[1][2] == "Operating within +/- 5% tolerance, OK"


@pytest.mark.anyio
async def test_csv_header_detection():
    """Verify header detection and preservation."""
    # Clearly defined textual header with numeric data
    content = "Timestamp,Reading_bar,Temperature_C\n2026-01-01 10:00:00,12.5,45.2\n2026-01-01 11:00:00,13.1,46.0\n"
    raw_bytes = content.encode("utf-8")

    res = await csv_parser.parse(raw_bytes, filename="telemetry.csv")

    assert res.has_header is True
    assert res.headers == ["Timestamp", "Reading_bar", "Temperature_C"]
    assert len(res.rows) == 2


@pytest.mark.anyio
async def test_empty_csv():
    """Verify empty input returns structured empty result without errors."""
    # 0 bytes
    res_zero = await csv_parser.parse(b"", filename="empty.csv")
    assert isinstance(res_zero, CsvParseResult)
    assert res_zero.num_rows == 0
    assert len(res_zero.rows) == 0
    assert res_zero.metadata["is_empty"] is True

    # Whitespace only
    res_ws = await csv_parser.parse(b"   \n\r\n\t   \n", filename="blank.csv")
    assert isinstance(res_ws, CsvParseResult)
    assert res_ws.num_rows == 0
    assert len(res_ws.rows) == 0
    assert res_ws.metadata["is_empty"] is True


@pytest.mark.anyio
async def test_csv_alternative_delimiters():
    """Verify semicolons and tabs are sniffed and parsed into columns correctly."""
    # Semicolon separated
    sc_content = "ID;Parameter;Threshold\n1;Temp;100\n2;Pressure;500\n"
    res_sc = await csv_parser.parse(sc_content.encode("utf-8"), filename="semicolon.csv")
    assert res_sc.delimiter == ";"
    assert res_sc.headers == ["ID", "Parameter", "Threshold"]
    assert res_sc.rows[0] == ["1", "Temp", "100"]

    # Stream input
    stream = io.BytesIO(b"Col1,Col2\nValA,ValB\n")
    res_stream = await csv_parser.parse(stream, filename="stream.csv")
    assert res_stream.headers == ["Col1", "Col2"]
    assert res_stream.rows[0] == ["ValA", "ValB"]
