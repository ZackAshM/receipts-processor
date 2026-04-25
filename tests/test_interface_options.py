from __future__ import annotations

from pathlib import Path

from receipt_processor.interface_options import OutputType, resolve_output_file


def test_resolve_output_file_defaults_to_input_folder() -> None:
    path = resolve_output_file(Path("/tmp/receipts"), None, OutputType.csv)
    assert path == Path("/tmp/receipts/Expenses.csv")


def test_resolve_output_file_respects_output_type() -> None:
    path = resolve_output_file(Path("/tmp/receipts"), None, OutputType.xlsx)
    assert path == Path("/tmp/receipts/Expenses.xlsx")


def test_resolve_output_file_appends_extension_when_missing() -> None:
    path = resolve_output_file(Path("/tmp/receipts"), Path("/tmp/out/report"), OutputType.xlsx)
    assert path == Path("/tmp/out/report.xlsx")


def test_resolve_output_file_keeps_existing_extension() -> None:
    path = resolve_output_file(
        Path("/tmp/receipts"),
        Path("/tmp/out/custom.csv"),
        OutputType.xlsx,
    )
    assert path == Path("/tmp/out/custom.csv")
