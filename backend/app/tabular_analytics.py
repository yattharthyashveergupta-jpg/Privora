"""Privora — Deterministic Tabular & Spreadsheet Analytics Engine
Performs reproducible, traceable mathematical aggregations (Totals, Averages, Min, Max)
directly from raw XLSX and CSV files with cell-coordinate references.
Zero language-model arithmetic hallucinations.
"""
from __future__ import annotations

import csv
from pathlib import Path
import re
from typing import Any


def clean_numeric_value(val: Any) -> float | None:
    """Safely extracts a float from raw tabular cell contents, handling currency and formatting."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return None

    # Handle negative notation: (1,250.00) -> -1250.00
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Strip currency symbols and commas
    cleaned = re.sub(r"[$,€£¥\s%]", "", s)
    try:
        num = float(cleaned)
        return -num if is_negative else num
    except (ValueError, TypeError):
        return None


def analyze_tabular_file(path: Path, suffix: str) -> dict[str, Any]:
    """Inspects an XLSX or CSV file and computes deterministic column-level statistics."""
    clean_suffix = suffix.lower()
    sheets_out: list[dict[str, Any]] = []

    if clean_suffix == ".xlsx":
        import openpyxl
        from openpyxl.utils import get_column_letter

        try:
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows_data: list[list[Any]] = []
                for row in ws.iter_rows(values_only=True):
                    filtered = [str(c).strip() if c is not None else "" for c in row]
                    if any(filtered):
                        rows_data.append(list(row))

                if not rows_data:
                    continue

                headers = [str(h).strip() if h is not None and str(h).strip() else f"Col_{i+1}" for i, h in enumerate(rows_data[0])]
                data_rows = rows_data[1:] if len(rows_data) > 1 else []
                num_cols = len(headers)

                sheet_info = _compute_columns_stats(
                    sheet_name=sheet_name,
                    headers=headers,
                    data_rows=data_rows,
                    start_row=2 if len(rows_data) > 1 else 1,
                    get_col_ref=lambda idx: get_column_letter(idx + 1),
                )
                sheets_out.append(sheet_info)
            wb.close()
        except Exception as exc:
            raise ValueError(f"Error analyzing Excel workbook: {exc}")

    elif clean_suffix == ".csv":
        content = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                content = path.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue

        if not content:
            raise ValueError("Could not decode CSV content")

        sample = content[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ","

        reader = csv.reader(content.splitlines(), delimiter=delimiter)
        raw_rows = [row for row in reader if any(c.strip() for c in row)]
        if raw_rows:
            headers = [h.strip() if h.strip() else f"Col_{i+1}" for i, h in enumerate(raw_rows[0])]
            data_rows = raw_rows[1:] if len(raw_rows) > 1 else []
            sheet_info = _compute_columns_stats(
                sheet_name="Main",
                headers=headers,
                data_rows=data_rows,
                start_row=2 if len(raw_rows) > 1 else 1,
                get_col_ref=lambda idx: f"Col {idx+1}",
            )
            sheets_out.append(sheet_info)

    return {
        "filename": path.name,
        "format": clean_suffix.lstrip("."),
        "total_sheets": len(sheets_out),
        "sheets": sheets_out,
    }


def _compute_columns_stats(
    sheet_name: str,
    headers: list[str],
    data_rows: list[list[Any]],
    start_row: int,
    get_col_ref: Any,
) -> dict[str, Any]:
    """Helper to calculate mathematical summaries per column."""
    num_cols = len(headers)
    end_row = start_row + len(data_rows) - 1

    numeric_columns: list[dict[str, Any]] = []
    text_columns: list[dict[str, Any]] = []

    for c_idx in range(num_cols):
        col_name = headers[c_idx]
        col_ref = get_col_ref(c_idx)
        raw_vals = [row[c_idx] if c_idx < len(row) else None for row in data_rows]

        # Check numeric density
        numbers: list[float] = []
        for val in raw_vals:
            parsed = clean_numeric_value(val)
            if parsed is not None:
                numbers.append(parsed)

        # If more than 50% of populated values are numeric, treat as numeric column
        populated_count = sum(1 for v in raw_vals if v is not None and str(v).strip() != "")
        if populated_count > 0 and len(numbers) >= (populated_count * 0.5):
            tot = sum(numbers)
            mean_val = tot / len(numbers) if numbers else 0.0
            min_val = min(numbers) if numbers else 0.0
            max_val = max(numbers) if numbers else 0.0
            if str(col_ref).startswith("Col"):
                range_str = f"{col_ref} (Rows {start_row}-{end_row})"
            else:
                range_str = f"{col_ref}{start_row}:{col_ref}{end_row}"

            numeric_columns.append({
                "column": col_name,
                "column_ref": col_ref,
                "cell_range": range_str,
                "count": len(numbers),
                "total": round(tot, 2),
                "mean": round(mean_val, 2),
                "min": round(min_val, 2),
                "max": round(max_val, 2),
            })
        else:
            distinct = list(dict.fromkeys(str(v).strip() for v in raw_vals if v is not None and str(v).strip() != ""))
            text_columns.append({
                "column": col_name,
                "column_ref": col_ref,
                "count": populated_count,
                "distinct_count": len(distinct),
                "sample_values": distinct[:4],
            })

    return {
        "sheet_name": sheet_name,
        "total_rows": len(data_rows),
        "total_columns": num_cols,
        "headers": headers,
        "numeric_columns": numeric_columns,
        "text_columns": text_columns,
    }


def generate_tabular_summary_passage(sheet_info: dict[str, Any], filename: str) -> tuple[int | None, str, str] | None:
    """Generates an indexed reference passage containing deterministic column aggregations."""
    sheet_name = sheet_info["sheet_name"]
    numeric_cols = sheet_info.get("numeric_columns", [])
    if not numeric_cols:
        return None

    lines = [
        f"[Spreadsheet Intelligence Summary — {filename} ({sheet_name})]",
        f"Analyzed {sheet_info['total_rows']} records across {sheet_info['total_columns']} columns.",
        "Verified Deterministic Column Calculations:",
    ]
    for c in numeric_cols:
        lines.append(
            f"• Column '{c['column']}' ({c['cell_range']}): "
            f"Total = {c['total']:,} | Average = {c['mean']:,} | Min = {c['min']:,} | Max = {c['max']:,} "
            f"(Evaluated from {c['count']} numerical entries)"
        )

    text_summary = "\n".join(lines)
    section_title = f"Sheet: {sheet_name} | Deterministic Summary"
    return (None, text_summary, section_title)
