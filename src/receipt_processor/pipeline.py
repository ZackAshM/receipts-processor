"""Pipeline orchestration for receipt ingestion and export."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable

from receipt_processor.config.risk_controls import load_risk_controls
from receipt_processor.extraction.filename_inference import infer_fields_from_filename
from receipt_processor.extraction.notes_inference import collect_note_context, infer_fields_from_notes
from receipt_processor.extraction.ocr_router import extract_document
from receipt_processor.extraction.structured_extractor import extract_structured_data
from receipt_processor.extraction.transaction_type import normalize_transaction_type
from receipt_processor.io.exporter import export_expenses
from receipt_processor.io.file_discovery import discover_receipt_files
from receipt_processor.io.template_loader import infer_template_hints, load_model_columns, load_model_rows
from receipt_processor.io.template_renderer import (
    SUPPORTED_TEMPLATE_KEYWORDS,
    SUPPORTED_TEMPLATE_OPERATIONS,
    collect_template_tokens,
    has_keyword_placeholders,
    infer_required_review_fields,
    normalize_date_string,
    render_rows_from_model_template,
)
from receipt_processor.llm.config import LLMInputMode, LLMSettings, load_llm_settings
from receipt_processor.llm.context_sanitizer import sanitize_statement_text
from receipt_processor.llm.orchestrator import extract_with_optional_llm
from receipt_processor.llm.review_assist import LLMReviewAssistResult, attempt_llm_review_resolution
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


def _summary_sidecar_path(output_file: Path) -> Path:
    return output_file.with_name(f"{output_file.stem}_summary.md")


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


def _format_money(value: object) -> str:
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _safe_markdown_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _write_detailed_summary_markdown(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    receipts = payload.get("receipts", []) if isinstance(payload, dict) else []

    lines: list[str] = []
    lines.append("# ReceiptProcessor Summary")
    lines.append("")
    lines.append("## Run")
    lines.append(f"- Generated (UTC): {_safe_markdown_text(payload.get('generated_at_utc'))}")
    lines.append(f"- Input Dir: {_safe_markdown_text(payload.get('input_dir'))}")
    lines.append(f"- Output File: {_safe_markdown_text(payload.get('output_file'))}")
    lines.append("")
    lines.append("## Totals")
    lines.append(f"- Processed Receipts: {_safe_markdown_text(summary.get('processed_count'))}")
    lines.append(f"- Flagged Receipts: {_safe_markdown_text(summary.get('flagged_count'))}")
    lines.append(f"- Total Expenses: {_format_money(summary.get('total_expenses'))}")
    lines.append(f"- Total Receipt Expenses: {_format_money(summary.get('total_receipt_expenses'))}")
    lines.append(f"- Review Count: {_safe_markdown_text(summary.get('review_count'))}")
    lines.append("")
    lines.append("## Receipts")
    lines.append(
        "| Filename | Status | Merchant | Date | True Expense | Receipt Expense | Needs Review | Issue | Extraction |"
    )
    lines.append("|---|---|---|---|---:|---:|---|---|---|")

    if isinstance(receipts, list):
        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            extracted = receipt.get("extracted", {})
            processed = receipt.get("processed", {})
            extraction = receipt.get("extraction", {})
            issue = receipt.get("issue_type", "")
            if not issue:
                blocking = receipt.get("blocking_contradictions", [])
                if isinstance(blocking, list) and blocking:
                    issue = "; ".join(str(item) for item in blocking if str(item).strip())
            lines.append(
                "| "
                + " | ".join(
                    [
                        _safe_markdown_text(receipt.get("filename")),
                        _safe_markdown_text(receipt.get("status")),
                        _safe_markdown_text(
                            extracted.get("merchant_name") if isinstance(extracted, dict) else ""
                        ),
                        _safe_markdown_text(
                            extracted.get("transaction_date") if isinstance(extracted, dict) else ""
                        ),
                        _format_money(
                            processed.get("true_expense") if isinstance(processed, dict) else None
                        ),
                        _format_money(
                            processed.get("receipt_expense") if isinstance(processed, dict) else None
                        ),
                        _safe_markdown_text(
                            processed.get("needs_review") if isinstance(processed, dict) else ""
                        ),
                        _safe_markdown_text(issue),
                        _safe_markdown_text(
                            extraction.get("extraction_mode") if isinstance(extraction, dict) else ""
                        ),
                    ]
                )
                + " |"
            )
    lines.append("")
    lines.append("_Generated for readability from Expenses_detailed.json._")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _resolve_llm_settings(
    *,
    enable_llm: bool | None,
    llm_model: str | None,
    llm_input_mode: str | None,
    llm_exception_assist: bool | None,
) -> tuple[LLMSettings, dict[str, object]]:
    base_settings = load_llm_settings()
    resolved = base_settings
    overrides: dict[str, object] = {}

    if enable_llm is not None:
        resolved = replace(resolved, enabled=bool(enable_llm))
        overrides["enable_llm"] = bool(enable_llm)

    if llm_model is not None:
        candidate_model = str(llm_model).strip()
        if candidate_model:
            resolved = replace(resolved, model=candidate_model)
            overrides["llm_model"] = candidate_model

    if llm_input_mode is not None:
        parsed_mode = LLMInputMode.parse(llm_input_mode)
        resolved = replace(resolved, input_mode=parsed_mode)
        overrides["llm_input_mode"] = parsed_mode.value

    if llm_exception_assist is not None:
        resolved = replace(resolved, enable_exception_assist=bool(llm_exception_assist))
        overrides["llm_exception_assist"] = bool(llm_exception_assist)

    return resolved, overrides


REVIEW_FIELD_ORDER = ("vendor", "date", "amount", "expense_type")
REVIEW_FIELD_LABELS = {
    "vendor": "Vendor",
    "date": "Date",
    "amount": "Amount",
    "expense_type": "Transaction Type",
}
WarningHandler = Callable[[dict[str, object]], None]
StatusHandler = Callable[[dict[str, object]], None]
ProgressHandler = Callable[[dict[str, object]], None]
STATEMENT_FILENAME_HINTS = (
    "statement",
    "credit",
    "bank",
    "account",
    "card",
    "visa",
    "mastercard",
    "amex",
    "discover",
)
MAX_STATEMENT_CONTEXT_FILES = 3
MAX_STATEMENT_CONTEXT_CHARS = 2200
MAX_NOTE_CONTEXT_CHARS = 1800
STANDARD_OUTPUT_DATE_FORMAT = "%Y/%m/%d"
LLM_CIRCUIT_BREAKER_FAILURE_STREAK = 3
LLM_PROVIDER_FAILURE_HINTS = (
    "status=429",
    "status=500",
    "status=502",
    "status=503",
    "status=504",
    "timeout",
    "connection",
    "rate_limit",
    "openrouter api",
    "missing structured content",
    "missing message content",
    "operation was aborted",
)


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


def _looks_like_statement(path: Path) -> bool:
    name = path.stem.lower()
    return any(token in name for token in STATEMENT_FILENAME_HINTS)


def _collect_statement_context(receipt_files: list[Path]) -> list[dict[str, str]]:
    context_rows: list[dict[str, str]] = []
    for path in receipt_files:
        if len(context_rows) >= MAX_STATEMENT_CONTEXT_FILES:
            break
        if not _looks_like_statement(path):
            continue
        extracted = extract_document(path)
        compact_text = sanitize_statement_text(
            extracted.raw_text or "",
            max_chars=MAX_STATEMENT_CONTEXT_CHARS,
        )
        if not compact_text:
            continue
        context_rows.append(
            {
                "filename": path.name,
                "text": compact_text[:MAX_STATEMENT_CONTEXT_CHARS],
            }
        )
    return context_rows


def _build_llm_context(
    *,
    receipt_path: Path,
    note_context_entries: list[tuple[str, str]],
    statement_context_rows: list[dict[str, str]],
) -> dict[str, object]:
    notes_context: list[dict[str, str]] = []
    for note_name, note_text in note_context_entries:
        compact = " ".join(note_text.split()).strip()
        if not compact:
            continue
        notes_context.append({"filename": note_name, "text": compact[:MAX_NOTE_CONTEXT_CHARS]})

    filtered_statements = [
        dict(item)
        for item in statement_context_rows
        if str(item.get("filename", "")).strip() != receipt_path.name
    ]

    return {
        "filename": receipt_path.name,
        "notes": notes_context,
        "statements": filtered_statements,
    }


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
            extracted["transaction_date"] = normalize_date_string(
                value,
                STANDARD_OUTPUT_DATE_FORMAT,
            )
        elif key == "amount":
            try:
                extracted["amount_paid"] = float(value.replace("$", "").replace(",", ""))
            except ValueError:
                pass
        elif key == "expense_type":
            extracted["transaction_type"] = normalize_transaction_type(
                value,
                context_text=str(extracted.get("merchant_name", "")).strip(),
            )

    extracted["transaction_date"] = normalize_date_string(
        extracted.get("transaction_date", ""),
        STANDARD_OUTPUT_DATE_FORMAT,
    )


def _recompute_contradictions_after_resolution(
    *,
    parsed: dict[str, str],
    filename_observed_fields: dict[str, str],
    parsed_from_notes: dict[str, str],
    resolved_fields: dict[str, str],
    required_review_fields: set[str],
) -> tuple[list[str], list[str], list[str]]:
    contradictions = detect_contradictions(
        {
            "file": {
                "vendor": str(parsed.get("vendor", "")).strip(),
                "date": str(parsed.get("date", "")).strip(),
                "amount": str(parsed.get("amount", "")).strip(),
                "expense_type": str(parsed.get("expense_type", "")).strip(),
            },
            "filename": filename_observed_fields,
            "notes": parsed_from_notes,
        }
    )
    contradictions = _filter_resolved_contradictions(
        contradictions,
        resolved_fields,
    )
    blocking_contradictions, non_blocking_contradictions = _partition_contradictions(
        contradictions,
        required_review_fields,
    )
    return contradictions, blocking_contradictions, non_blocking_contradictions


def _llm_assist_log_payload(
    *,
    source_file: str,
    issue_type: str,
    result: LLMReviewAssistResult,
    llm_model: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_file": source_file,
        "issue_type": issue_type,
        "attempted": result.attempted,
        "resolved": result.resolved,
        "reason": result.reason,
        "llm_model": llm_model,
    }
    if result.decision is not None and result.decision.resolved_fields:
        payload["resolved_fields"] = sorted(result.decision.resolved_fields.keys())
    if result.usage:
        payload["llm_usage"] = dict(result.usage)
    if result.response_id:
        payload["llm_response_id"] = result.response_id
    return payload


def _is_provider_llm_failure(reason: str) -> bool:
    lowered = str(reason or "").strip().lower()
    if not lowered:
        return False
    if lowered.startswith("invalid_structured_output:") or lowered.startswith(
        "failed_downstream_validation:"
    ):
        return False
    return any(hint in lowered for hint in LLM_PROVIDER_FAILURE_HINTS)


def _should_skip_llm_exception_assist(extraction_details: dict[str, object]) -> bool:
    extraction_mode = str(extraction_details.get("extraction_mode", "")).strip().lower()
    failure_reason = str(extraction_details.get("llm_failure_reason", "")).strip()
    if extraction_mode != "llm_fallback":
        return False
    return _is_provider_llm_failure(failure_reason)


def _emit_llm_assist_fallback_warning(
    *,
    source_file: str,
    issue_type: str,
    llm_assist_result: LLMReviewAssistResult,
    logger: RuntimeLogger,
    warning_handler: WarningHandler | None,
) -> None:
    if not llm_assist_result.attempted or llm_assist_result.resolved:
        return
    warning_event = {
        "warning_type": "llm_exception_assist_fallback",
        "source_file": source_file,
        "issue_type": issue_type,
        "details": llm_assist_result.reason,
    }
    logger.emit("receipt_warning", warning_event)
    if warning_handler is not None:
        warning_handler(dict(warning_event))


def run_pipeline(
    input_dir: Path,
    model_file: Path,
    example_file: Path,
    output_file: Path,
    log_dir: Path | None = None,
    risk_controls_file: Path | None = None,
    enable_llm: bool | None = None,
    llm_model: str | None = None,
    llm_input_mode: str | None = None,
    llm_exception_assist: bool | None = None,
    review_handler: ReviewHandler | None = None,
    warning_handler: WarningHandler | None = None,
    status_handler: StatusHandler | None = None,
    progress_handler: ProgressHandler | None = None,
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
    llm_settings, llm_overrides = _resolve_llm_settings(
        enable_llm=enable_llm,
        llm_model=llm_model,
        llm_input_mode=llm_input_mode,
        llm_exception_assist=llm_exception_assist,
    )

    model_columns = load_model_columns(model_file)
    template_hints = infer_template_hints(model_file, example_file)
    template_hints = replace(template_hints, date_output_format=STANDARD_OUTPUT_DATE_FORMAT)

    accepted_keyword_rows: list[dict[str, object]] = []
    accepted_processed_rows: list[dict[str, object]] = []
    detailed_receipts: list[dict[str, object]] = []
    exception_rows: list[dict] = []
    receipt_files = discover_receipt_files(input_dir)
    statement_context_rows = _collect_statement_context(receipt_files) if llm_settings.enabled else []
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
            "llm_settings": llm_settings.redacted(),
            "llm_runtime_overrides": llm_overrides,
        },
    )
    run_mode_event: dict[str, object] = {
        "event_type": "run_mode",
        "input_file_count": len(receipt_files),
        "llm_mode": "llm_supported" if llm_settings.enabled else "deterministic",
        "llm_model": llm_settings.model if llm_settings.enabled else "",
        "llm_input_mode": llm_settings.input_mode.value,
        "llm_exception_assist": bool(llm_settings.enable_exception_assist),
        "llm_runtime_overrides": llm_overrides,
    }
    logger.emit("run_mode", dict(run_mode_event))
    if status_handler is not None:
        status_handler(dict(run_mode_event))

    total_files = len(receipt_files)
    completed_files = 0
    llm_circuit_breaker_open = False
    llm_provider_failure_streak = 0

    for receipt_path in receipt_files:
        receipt_started = perf_counter()
        extraction_mode = "deterministic"
        effective_llm_settings = llm_settings
        if llm_circuit_breaker_open and llm_settings.enabled:
            effective_llm_settings = replace(llm_settings, enabled=False)
        extraction_details: dict[str, object] = {
            "extraction_mode": extraction_mode,
            "llm_attempted": False,
            "llm_requested_mode": "text",
            "llm_used_mode": "",
            "llm_model": "",
        }
        try:
            note_context_entries = collect_note_context(input_dir=input_dir, receipt_path=receipt_path)
            llm_context = _build_llm_context(
                receipt_path=receipt_path,
                note_context_entries=note_context_entries,
                statement_context_rows=statement_context_rows,
            )
            extracted_document = extract_document(receipt_path)
            deterministic_extracted = extract_structured_data(receipt_path, extracted_document)
            llm_result = extract_with_optional_llm(
                receipt_path=receipt_path,
                document=extracted_document,
                deterministic_extracted=deterministic_extracted,
                settings=effective_llm_settings,
                downstream_validator=process_structured_data,
                llm_context=llm_context,
            )
            extracted = llm_result.extracted
            extracted["transaction_date"] = normalize_date_string(
                extracted.get("transaction_date", ""),
                STANDARD_OUTPUT_DATE_FORMAT,
            )
            extraction_mode = llm_result.extraction_mode
            extraction_details = {
                "extraction_mode": llm_result.extraction_mode,
                "llm_attempted": llm_result.llm_attempted,
                "llm_requested_mode": llm_result.llm_requested_mode,
                "llm_used_mode": llm_result.llm_used_mode or "",
                "llm_model": llm_result.llm_model or "",
                "llm_failure_reason": llm_result.llm_failure_reason or "",
                "llm_usage": llm_result.llm_usage or {},
                "llm_response_id": llm_result.llm_response_id or "",
            }
            if (
                effective_llm_settings.enabled
                and llm_result.extraction_mode == "llm"
            ):
                llm_provider_failure_streak = 0
            elif (
                effective_llm_settings.enabled
                and llm_result.llm_attempted
                and llm_result.extraction_mode == "llm_fallback"
                and _is_provider_llm_failure(llm_result.llm_failure_reason or "")
            ):
                llm_provider_failure_streak += 1
                if (
                    not llm_circuit_breaker_open
                    and llm_provider_failure_streak >= LLM_CIRCUIT_BREAKER_FAILURE_STREAK
                ):
                    llm_circuit_breaker_open = True
                    breaker_warning = {
                        "warning_type": "llm_circuit_breaker_opened",
                        "source_file": receipt_path.name,
                        "details": (
                            "LLM provider failures reached streak threshold; "
                            "continuing run in deterministic mode."
                        ),
                        "failure_streak": llm_provider_failure_streak,
                    }
                    logger.emit("receipt_warning", breaker_warning)
                    if warning_handler is not None:
                        warning_handler(dict(breaker_warning))
            elif effective_llm_settings.enabled and llm_result.llm_attempted:
                llm_provider_failure_streak = 0
            logger.emit(
                "extraction_strategy_selected",
                llm_result.to_log_payload(source_file=receipt_path.name),
            )
            if llm_result.warning_event is not None:
                logger.emit("receipt_warning", llm_result.warning_event)
                if warning_handler is not None:
                    warning_handler(dict(llm_result.warning_event))
            parsed_from_text = {
                "vendor": str(extracted.get("merchant_name", "")).strip(),
                "date": str(extracted.get("transaction_date", "")).strip(),
                "amount": _amount_to_text(extracted.get("amount_paid")),
                "expense_type": str(extracted.get("transaction_type", "")).strip(),
            }
            parsed_from_notes, matched_note_files = infer_fields_from_notes(
                input_dir=input_dir,
                receipt_path=receipt_path,
                note_context=note_context_entries,
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
                            "extraction_mode": extraction_mode,
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
                            "extraction": extraction_details,
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
                contradiction_request = ReviewRequest(
                    issue_type="contradiction_detected",
                    title="Contradiction Detected",
                    message=(
                        "Contradicting source values were found. "
                        "Choose one source value or enter manual input."
                    ),
                    receipt_filename=receipt_path.name,
                    fields=conflict_fields,
                )
                if _should_skip_llm_exception_assist(extraction_details):
                    llm_assist_result = LLMReviewAssistResult(
                        attempted=False,
                        resolved=False,
                        reason="skipped_after_llm_provider_failure",
                    )
                else:
                    llm_assist_result = attempt_llm_review_resolution(
                        request=contradiction_request,
                        source_fields=source_fields,
                        receipt_filename=receipt_path.name,
                        settings=effective_llm_settings,
                    )
                logger.emit(
                    "llm_exception_assist",
                    _llm_assist_log_payload(
                        source_file=receipt_path.name,
                        issue_type="contradiction_detected",
                        result=llm_assist_result,
                        llm_model=llm_settings.model if llm_settings.enabled else "",
                    ),
                )
                if review_handler is not None and conflict_fields:
                    _emit_llm_assist_fallback_warning(
                        source_file=receipt_path.name,
                        issue_type="contradiction_detected",
                        llm_assist_result=llm_assist_result,
                        logger=logger,
                        warning_handler=warning_handler,
                    )

                decision: ReviewDecision | None = None
                decision_source = ""
                if llm_assist_result.resolved and llm_assist_result.decision is not None:
                    decision = llm_assist_result.decision
                    decision_source = "llm_exception_assist"
                elif review_handler is not None and conflict_fields:
                    decision = review_handler(contradiction_request)
                    decision_source = "user_review"

                if decision is not None:
                    if decision.action == "cancel_run":
                        raise RunCancelledError("Run cancelled by user review action.")
                    review_actions.append(
                        {
                            "issue_type": "contradiction_detected",
                            "action": (
                                "resolved_via_llm_exception_assist"
                                if decision_source == "llm_exception_assist"
                                and decision.action == "resolved"
                                else decision.action
                            ),
                            "decision_source": decision_source,
                            "resolved_fields": dict(decision.resolved_fields),
                        }
                    )
                    if decision.action == "resolved":
                        _apply_resolved_fields(decision.resolved_fields, parsed, extracted)
                        (
                            contradictions,
                            blocking_contradictions,
                            non_blocking_contradictions,
                        ) = _recompute_contradictions_after_resolution(
                            parsed=parsed,
                            filename_observed_fields=filename_observed_fields,
                            parsed_from_notes=parsed_from_notes,
                            resolved_fields=decision.resolved_fields,
                            required_review_fields=required_review_fields,
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
                            "extraction_mode": extraction_mode,
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
                            "extraction": extraction_details,
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
            extracted["transaction_date"] = normalize_date_string(
                extracted.get("transaction_date", ""),
                STANDARD_OUTPUT_DATE_FORMAT,
            )
            if (
                parsed.get("expense_type")
                and str(extracted.get("transaction_type", "")).strip() in {"", "Misc"}
            ):
                extracted["transaction_type"] = normalize_transaction_type(
                    parsed["expense_type"],
                    context_text=str(extracted.get("merchant_name", "")).strip(),
                )
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
                low_confidence_request = ReviewRequest(
                    issue_type="low_confidence",
                    title="Low Confidence Extraction",
                    message=(
                        "Extraction confidence is below the acceptance threshold. "
                        "Provide manual corrections, skip this receipt, or cancel the run."
                    ),
                    receipt_filename=receipt_path.name,
                    fields=editable_fields,
                )
                if _should_skip_llm_exception_assist(extraction_details):
                    llm_assist_result = LLMReviewAssistResult(
                        attempted=False,
                        resolved=False,
                        reason="skipped_after_llm_provider_failure",
                    )
                else:
                    llm_assist_result = attempt_llm_review_resolution(
                        request=low_confidence_request,
                        source_fields=source_fields,
                        receipt_filename=receipt_path.name,
                        settings=effective_llm_settings,
                    )
                logger.emit(
                    "llm_exception_assist",
                    _llm_assist_log_payload(
                        source_file=receipt_path.name,
                        issue_type="low_confidence",
                        result=llm_assist_result,
                        llm_model=llm_settings.model if llm_settings.enabled else "",
                    ),
                )
                if review_handler is not None and editable_fields:
                    _emit_llm_assist_fallback_warning(
                        source_file=receipt_path.name,
                        issue_type="low_confidence",
                        llm_assist_result=llm_assist_result,
                        logger=logger,
                        warning_handler=warning_handler,
                    )

                decision: ReviewDecision | None = None
                decision_source = ""
                if llm_assist_result.resolved and llm_assist_result.decision is not None:
                    decision = llm_assist_result.decision
                    decision_source = "llm_exception_assist"
                elif review_handler is not None and editable_fields:
                    decision = review_handler(low_confidence_request)
                    decision_source = "user_review"

                if decision is not None:
                    if decision.action == "cancel_run":
                        raise RunCancelledError("Run cancelled by user review action.")
                    review_actions.append(
                        {
                            "issue_type": "low_confidence",
                            "action": (
                                "resolved_via_llm_exception_assist"
                                if decision_source == "llm_exception_assist"
                                and decision.action == "resolved"
                                else decision.action
                            ),
                            "decision_source": decision_source,
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
                            "extraction_mode": extraction_mode,
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
                            "extraction": extraction_details,
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
                    "extraction": extraction_details,
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
                    "extraction_mode": extraction_mode,
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
                    "extraction_mode": extraction_mode,
                    "duration_ms": round((perf_counter() - receipt_started) * 1000, 2),
                    "details": str(exc),
                },
            )
            detailed_receipts.append(
                {
                    "filename": receipt_path.name,
                    "status": "flagged",
                    "issue_type": "unexpected_pipeline_error",
                    "extraction": extraction_details,
                    "details": str(exc),
                }
            )
        finally:
            completed_files += 1
            percent = int(round((completed_files / total_files) * 100)) if total_files > 0 else 100
            progress_event = {
                "event_type": "progress",
                "filename": receipt_path.name,
                "completed": completed_files,
                "total": total_files,
                "percent": max(0, min(100, percent)),
            }
            if progress_handler is not None:
                progress_handler(dict(progress_event))

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
    detailed_output_path = _detailed_sidecar_path(output_file)
    summary_output_path = _summary_sidecar_path(output_file)
    _write_detailed_json(detailed_output_path, detailed_payload)
    _write_detailed_summary_markdown(summary_output_path, detailed_payload)

    logger.emit(
        "run_completed",
        {
            "processed_count": len(accepted_keyword_rows),
            "flagged_count": len(exception_rows),
            "duration_ms": round((perf_counter() - run_started) * 1000, 2),
            "output_file": output_file.name,
            "exception_output_file": exception_output_path.name,
            "detailed_output_file": detailed_output_path.name,
            "summary_output_file": summary_output_path.name,
        },
    )
