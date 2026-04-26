"""Pipeline orchestration for receipt ingestion and export."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from receipt_processor.config.risk_controls import load_risk_controls
from receipt_processor.extraction.filename_inference import infer_fields_from_filename
from receipt_processor.extraction.notes_inference import infer_fields_from_notes
from receipt_processor.extraction.ocr_router import extract_document
from receipt_processor.extraction.structured_extractor import extract_structured_data
from receipt_processor.io.exporter import export_expenses
from receipt_processor.io.file_discovery import discover_receipt_files
from receipt_processor.io.template_loader import infer_template_hints, load_model_columns, load_model_rows
from receipt_processor.io.template_renderer import map_columns_from_keywords, render_rows_from_model_template
from receipt_processor.observability.runtime_logger import RuntimeLogger
from receipt_processor.processing.expense_processor import process_structured_data, summarize_processed_rows
from receipt_processor.quality.confidence import calculate_confidence
from receipt_processor.quality.consistency import detect_contradictions, is_null_result
from receipt_processor.quality.exception_queue import (
    build_exception_record,
    export_exception_records,
)


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


def _detailed_sidecar_path(output_file: Path) -> Path:
    return output_file.with_name(f"{output_file.stem}_detailed.json")


def _amount_to_text(value: object) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value).strip()


def _write_detailed_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, default=str)


def run_pipeline(
    input_dir: Path,
    model_file: Path,
    example_file: Path,
    output_file: Path,
    log_dir: Path | None = None,
    risk_controls_file: Path | None = None,
) -> None:
    """Extract receipt data and export records in model format."""
    run_started = perf_counter()
    logger = RuntimeLogger(log_dir=log_dir)
    env_controls_path = os.environ.get("RECEIPT_PROCESSOR_RISK_CONTROLS_FILE", "").strip()
    controls_path = (
        risk_controls_file
        or (Path(env_controls_path) if env_controls_path else None)
        or Path("configs/risk_controls.yaml")
    )
    risk_controls = load_risk_controls(controls_path)

    model_columns = load_model_columns(model_file)
    template_hints = infer_template_hints(model_file, example_file)

    accepted_keyword_rows: list[dict[str, object]] = []
    accepted_processed_rows: list[dict[str, object]] = []
    detailed_receipts: list[dict[str, object]] = []
    exception_rows: list[dict] = []
    receipt_files = discover_receipt_files(input_dir)
    model_template_rows = load_model_rows(model_file)

    logger.emit(
        "run_started",
        {
            "started_at_utc": datetime.now(UTC).isoformat(),
            "input_dir": input_dir.name,
            "input_file_count": len(receipt_files),
            "model_file": model_file.name,
            "example_file": example_file.name,
            "output_file": output_file.name,
            "risk_controls_file": controls_path.name if controls_path.exists() else "default",
            "minimum_auto_accept_confidence": risk_controls.minimum_auto_accept_confidence,
            "require_manual_review_below": risk_controls.require_manual_review_below,
            "route_low_confidence_to_review": risk_controls.route_low_confidence_to_review,
        },
    )

    for receipt_path in receipt_files:
        receipt_started = perf_counter()
        try:
            extracted_document = extract_document(receipt_path)
            extracted = extract_structured_data(receipt_path, extracted_document)
            parsed_from_text = {
                "vendor": str(extracted.get("merchant_name", "")).strip(),
                "date": str(extracted.get("transaction_date", "")).strip(),
                "amount": _amount_to_text(extracted.get("amount_paid")),
                "expense_type": str(extracted.get("transaction_type", "")).strip(),
            }
            parsed_from_notes, matched_note_files = infer_fields_from_notes(
                input_dir=input_dir,
                receipt_path=receipt_path,
            )
            filename_observed_fields = infer_fields_from_filename(receipt_path.name, {})
            parsed_from_filename = infer_fields_from_filename(receipt_path.name, parsed_from_text)

            contradictions = detect_contradictions(
                {
                    "file": parsed_from_text,
                    "filename": filename_observed_fields,
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
                detailed_receipts.append(
                    {
                        "filename": receipt_path.name,
                        "status": "flagged",
                        "issue_type": "no_relevant_information",
                        "matched_notes_files": matched_note_files,
                        "extracted": extracted,
                    }
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
                detailed_receipts.append(
                    {
                        "filename": receipt_path.name,
                        "status": "flagged",
                        "issue_type": "contradiction_detected",
                        "details": contradictions,
                        "matched_notes_files": matched_note_files,
                        "extracted": extracted,
                    }
                )
                continue

            if not extracted.get("merchant_name") and parsed.get("vendor"):
                extracted["merchant_name"] = parsed["vendor"]
            if not extracted.get("transaction_date") and parsed.get("date"):
                extracted["transaction_date"] = parsed["date"]
            if not extracted.get("transaction_type") and parsed.get("expense_type"):
                extracted["transaction_type"] = parsed["expense_type"]
            if extracted.get("amount_paid") is None and parsed.get("amount"):
                try:
                    extracted["amount_paid"] = float(str(parsed["amount"]).replace("$", "").replace(",", ""))
                except ValueError:
                    pass
            if matched_note_files:
                extracted["notes_files"] = list(matched_note_files)

            processed = process_structured_data(extracted)
            keyword_values: dict[str, object] = {
                **extracted,
                **processed,
                "merchant_name": extracted.get("merchant_name", ""),
                "transaction_date": extracted.get("transaction_date", ""),
                "transaction_type": extracted.get("transaction_type", ""),
                "currency": extracted.get("currency", ""),
                "filename": receipt_path.name,
            }
            confidence_candidates, _, _ = render_rows_from_model_template(
                model_columns=model_columns,
                model_rows=model_template_rows,
                receipt_keyword_rows=[keyword_values],
                operation_values={},
                template_hints=template_hints,
            )
            if confidence_candidates:
                confidence_row = max(
                    confidence_candidates,
                    key=calculate_confidence,
                )
            else:
                confidence_row = map_columns_from_keywords(
                    model_columns=model_columns,
                    keyword_values=keyword_values,
                    template_hints=template_hints,
                )
            confidence = calculate_confidence(confidence_row)
            keyword_values["confidence"] = confidence

            if (
                risk_controls.route_low_confidence_to_review
                and confidence < risk_controls.minimum_auto_accept_confidence
            ):
                review_level = (
                    "required"
                    if confidence < risk_controls.require_manual_review_below
                    else "recommended"
                )
                low_confidence_record = dict(confidence_row)
                low_confidence_record["issue_type"] = "low_confidence"
                low_confidence_record["details"] = (
                    f"confidence={confidence:.4f} below minimum_auto_accept="
                    f"{risk_controls.minimum_auto_accept_confidence:.4f}"
                )
                low_confidence_record["review_level"] = review_level
                exception_rows.append(
                    build_exception_record(
                        receipt_path=receipt_path,
                        record=low_confidence_record,
                        errors=["Low confidence extraction result"],
                    )
                )
                logger.emit(
                    "receipt_flagged",
                    {
                        "source_file": receipt_path.name,
                        "status": "low_confidence",
                        "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                        "matched_notes_files": matched_note_files,
                        "confidence": confidence,
                        "minimum_auto_accept_confidence": (
                            risk_controls.minimum_auto_accept_confidence
                        ),
                        "require_manual_review_below": (
                            risk_controls.require_manual_review_below
                        ),
                        "review_level": review_level,
                    },
                )
                detailed_receipts.append(
                    {
                        "filename": receipt_path.name,
                        "status": "flagged",
                        "issue_type": "low_confidence",
                        "review_level": review_level,
                        "matched_notes_files": matched_note_files,
                        "extracted": extracted,
                        "processed": processed,
                        "keywords": keyword_values,
                    }
                )
                continue

            accepted_keyword_rows.append(keyword_values)
            accepted_processed_rows.append(processed)
            detailed_receipts.append(
                {
                    "filename": receipt_path.name,
                    "status": "processed",
                    "matched_notes_files": matched_note_files,
                    "extracted": extracted,
                    "processed": processed,
                    "keywords": keyword_values,
                }
            )
            logger.emit(
                "receipt_processed",
                {
                    "source_file": receipt_path.name,
                    "status": "processed",
                    "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                    "matched_notes_files": matched_note_files,
                    "confidence": confidence,
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
            detailed_receipts.append(
                {
                    "filename": receipt_path.name,
                    "status": "flagged",
                    "issue_type": "unexpected_pipeline_error",
                    "details": str(exc),
                }
            )

    operation_values = summarize_processed_rows(accepted_processed_rows)
    rendered_rows, unknown_keywords, unknown_operations = render_rows_from_model_template(
        model_columns=model_columns,
        model_rows=model_template_rows,
        receipt_keyword_rows=accepted_keyword_rows,
        operation_values=operation_values,
        template_hints=template_hints,
    )
    if unknown_keywords or unknown_operations:
        logger.emit(
            "template_tokens_unknown",
            {
                "unknown_keywords": sorted(unknown_keywords),
                "unknown_operations": sorted(unknown_operations),
            },
        )
    export_expenses(
        rendered_rows,
        output_file,
        template_hints=template_hints,
        model_columns=model_columns,
        append_summary_rows=False,
    )
    exception_output_path = _exception_sidecar_path(output_file)
    export_exception_records(exception_rows, exception_output_path)
    if not exception_rows and exception_output_path.exists():
        exception_output_path.unlink()
    detailed_payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "input_dir": input_dir.name,
        "model_file": model_file.name,
        "example_file": example_file.name,
        "output_file": output_file.name,
        "summary": {
            **operation_values,
            "processed_count": len(accepted_keyword_rows),
            "flagged_count": len(exception_rows),
            "unknown_keywords": sorted(unknown_keywords),
            "unknown_operations": sorted(unknown_operations),
        },
        "receipts": detailed_receipts,
    }
    _write_detailed_json(_detailed_sidecar_path(output_file), detailed_payload)

    logger.emit(
        "run_completed",
        {
            "processed_count": len(accepted_keyword_rows),
            "flagged_count": len(exception_rows),
            "duration_ms": round((perf_counter() - run_started) * 1000, 2),
            "output_file": output_file.name,
            "exception_output_file": exception_output_path.name,
            "detailed_output_file": _detailed_sidecar_path(output_file).name,
        },
    )
