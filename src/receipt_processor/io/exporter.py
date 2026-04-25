"""Export expense rows to CSV or XLSX."""

from __future__ import annotations

import csv
from pathlib import Path

from receipt_processor.io.sanitization import sanitize_spreadsheet_cell
from receipt_processor.io.template_loader import TemplateHints


def _parse_amount(value: object) -> float:
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    normalized = text.replace("$", "").replace(",", "").replace("'", "")
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _format_total(amount: float, currency_symbol: str) -> str:
    rendered = f"{amount:.2f}"
    return f"{currency_symbol}{rendered}" if currency_symbol else rendered


def _append_summary_rows(
    rows: list[dict[str, object]],
    template_hints: TemplateHints,
) -> list[dict[str, object]]:
    if not rows:
        return rows

    amount_col = template_hints.amount_column
    description_col = template_hints.description_column
    if not amount_col or not description_col:
        return rows

    total = 0.0
    counted_rows = 0
    for row in rows:
        status = str(row.get("_status", "")).strip().lower()
        if status == "requires_review":
            continue
        total += _parse_amount(row.get(amount_col))
        counted_rows += 1

    if counted_rows == 0:
        return rows

    columns = [column for column in rows[0].keys() if not column.startswith("_")]
    blank_row = {column: "" for column in columns}
    total_row = {column: "" for column in columns}
    total_row[description_col] = "Total:"
    total_row[amount_col] = _format_total(total, template_hints.currency_symbol)
    return rows + [blank_row, total_row]


def _prepare_rows(
    rows: list[dict[str, object]],
    template_hints: TemplateHints | None,
    model_columns: list[str] | None,
) -> tuple[list[str], list[dict[str, object]]]:
    if not rows:
        return model_columns or [], []

    columns = [column for column in rows[0].keys() if not column.startswith("_")]
    prepared_rows = [{column: row.get(column, "") for column in columns} for row in rows]

    if template_hints is not None:
        prepared_rows = _append_summary_rows(prepared_rows, template_hints)

    sanitized_rows: list[dict[str, object]] = []
    for row in prepared_rows:
        sanitized_rows.append(
            {column: sanitize_spreadsheet_cell(row.get(column, "")) for column in columns}
        )

    return columns, sanitized_rows


def _write_csv(columns: list[str], rows: list[dict[str, object]], output_file: Path) -> None:
    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_xlsx(columns: list[str], rows: list[dict[str, object]], output_file: Path) -> None:
    try:
        from openpyxl import Workbook
    except Exception as exc:
        raise ValueError("openpyxl is required for .xlsx exports") from exc

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column, "") for column in columns])
    workbook.save(output_file)


def export_expenses(
    rows: list[dict[str, object]],
    output_file: Path,
    template_hints: TemplateHints | None = None,
    model_columns: list[str] | None = None,
) -> None:
    """Write rows to CSV or XLSX based on output suffix."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    columns, prepared_rows = _prepare_rows(rows, template_hints, model_columns)
    suffix = output_file.suffix.lower()

    if suffix == ".csv":
        _write_csv(columns, prepared_rows, output_file)
        return
    if suffix == ".xlsx":
        _write_xlsx(columns, prepared_rows, output_file)
        return

    raise ValueError(f"Unsupported output format: {output_file}")
