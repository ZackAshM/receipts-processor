"""CLI entrypoint for ReceiptProcessor."""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

import typer

from receipt_processor.pipeline import run_pipeline

app = typer.Typer(
    help=(
        "Extract expenses from receipts and export to model format.\n\n"
        "Examples:\n"
        "  receipts_processor data/inbox\n"
        "  receipts_processor /path/to/receipts --output-file /tmp/Expenses.csv"
    )
)


class OutputType(str, Enum):
    csv = "csv"
    xlsx = "xlsx"


def _resolve_output_file(
    input_dir: Path,
    output_file: Path | None,
    output_type: OutputType,
) -> Path:
    if output_file is None:
        return input_dir / f"Expenses.{output_type.value}"

    if output_file.suffix:
        return output_file

    return output_file.with_suffix(f".{output_type.value}")


@app.command()
def run(
    input_dir: Path = typer.Argument(
        Path("data/inbox"),
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=False,
        help="Folder containing receipt files (.pdf, .jpeg, .jpg, .png).",
    ),
    model_file: Path = typer.Option(
        Path("models/model.csv"),
        "--model-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Model template file (.csv or .xlsx).",
    ),
    example_file: Path = typer.Option(
        Path("models/example.csv"),
        "--example-file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        help="Example template file (.csv or .xlsx).",
    ),
    output_file: Path | None = typer.Option(
        None,
        "--output-file",
        file_okay=True,
        dir_okay=False,
        help=(
            "Output expenses file (.csv or .xlsx). If omitted, default is "
            "<input_dir>/Expenses.<output-type>."
        ),
    ),
    output_type: OutputType = typer.Option(
        OutputType.csv,
        "--output-type",
        help="Default output format when extension is not specified (csv or xlsx).",
    ),
    log_dir: Path | None = typer.Option(
        Path("logs"),
        "--log-dir",
        help="Directory for structured runtime logs.",
    ),
    risk_controls_file: Path | None = typer.Option(
        None,
        "--risk-controls-file",
        help="Optional YAML file for confidence routing controls.",
    ),
) -> None:
    """Run the extraction pipeline directly from the command line."""
    resolved_output = _resolve_output_file(input_dir, output_file, output_type)
    run_pipeline(
        input_dir=input_dir,
        model_file=model_file,
        example_file=example_file,
        output_file=resolved_output,
        log_dir=log_dir,
        risk_controls_file=risk_controls_file,
    )
    typer.echo(f"Export complete: {resolved_output}")


def main() -> None:
    """Console-script entrypoint."""
    args = list(sys.argv[1:])
    # Backward compatibility for older command style:
    # `... build-expenses --input-dir ...`
    if args and args[0] == "build-expenses":
        args = args[1:]
    app(args=args, prog_name=sys.argv[0])


if __name__ == "__main__":
    main()
