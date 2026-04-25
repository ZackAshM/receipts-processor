"""Load model template schema from CSV or XLSX."""

from pathlib import Path

import pandas as pd


def load_model_columns(model_file: Path) -> list[str]:
    """Load column names from model template."""
    suffix = model_file.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(model_file, nrows=0)
        return list(df.columns)
    if suffix == ".xlsx":
        df = pd.read_excel(model_file, nrows=0)
        return list(df.columns)
    raise ValueError(f"Unsupported model format: {model_file}")
