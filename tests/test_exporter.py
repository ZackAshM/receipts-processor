from pathlib import Path

import pandas as pd

from receipt_processor.io.exporter import export_expenses
from receipt_processor.io.sanitization import sanitize_spreadsheet_cell


def test_export_expenses_csv(tmp_path: Path) -> None:
    out = tmp_path / "Expenses.csv"
    rows = [{"date": "2026-04-25", "vendor": "Store", "amount": "10.50"}]

    export_expenses(rows, out)

    loaded = pd.read_csv(out)
    assert loaded.shape[0] == 1
    assert loaded.loc[0, "vendor"] == "Store"


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

    loaded = pd.read_csv(out)
    assert loaded.loc[0, "vendor"] == "'=2+2"
    assert loaded.loc[0, "amount"] == "'-12.50"


def test_export_expenses_sanitizes_dangerous_values_for_xlsx(tmp_path: Path) -> None:
    out = tmp_path / "Expenses.xlsx"
    rows = [{"vendor": "@evil", "amount": "+1", "date": "2026-04-25"}]

    export_expenses(rows, out)

    loaded = pd.read_excel(out)
    assert loaded.loc[0, "vendor"] == "'@evil"
    assert loaded.loc[0, "amount"] == "'+1"
