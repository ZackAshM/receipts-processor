import csv
from pathlib import Path

from receipt_processor.io.exporter import export_expenses
from receipt_processor.io.sanitization import sanitize_spreadsheet_cell
from receipt_processor.io.template_loader import TemplateHints


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_export_expenses_csv(tmp_path: Path) -> None:
    out = tmp_path / "Expenses.csv"
    rows = [{"date": "2026-04-25", "vendor": "Store", "amount": "10.50"}]

    export_expenses(rows, out)

    loaded = _read_csv_rows(out)
    assert len(loaded) == 1
    assert loaded[0]["vendor"] == "Store"


def test_sanitize_spreadsheet_cell_blocks_formula_prefixes() -> None:
    assert sanitize_spreadsheet_cell("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert sanitize_spreadsheet_cell("+cmd") == "'+cmd"
    assert sanitize_spreadsheet_cell("-10+20") == "'-10+20"
    assert sanitize_spreadsheet_cell("@HYPERLINK(\"x\")") == "'@HYPERLINK(\"x\")"
    assert sanitize_spreadsheet_cell("safe text") == "safe text"
    assert sanitize_spreadsheet_cell(10.5) == 10.5


def test_export_expenses_sanitizes_dangerous_values_for_csv(tmp_path: Path) -> None:
    out = tmp_path / "Expenses.csv"
    rows = [{"vendor": "=2+2", "amount": "-12.50", "date": "2026-04-25"}]

    export_expenses(rows, out)

    loaded = _read_csv_rows(out)
    assert loaded[0]["vendor"] == "'=2+2"
    assert loaded[0]["amount"] == "'-12.50"


def test_export_expenses_appends_total_row_from_template_hints(tmp_path: Path) -> None:
    out = tmp_path / "Expenses.csv"
    rows = [
        {"Date": "2026 04 24", "Description": "Food - A", "Amt Claimed (USD)": "$10.00"},
        {"Date": "2026 04 25", "Description": "Food - B", "Amt Claimed (USD)": "$5.25"},
    ]
    hints = TemplateHints(
        date_output_format="%Y %m %d",
        currency_symbol="$",
        date_column="Date",
        description_column="Description",
        amount_column="Amt Claimed (USD)",
        receipt_amount_column="Receipt Amt",
    )

    export_expenses(rows, out, template_hints=hints)

    loaded = _read_csv_rows(out)
    assert len(loaded) == 4
    assert loaded[-1]["Description"] == "Total:"
    assert loaded[-1]["Amt Claimed (USD)"] == "$15.25"


def test_export_expenses_sanitizes_dangerous_values_for_xlsx(tmp_path: Path) -> None:
    out = tmp_path / "Expenses.xlsx"
    rows = [{"vendor": "@evil", "amount": "+1", "date": "2026-04-25"}]

    export_expenses(rows, out)

    try:
        from openpyxl import load_workbook
    except Exception:
        return

    workbook = load_workbook(out, data_only=True)
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    values = [cell.value for cell in sheet[2]]
    row = dict(zip(headers, values))
    assert row["vendor"] == "'@evil"
    assert row["amount"] == "'+1"
