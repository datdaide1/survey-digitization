"""Generic XLSX and DOCX reports for arbitrary flattened survey data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ProjectConfig


def _frequency_tables(frame):
    tables = []
    for column in frame.columns:
        if column == "record_id":
            continue
        counts = frame[column].fillna("(missing)").astype(str).value_counts(dropna=False)
        tables.append((column, counts))
    return tables


def build_reports(config: ProjectConfig):
    import pandas as pd
    from docx import Document
    from openpyxl import Workbook
    from openpyxl.styles import Font

    frame = pd.read_csv(config.paths.combined)
    config.paths.reports.mkdir(parents=True, exist_ok=True)
    stem = str(config.reporting.get("filename") or config.project_id)
    xlsx_path = config.paths.reports / f"{stem}.xlsx"
    docx_path = config.paths.reports / f"{stem}.docx"

    wb = Workbook()
    data = wb.active
    data.title = "Data"
    data.append(list(frame.columns))
    for cell in data[1]:
        cell.font = Font(bold=True)
    for row in frame.itertuples(index=False, name=None):
        data.append(list(row))
    freq = wb.create_sheet("Frequencies")
    freq.append(["field", "value", "count", "percent"])
    for column, counts in _frequency_tables(frame):
        denominator = int(counts.sum()) or 1
        for value, count in counts.items():
            freq.append([column, value, int(count), float(count) / denominator])
    wb.save(xlsx_path)

    document = Document()
    document.add_heading(config.title, 0)
    document.add_paragraph(f"Records: {len(frame)}")
    for column, counts in _frequency_tables(frame):
        document.add_heading(column, level=1)
        table = document.add_table(rows=1, cols=3)
        table.rows[0].cells[0].text = "Value"
        table.rows[0].cells[1].text = "Count"
        table.rows[0].cells[2].text = "Percent"
        denominator = int(counts.sum()) or 1
        for value, count in counts.items():
            cells = table.add_row().cells
            cells[0].text = str(value)
            cells[1].text = str(int(count))
            cells[2].text = f"{float(count) / denominator:.1%}"
    document.save(docx_path)
    return xlsx_path, docx_path
