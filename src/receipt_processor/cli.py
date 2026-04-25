"""CLI entrypoint for ReceiptProcessor."""

from pathlib import Path

import typer

from receipt_processor.pipeline import run_pipeline

app = typer.Typer(help="Extract expenses from receipts and export to model format.")


@app.command("build-expenses")
def build_expenses(
    input_dir: Path = typer.Option(..., exists=True, file_okay=False, dir_okay=True),
    model_file: Path = typer.Option(..., exists=True),
    example_file: Path = typer.Option(..., exists=True),
    output_file: Path = typer.Option(...),
    log_dir: Path | None = typer.Option(
        None,
        help="Optional directory for structured performance logs.",
    ),
) -> None:
    """Run the end-to-end extraction pipeline."""
    run_pipeline(
        input_dir=input_dir,
        model_file=model_file,
        example_file=example_file,
        output_file=output_file,
        log_dir=log_dir,
    )
    typer.echo(f"Export complete: {output_file}")


if __name__ == "__main__":
    app()
