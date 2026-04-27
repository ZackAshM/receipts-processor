"""CLI entrypoint for ReceiptProcessor."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from receipt_processor.config.env_loader import load_local_dotenv
from receipt_processor.interface_options import OutputType, resolve_output_file
from receipt_processor.pipeline import run_pipeline
from receipt_processor.review.cli_resolver import create_cli_review_handler
from receipt_processor.review.models import RunCancelledError

app = typer.Typer(
    help=(
        "Extract expenses from receipts and export to model format.\n\n"
        "Examples:\n"
        "  receipts_processor data/inbox\n"
        "  receipts_processor /path/to/receipts --output-file /tmp/Expenses.csv"
    )
)

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
    enable_llm: bool | None = typer.Option(
        None,
        "--enable-llm/--disable-llm",
        help="Override ENABLE_LLM from environment for this run.",
    ),
    llm_model: str | None = typer.Option(
        None,
        "--llm-model",
        help="Override OPENROUTER_MODEL for this run.",
    ),
    llm_input_mode: str | None = typer.Option(
        None,
        "--llm-input-mode",
        help="Override LLM_INPUT_MODE for this run (text, file, auto).",
    ),
    llm_exception_assist: bool | None = typer.Option(
        None,
        "--enable-llm-exception-assist/--disable-llm-exception-assist",
        help="Override ENABLE_LLM_EXCEPTION_ASSIST for this run.",
    ),
) -> None:
    """Run the extraction pipeline directly from the command line."""
    load_local_dotenv(override=False)
    resolved_output = resolve_output_file(input_dir, output_file, output_type)
    review_handler = None

    def warning_handler(event: dict[str, object]) -> None:
        warning_type = str(event.get("warning_type", "")).strip()
        if warning_type == "llm_fallback":
            source_file = str(event.get("source_file", "unknown"))
            reason = str(event.get("details", "")).strip() or "unknown_reason"
            typer.echo(
                (
                    f"Warning: {source_file} used deterministic fallback because "
                    f"LLM extraction failed ({reason})."
                ),
                err=True,
            )
            return
        if warning_type == "llm_exception_assist_fallback":
            source_file = str(event.get("source_file", "unknown"))
            issue_type = str(event.get("issue_type", "unknown_issue")).strip() or "unknown_issue"
            reason = str(event.get("details", "")).strip() or "not_obvious"
            typer.echo(
                (
                    f"Info: {source_file} LLM exception assist abstained for {issue_type} "
                    f"({reason}); falling back to user review."
                ),
                err=True,
            )
            return
        if warning_type == "llm_circuit_breaker_opened":
            reason = str(event.get("details", "")).strip() or "provider instability"
            typer.echo(
                f"Warning: LLM circuit breaker opened ({reason})",
                err=True,
            )
            return
        if warning_type != "non_blocking_contradictions":
            return
        source_file = str(event.get("source_file", "unknown"))
        details = event.get("details")
        if isinstance(details, list):
            detail_text = "; ".join(str(item) for item in details)
        else:
            detail_text = str(details or "")
        if detail_text:
            typer.echo(
                (
                    f"Warning: {source_file} has non-blocking contradictions "
                    f"(kept in detailed output): {detail_text}"
                ),
                err=True,
            )
        else:
            typer.echo(
                f"Warning: {source_file} has non-blocking contradictions (kept in detailed output).",
                err=True,
            )

    def status_handler(event: dict[str, object]) -> None:
        if str(event.get("event_type", "")).strip() != "run_mode":
            return
        llm_mode = str(event.get("llm_mode", "")).strip()
        if llm_mode != "llm_supported":
            typer.echo("Run mode: deterministic extraction (LLM disabled).")
            return

        llm_model_name = str(event.get("llm_model", "")).strip() or "unknown_model"
        llm_input_mode_name = str(event.get("llm_input_mode", "")).strip() or "auto"
        exception_assist_enabled = bool(event.get("llm_exception_assist", False))
        overrides = event.get("llm_runtime_overrides")
        override_keys: list[str] = []
        if isinstance(overrides, dict):
            override_keys = sorted(str(key).strip() for key in overrides.keys() if str(key).strip())
        override_text = ", ".join(override_keys) if override_keys else "none"
        typer.echo(
            (
                "Run mode: LLM-supported extraction "
                f"(model={llm_model_name}, input_mode={llm_input_mode_name}, "
                f"exception_assist={'enabled' if exception_assist_enabled else 'disabled'}, "
                f"runtime_overrides={override_text})."
            )
        )

    def progress_handler(event: dict[str, object]) -> None:
        if str(event.get("event_type", "")).strip() != "progress":
            return
        filename = str(event.get("filename", "unknown")).strip() or "unknown"
        percent = int(event.get("percent", 0))
        typer.echo(f"{filename} [{percent}% / 100%]")

    if sys.stdin.isatty() and sys.stdout.isatty():
        review_handler = create_cli_review_handler()
    try:
        run_pipeline(
            input_dir=input_dir,
            model_file=model_file,
            example_file=example_file,
            output_file=resolved_output,
            log_dir=log_dir,
            risk_controls_file=risk_controls_file,
            enable_llm=enable_llm,
            llm_model=llm_model,
            llm_input_mode=llm_input_mode,
            llm_exception_assist=llm_exception_assist,
            review_handler=review_handler,
            warning_handler=warning_handler,
            status_handler=status_handler,
            progress_handler=progress_handler,
        )
    except RunCancelledError:
        typer.echo("Run cancelled by user.", err=True)
        raise typer.Exit(code=1)
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
