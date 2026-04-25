"""Shared CLI/GUI option helpers."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class OutputType(str, Enum):
    """Supported export output file types."""

    csv = "csv"
    xlsx = "xlsx"


def resolve_output_file(
    input_dir: Path,
    output_file: Path | None,
    output_type: OutputType,
) -> Path:
    """Resolve the final output file path using type defaults."""
    if output_file is None:
        return input_dir / f"Expenses.{output_type.value}"

    if output_file.suffix:
        return output_file

    return output_file.with_suffix(f".{output_type.value}")

