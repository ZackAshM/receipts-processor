"""Pipeline orchestration for receipt ingestion and export."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable

from receipt_processor.config.risk_controls import load_risk_controls
from receipt_processor.extraction.filename_inference import infer_fields_from_filename
from receipt_processor.extraction.notes_inference import infer_fields_from_notes
from receipt_processor.extraction.ocr_router import extract_document
from receipt_processor.extraction.structured_extractor import extract_structured_data
from receipt_processor.io.exporter import export_expenses
from receipt_processor.io.file_discovery import discover_receipt_files
from receipt_processor.io.template_loader import infer_template_hints, load_model_columns, load_model_rows
from receipt_processor.io.template_renderer import (
    SUPPORTED_TEMPLATE_KEYWORDS,
    SUPPORTED_TEMPLATE_OPERATIONS,
    collect_template_tokens,
    has_keyword_placeholders,
    infer_required_review_fields,
    render_rows_from_model_template,
)
from receipt_processor.observability.runtime_logger import RuntimeLogger
from receipt_processor.processing.expense_processor import process_structured_data, summarize_processed_rows
from receipt_processor.quality.confidence import calculate_confidence
from receipt_processor.quality.consistency import detect_contradictions
from receipt_processor.quality.exception_queue import (
    build_exception_record,
    export_exception_records,
)
from receipt_processor.review.models import (
    ReviewField,
    ReviewHandler,
    ReviewOption,
    ReviewRequest,
    RunCancelledError,
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


REVIEW_FIELD_ORDER = ("vendor", "date", "amount", "expense_type")
REVIEW_FIELD_LABELS = {
    "vendor": "Vendor",
    "date": "Date",
    "amount": "Amount",
    "expense_type": "Transaction Type",
}
WarningHandler = Callable[[dict[str, object]], None]


def _ordered_required_fields(required_fields: set[str]) -> list[str]:
    return [field for field in REVIEW_FIELD_ORDER if field in required_fields]


def _is_null_result_for_required_fields(
    fields: dict[str, str],
    required_fields: set[str],
) -> bool:
    ordered = _ordered_required_fields(required_fields)
    if not ordered:
        return False
    return all(not str(fields.get(field, "")).strip() for field in ordered)


def _build_conflict_review_fields(
    source_fields: dict[str, dict[str, str]],
    required_fields: set[str],
) -> list[ReviewField]:
    fields: list[ReviewField] = []
    for key in _ordered_required_fields(required_fields):
        options: list[ReviewOption] = []
        seen: set[str] = set()
        for source_name, values in source_fields.items():
            value = str(values.get(key, "")).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            options.append(ReviewOption(source=source_name, value=value))
        if len(options) > 1:
            fields.append(
                ReviewField(
                    name=key,
                    display_name=REVIEW_FIELD_LABELS.get(key, key),
                    options=options,
                )
            )
    return fields


def _build_manual_review_fields(required_fields: set[str]) -> list[ReviewField]:
    return [
        ReviewField(
            name=field,
            display_name=REVIEW_FIELD_LABELS.get(field, field),
            options=[],
        )
        for field in _ordered_required_fields(required_fields)
    ]


def _build_editable_review_fields(
    source_fields: dict[str, dict[str, str]],
    required_fields: set[str],
) -> list[ReviewField]:
    fields: list[ReviewField] = []
    for key in _ordered_required_fields(required_fields):
        options: list[ReviewOption] = []
        seen: set[str] = set()
        for source_name, values in source_fields.items():
            value = str(values.get(key, "")).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            options.append(ReviewOption(source=source_name, value=value))
        fields.append(
            ReviewField(
                name=key,
                display_name=REVIEW_FIELD_LABELS.get(key, key),
                options=options,
            )
        )
    return fields


def _filter_resolved_contradictions(
    contradictions: list[str],
    resolved_fields: dict[str, str],
) -> list[str]:
    resolved_keys = {
        key.strip().lower()
        for key, value in resolved_fields.items()
        if str(value).strip()
    }
    if not resolved_keys:
        return contradictions

    filtered: list[str] = []
    for item in contradictions:
        normalized = item.strip().lower()
        if any(normalized.startswith(f"{key} mismatch") for key in resolved_keys):
            continue
        filtered.append(item)
    return filtered


def _contradiction_field(contradiction: str) -> str:
    lowered = contradiction.strip().lower()
    marker = " mismatch"
    idx = lowered.find(marker)
    if idx <= 0:
        return ""
    return lowered[:idx].strip()


def _partition_contradictions(
    contradictions: list[str],
    required_fields: set[str],
) -> tuple[list[str], list[str]]:
    if not contradictions:
        return [], []

    blocking: list[str] = []
    non_blocking: list[str] = []
    for contradiction in contradictions:
        field = _contradiction_field(contradiction)
        if field and field in required_fields:
            blocking.append(contradiction)
        else:
            non_blocking.append(contradiction)
    return blocking, non_blocking


def _apply_resolved_fields(
    resolved_fields: dict[str, str],
    parsed: dict[str, str],
    extracted: dict[str, object],
) -> None:
    for key, raw_value in resolved_fields.items():
        value = str(raw_value).strip()
        if not value:
            continue
        parsed[key] = value
        if key == "vendor":
            extracted["merchant_name"] = value
        elif key == "date":
            extracted["transaction_date"] = value
        elif key == "amount":
            try:
                extracted["amount_paid"] = float(value.replace("$", "").replace(",", ""))
            except ValueError:
                pass
        elif key == "expense_type":
            extracted["transaction_type"] = value


def run_pipeline(
    input_dir: Path,
    model_file: Path,
    example_file: Path,
    output_file: Path,
    log_dir: Path | None = None,
    risk_controls_file: Path | None = None,
    review_handler: ReviewHandler | None = None,
    warning_handler: WarningHandler | None = None,
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
    template_keywords, template_operations = collect_template_tokens(model_template_rows)
    preflight_unknown_keywords = sorted(template_keywords - SUPPORTED_TEMPLATE_KEYWORDS)
    preflight_unknown_operations = sorted(template_operations - SUPPORTED_TEMPLATE_OPERATIONS)
    if preflight_unknown_keywords or preflight_unknown_operations:
        raise ValueError(
            "Unknown template tokens detected before processing; refusing to run. "
            f"unknown_keywords={preflight_unknown_keywords} "
            f"unknown_operations={preflight_unknown_operations}"
        )
    required_review_fields = infer_required_review_fields(
        model_columns=model_columns,
        model_rows=model_template_rows,
    )
    sorted_required_review_fields = sorted(required_review_fields)
    if receipt_files and not has_keyword_placeholders(model_template_rows):
        raise ValueError(
            "Model template must include at least one {{keyword}} placeholder row. "
            "Alias-based column mapping is no longer supported."
        )

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
            "required_review_fields": sorted_required_review_fields,
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

            source_fields = {
                "file": parsed_from_text,
                "filename": filename_observed_fields,
                "notes": parsed_from_notes,
            }
            contradictions = detect_contradictions(source_fields)
            blocking_contradictions, non_blocking_contradictions = _partition_contradictions(
                contradictions,
                required_review_fields,
            )

            parsed = _merge_fields_by_priority(
                parsed_from_filename,
                parsed_from_notes,
                parsed_from_text,
            )
            if matched_note_files:
                parsed["notes_files"] = ", ".join(matched_note_files)
            review_actions: list[dict[str, object]] = []

            if _is_null_result_for_required_fields(parsed, required_review_fields):
                manual_fields = _build_manual_review_fields(required_review_fields)
                if review_handler is not None and manual_fields:
                    decision = review_handler(
                        ReviewRequest(
                            issue_type="no_relevant_information",
                            title="No Relevant Information Found",
                            message=(
                                "No reliable fields were extracted. Enter manual values, "
                                "skip this receipt, or cancel the run."
                            ),
                            receipt_filename=receipt_path.name,
                            fields=manual_fields,
                        )
                    )
                    if decision.action == "cancel_run":
                        raise RunCancelledError("Run cancelled by user review action.")
                    review_actions.append(
                        {
                            "issue_type": "no_relevant_information",
                            "action": decision.action,
                            "resolved_fields": dict(decision.resolved_fields),
                        }
                    )
                    if decision.action == "resolved":
                        _apply_resolved_fields(decision.resolved_fields, parsed, extracted)

                if _is_null_result_for_required_fields(parsed, required_review_fields):
                    exception_rows.append(
                        build_exception_record(
                            receipt_path=receipt_path,
                            record={
                                "issue_type": "no_relevant_information",
                                "details": (
                                    "No model-required fields extracted from file text, "
                                    "filename, or notes context."
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
                            "required_review_fields": sorted_required_review_fields,
                            "matched_notes_files": matched_note_files,
                            "contradictions": contradictions,
                            "blocking_contradictions": blocking_contradictions,
                            "non_blocking_contradictions": non_blocking_contradictions,
                            "extracted": extracted,
                            "review_actions": review_actions,
                        }
                    )
                    continue

            if blocking_contradictions:
                conflict_fields = _build_conflict_review_fields(
                    source_fields,
                    {_contradiction_field(item) for item in blocking_contradictions},
                )
                if review_handler is not None and conflict_fields:
                    decision = review_handler(
                        ReviewRequest(
                            issue_type="contradiction_detected",
                            title="Contradiction Detected",
                            message=(
                                "Contradicting source values were found. "
                                "Choose one source value or enter manual input."
                            ),
                            receipt_filename=receipt_path.name,
                            fields=conflict_fields,
                        )
                    )
                    if decision.action == "cancel_run":
                        raise RunCancelledError("Run cancelled by user review action.")
                    review_actions.append(
                        {
                            "issue_type": "contradiction_detected",
                            "action": decision.action,
                            "resolved_fields": dict(decision.resolved_fields),
                        }
                    )
                    if decision.action == "resolved":
                        _apply_resolved_fields(decision.resolved_fields, parsed, extracted)
                        contradictions = detect_contradictions(
                            {
                                "file": {
                                    "vendor": str(parsed.get("vendor", "")).strip(),
                                    "date": str(parsed.get("date", "")).strip(),
                                    "amount": str(parsed.get("amount", "")).strip(),
                                },
                                "filename": filename_observed_fields,
                                "notes": parsed_from_notes,
                            }
                        )
                        contradictions = _filter_resolved_contradictions(
                            contradictions,
                            decision.resolved_fields,
                        )
                        (
                            blocking_contradictions,
                            non_blocking_contradictions,
                        ) = _partition_contradictions(
                            contradictions,
                            required_review_fields,
                        )

                if blocking_contradictions:
                    exception_rows.append(
                        build_exception_record(
                            receipt_path=receipt_path,
                            record={
                                "issue_type": "contradiction_detected",
                                "details": " | ".join(blocking_contradictions),
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
                            "details": blocking_contradictions,
                        },
                    )
                    detailed_receipts.append(
                        {
                            "filename": receipt_path.name,
                            "status": "flagged",
                            "issue_type": "contradiction_detected",
                            "required_review_fields": sorted_required_review_fields,
                            "details": blocking_contradictions,
                            "all_contradictions": contradictions,
                            "blocking_contradictions": blocking_contradictions,
                            "non_blocking_contradictions": non_blocking_contradictions,
                            "matched_notes_files": matched_note_files,
                            "extracted": extracted,
                            "review_actions": review_actions,
                        }
                    )
                    continue

            if non_blocking_contradictions and not blocking_contradictions:
                warning_event = {
                    "warning_type": "non_blocking_contradictions",
                    "source_file": receipt_path.name,
                    "details": list(non_blocking_contradictions),
                    "required_review_fields": sorted_required_review_fields,
                }
                logger.emit("receipt_warning", warning_event)
                if warning_handler is not None:
                    warning_handler(dict(warning_event))

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
                confidence_row = {}
            confidence = calculate_confidence(confidence_row)
            keyword_values["confidence"] = confidence

            if (
                risk_controls.route_low_confidence_to_review
                and confidence < risk_controls.minimum_auto_accept_confidence
            ):
                editable_fields = _build_editable_review_fields(
                    source_fields,
                    required_review_fields,
                )
                if review_handler is not None and editable_fields:
                    decision = review_handler(
                        ReviewRequest(
                            issue_type="low_confidence",
                            title="Low Confidence Extraction",
                            message=(
                                "Extraction confidence is below the acceptance threshold. "
                                "Provide manual corrections, skip this receipt, or cancel the run."
                            ),
                            receipt_filename=receipt_path.name,
                            fields=editable_fields,
                        )
                    )
                    if decision.action == "cancel_run":
                        raise RunCancelledError("Run cancelled by user review action.")
                    review_actions.append(
                        {
                            "issue_type": "low_confidence",
                            "action": decision.action,
                            "resolved_fields": dict(decision.resolved_fields),
                        }
                    )
                    if decision.action == "resolved":
                        _apply_resolved_fields(decision.resolved_fields, parsed, extracted)
                        processed = process_structured_data(extracted)
                        keyword_values = {
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
                            confidence_row = max(confidence_candidates, key=calculate_confidence)
                        else:
                            confidence_row = {}
                        confidence = calculate_confidence(confidence_row)
                        keyword_values["confidence"] = confidence

                if confidence < risk_controls.minimum_auto_accept_confidence:
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
                            "required_review_fields": sorted_required_review_fields,
                            "review_level": review_level,
                            "matched_notes_files": matched_note_files,
                            "contradictions": contradictions,
                            "blocking_contradictions": blocking_contradictions,
                            "non_blocking_contradictions": non_blocking_contradictions,
                            "extracted": extracted,
                            "processed": processed,
                            "keywords": keyword_values,
                            "review_actions": review_actions,
                        }
                    )
                    continue

            accepted_keyword_rows.append(keyword_values)
            accepted_processed_rows.append(processed)
            detailed_receipts.append(
                {
                    "filename": receipt_path.name,
                    "status": "processed",
                    "required_review_fields": sorted_required_review_fields,
                    "matched_notes_files": matched_note_files,
                    "contradictions": contradictions,
                    "blocking_contradictions": blocking_contradictions,
                    "non_blocking_contradictions": non_blocking_contradictions,
                    "extracted": extracted,
                    "processed": processed,
                    "keywords": keyword_values,
                    "review_actions": review_actions,
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
        except RunCancelledError:
            raise
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
        details = {
            "unknown_keywords": sorted(unknown_keywords),
            "unknown_operations": sorted(unknown_operations),
        }
        logger.emit(
            "template_tokens_unknown",
            details,
        )
        raise ValueError(
            "Unknown template tokens detected; refusing to export with blank substitutions. "
            f"unknown_keywords={details['unknown_keywords']} "
            f"unknown_operations={details['unknown_operations']}"
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
