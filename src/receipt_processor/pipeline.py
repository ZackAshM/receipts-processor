"""Pipeline orchestration for receipt ingestion and export."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from receipt_processor.extraction.filename_inference import infer_fields_from_filename
from receipt_processor.extraction.notes_inference import infer_fields_from_notes
from receipt_processor.extraction.ocr_router import extract_text
from receipt_processor.extraction.receipt_parser import parse_receipt_text
from receipt_processor.extraction.schema_mapper import map_to_model_columns
from receipt_processor.io.exporter import export_expenses
from receipt_processor.io.file_discovery import discover_receipt_files
from receipt_processor.io.template_loader import infer_template_hints, load_model_columns
from receipt_processor.observability.runtime_logger import RuntimeLogger
from receipt_processor.quality.confidence import calculate_confidence
from receipt_processor.quality.consistency import detect_contradictions, is_null_result
from receipt_processor.quality.exception_queue import (
    build_exception_record,
    export_exception_records,
)
from receipt_processor.quality.validation import validate_expense_record


def _merge_fields_by_priority(*sources: dict[str, str]) -> dict[str, str]:
    """Merge multiple field dictionaries from lowest to highest priority."""
    merged: dict[str, str] = {}
    for source in sources:
        for key, value in source.items():
            if value not in (None, ""):
                merged[key] = value
    return merged


def _exception_sidecar_path(output_file: Path) -> Path:
    return output_file.with_name(f"{output_file.stem}_exceptions.csv")


def run_pipeline(
    input_dir: Path,
    model_file: Path,
    example_file: Path,
    output_file: Path,
    log_dir: Path | None = None,
) -> None:
    """Extract receipt data and export records in model format."""
    run_started = perf_counter()
    logger = RuntimeLogger(log_dir=log_dir)

    model_columns = load_model_columns(model_file)
    template_hints = infer_template_hints(model_file, example_file)

    mapped_rows: list[dict[str, str]] = []
    exception_rows: list[dict] = []
    receipt_files = discover_receipt_files(input_dir)

    logger.emit(
        "run_started",
        {
            "started_at_utc": datetime.now(UTC).isoformat(),
            "input_dir": input_dir.name,
            "input_file_count": len(receipt_files),
            "model_file": model_file.name,
            "example_file": example_file.name,
            "output_file": output_file.name,
        },
    )

    for receipt_path in receipt_files:
        receipt_started = perf_counter()
        try:
            raw_text = extract_text(receipt_path)
            parsed_from_text = parse_receipt_text(raw_text)
            parsed_from_notes, matched_note_files = infer_fields_from_notes(
                input_dir=input_dir,
                receipt_path=receipt_path,
            )
            parsed_from_filename = infer_fields_from_filename(receipt_path.name, parsed_from_text)

            contradictions = detect_contradictions(
                {
                    "file": parsed_from_text,
                    "filename": parsed_from_filename,
                    "notes": parsed_from_notes,
                }
            )

            parsed = _merge_fields_by_priority(
                parsed_from_filename,
                parsed_from_notes,
                parsed_from_text,
            )
            if matched_note_files:
                parsed["notes_files"] = ", ".join(matched_note_files)

            if is_null_result(parsed):
                exception_rows.append(
                    build_exception_record(
                        receipt_path=receipt_path,
                        record={
                            "issue_type": "no_relevant_information",
                            "details": (
                                "No relevant fields extracted from file text, filename,"
                                " or notes context."
                            ),
                        },
                        errors=["No relevant information found"],
                    )
                )
                logger.emit(
                    "receipt_flagged",
                    {
                        "source_file": receipt_path.name,
                        "status": "no_relevant_information",
                        "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                        "matched_notes_files": matched_note_files,
                    },
                )
                continue

            if contradictions:
                exception_rows.append(
                    build_exception_record(
                        receipt_path=receipt_path,
                        record={
                            "issue_type": "contradiction_detected",
                            "details": " | ".join(contradictions),
                        },
                        errors=["Contradicting information across sources"],
                    )
                )
                logger.emit(
                    "receipt_flagged",
                    {
                        "source_file": receipt_path.name,
                        "status": "contradiction_detected",
                        "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                        "matched_notes_files": matched_note_files,
                        "details": contradictions,
                    },
                )
                continue

            record = map_to_model_columns(parsed, model_columns, template_hints)
            record["_confidence"] = str(calculate_confidence(record))

            is_valid, errors = validate_expense_record(record)
            if not is_valid:
                exception_rows.append(build_exception_record(receipt_path, record, errors))
                logger.emit(
                    "receipt_flagged",
                    {
                        "source_file": receipt_path.name,
                        "status": "validation_failed",
                        "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                        "matched_notes_files": matched_note_files,
                        "details": errors,
                    },
                )
                continue

            mapped_rows.append(record)
            logger.emit(
                "receipt_processed",
                {
                    "source_file": receipt_path.name,
                    "status": "processed",
                    "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                    "matched_notes_files": matched_note_files,
                    "confidence": record.get("_confidence", ""),
                },
            )
        except Exception as exc:
            exception_rows.append(
                build_exception_record(
                    receipt_path,
                    {
                        "issue_type": "unexpected_pipeline_error",
                        "details": f"{exc}",
                    },
                    ["Unexpected pipeline error"],
                )
            )
            logger.emit(
                "receipt_flagged",
                {
                    "source_file": receipt_path.name,
                    "status": "unexpected_pipeline_error",
                    "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                    "details": str(exc),
                },
            )

    export_expenses(
        mapped_rows,
        output_file,
        template_hints=template_hints,
        model_columns=model_columns,
    )
    export_exception_records(exception_rows, _exception_sidecar_path(output_file))

    logger.emit(
        "run_completed",
        {
            "processed_count": len(mapped_rows),
            "flagged_count": len(exception_rows),
            "duration_ms": round((perf_counter() - run_started) * 1000, 2),
            "output_file": output_file.name,
            "exception_output_file": _exception_sidecar_path(output_file).name,
        },
    )
