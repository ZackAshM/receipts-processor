from __future__ import annotations

import os
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


def test_cli_llm_runtime_overrides_are_passed_to_pipeline(monkeypatch, tmp_path: Path) -> None:
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
            "--enable-llm",
            "--llm-model",
            "anthropic/claude-3.5-sonnet",
            "--llm-input-mode",
            "file",
            "--enable-llm-exception-assist",
        ],
    )

    assert result.exit_code == 0
    assert calls["enable_llm"] is True
    assert calls["llm_model"] == "anthropic/claude-3.5-sonnet"
    assert calls["llm_input_mode"] == "file"
    assert calls["llm_exception_assist"] is True


def test_cli_auto_loads_dotenv_from_cwd(monkeypatch) -> None:
    calls = {}
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    def fake_run_pipeline(**kwargs):
        calls.update(kwargs)
        calls["openrouter_model_env"] = os.environ.get("OPENROUTER_MODEL", "")

    monkeypatch.setattr("receipt_processor.cli.run_pipeline", fake_run_pipeline)

    with runner.isolated_filesystem():
        Path(".env").write_text(
            "OPENROUTER_MODEL=anthropic/claude-3.5-sonnet\n",
            encoding="utf-8",
        )
        input_dir = Path("receipts")
        input_dir.mkdir()
        model_file = Path("model.csv")
        model_file.write_text("Date,Description,Amt Claimed (USD)\n", encoding="utf-8")
        example_file = Path("example.csv")
        example_file.write_text(
            "Date,Description,Amt Claimed (USD)\n2025 06 25,Transportation - Lyft,$54.91\n",
            encoding="utf-8",
        )

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
    assert calls["openrouter_model_env"] == "anthropic/claude-3.5-sonnet"


def test_cli_prints_run_status_and_progress(monkeypatch, tmp_path: Path) -> None:
    input_dir, model_file, example_file = _make_templates(tmp_path)

    def fake_run_pipeline(**kwargs):
        status_handler = kwargs.get("status_handler")
        progress_handler = kwargs.get("progress_handler")
        if callable(status_handler):
            status_handler(
                {
                    "event_type": "run_mode",
                    "llm_mode": "llm_supported",
                    "llm_model": "google/gemini-2.5-flash",
                    "llm_input_mode": "auto",
                    "llm_exception_assist": True,
                    "llm_runtime_overrides": {"enable_llm": True},
                }
            )
        if callable(progress_handler):
            progress_handler(
                {
                    "event_type": "progress",
                    "filename": "receipt_a.png",
                    "percent": 50,
                }
            )

    monkeypatch.setattr("receipt_processor.cli.run_pipeline", fake_run_pipeline)

    result = runner.invoke(
        app,
        [
            str(input_dir),
            "--model-file",
            str(model_file),
            "--example-file",
            str(example_file),
            "--enable-llm",
        ],
    )

    assert result.exit_code == 0
    assert "Run mode: LLM-supported extraction" in result.stdout
    assert "receipt_a.png [50% / 100%]" in result.stdout
