from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from receipt_processor.cli import app

runner = CliRunner()


def _make_templates(tmp_path: Path) -> tuple[Path, Path, Path]:
    input_dir = tmp_path / "receipts"
    input_dir.mkdir()

    model_file = tmp_path / "model.csv"
    model_file.write_text("Date,Description,Amt Claimed (USD)\n", encoding="utf-8")

    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Date,Description,Amt Claimed (USD)\n2025 06 25,Transportation - Lyft,$54.91\n",
        encoding="utf-8",
    )
    return input_dir, model_file, example_file


def test_cli_direct_positional_run(monkeypatch, tmp_path: Path) -> None:
    input_dir, model_file, example_file = _make_templates(tmp_path)
    output_file = tmp_path / "Expenses.csv"

    calls = {}

    def fake_run_pipeline(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("receipt_processor.cli.run_pipeline", fake_run_pipeline)

    result = runner.invoke(
        app,
        [
            str(input_dir),
            "--model-file",
            str(model_file),
            "--example-file",
            str(example_file),
            "--output-file",
            str(output_file),
            "--log-dir",
            str(tmp_path / "logs"),
        ],
    )

    assert result.exit_code == 0
    assert calls["input_dir"] == input_dir
    assert calls["model_file"] == model_file
    assert calls["example_file"] == example_file
    assert calls["output_file"] == output_file


def test_cli_defaults_output_file_to_input_dir(monkeypatch, tmp_path: Path) -> None:
    input_dir, model_file, example_file = _make_templates(tmp_path)
    calls = {}

    def fake_run_pipeline(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("receipt_processor.cli.run_pipeline", fake_run_pipeline)

    result = runner.invoke(
        app,
        [
            str(input_dir),
            "--model-file",
            str(model_file),
            "--example-file",
            str(example_file),
        ],
    )

    assert result.exit_code == 0
    assert calls["output_file"] == input_dir / "Expenses.csv"


def test_cli_defaults_output_file_type_to_xlsx(monkeypatch, tmp_path: Path) -> None:
    input_dir, model_file, example_file = _make_templates(tmp_path)
    calls = {}

    def fake_run_pipeline(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("receipt_processor.cli.run_pipeline", fake_run_pipeline)

    result = runner.invoke(
        app,
        [
            str(input_dir),
            "--model-file",
            str(model_file),
            "--example-file",
            str(example_file),
            "--output-type",
            "xlsx",
        ],
    )

    assert result.exit_code == 0
    assert calls["output_file"] == input_dir / "Expenses.xlsx"


def test_cli_output_file_without_extension_uses_output_type(monkeypatch, tmp_path: Path) -> None:
    input_dir, model_file, example_file = _make_templates(tmp_path)
    calls = {}

    def fake_run_pipeline(**kwargs):
        calls.update(kwargs)

    monkeypatch.setattr("receipt_processor.cli.run_pipeline", fake_run_pipeline)

    result = runner.invoke(
        app,
        [
            str(input_dir),
            "--model-file",
            str(model_file),
            "--example-file",
            str(example_file),
            "--output-file",
            str(tmp_path / "report"),
            "--output-type",
            "xlsx",
        ],
    )

    assert result.exit_code == 0
    assert calls["output_file"] == tmp_path / "report.xlsx"
