"""Export expense rows to CSV or XLSX."""

from pathlib import Path

import pandas as pd

from receipt_processor.io.sanitization import sanitize_spreadsheet_cell


def export_expenses(rows: list[dict], output_file: Path) -> None:
    """Write rows to CSV or XLSX based on output suffix."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    for column in df.columns:
        df[column] = df[column].map(sanitize_spreadsheet_cell)
    suffix = output_file.suffix.lower()

    if suffix == ".csv":
        df.to_csv(output_file, index=False)
        return
    if suffix == ".xlsx":
        df.to_excel(output_file, index=False)
        return

    raise ValueError(f"Unsupported output format: {output_file}")
