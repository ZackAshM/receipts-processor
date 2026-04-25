from pathlib import Path

import pandas as pd

from receipt_processor.io.exporter import export_expenses


def test_export_expenses_csv(tmp_path: Path) -> None:
    out = tmp_path / "Expenses.csv"
    rows = [{"date": "2026-04-25", "vendor": "Store", "amount": "10.50"}]

    export_expenses(rows, out)

    loaded = pd.read_csv(out)
    assert loaded.shape[0] == 1
    assert loaded.loc[0, "vendor"] == "Store"
