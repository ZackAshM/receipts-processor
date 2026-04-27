"""Orchestrates deterministic extraction with optional LLM augmentation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from receipt_processor.extraction.ocr_router import DocumentExtraction
from receipt_processor.llm.client_base import LLMClient, LLMStructuredOutputError
from receipt_processor.llm.config import LLMSettings, load_llm_settings
from receipt_processor.llm.extractor import LLMExtractionService
from receipt_processor.llm.schema import normalize_llm_payload

DownstreamValidator = Callable[[dict[str, Any]], object]


@dataclass(frozen=True)
class LLMExtractionResult:
    """Final extraction selection and diagnostics for one receipt."""

    extracted: dict[str, Any]
    deterministic_extracted: dict[str, Any]
    extraction_mode: str
    llm_enabled: bool
    llm_attempted: bool
    llm_requested_mode: str
    llm_used_mode: str | None
    llm_model: str | None
    llm_failure_reason: str | None = None
    llm_usage: dict[str, Any] | None = None
    llm_response_id: str | None = None
    warning_event: dict[str, Any] | None = None

    def to_log_payload(self, *, source_file: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_file": source_file,
            "extraction_mode": self.extraction_mode,
            "llm_enabled": self.llm_enabled,
            "llm_attempted": self.llm_attempted,
            "llm_requested_mode": self.llm_requested_mode,
            "llm_used_mode": self.llm_used_mode or "",
            "llm_model": self.llm_model or "",
        }
        if self.llm_failure_reason:
            payload["llm_failure_reason"] = self.llm_failure_reason
        if self.llm_usage:
            payload["llm_usage"] = dict(self.llm_usage)
        if self.llm_response_id:
            payload["llm_response_id"] = self.llm_response_id
        return payload


def _fallback_result(
    *,
    deterministic_extracted: dict[str, Any],
    settings: LLMSettings,
    attempted: bool,
    requested_mode: str,
    used_mode: str | None,
    reason: str,
    source_file: str,
    usage: dict[str, Any] | None = None,
    response_id: str | None = None,
) -> LLMExtractionResult:
    warning_event = {
        "warning_type": "llm_fallback",
        "source_file": source_file,
        "details": reason,
        "llm_requested_mode": requested_mode,
        "llm_used_mode": used_mode or "",
    }
    return LLMExtractionResult(
        extracted=dict(deterministic_extracted),
        deterministic_extracted=dict(deterministic_extracted),
        extraction_mode="llm_fallback" if attempted else "deterministic",
        llm_enabled=settings.enabled,
        llm_attempted=attempted,
        llm_requested_mode=requested_mode,
        llm_used_mode=used_mode,
        llm_model=settings.model if settings.enabled else None,
        llm_failure_reason=reason,
        llm_usage=usage,
        llm_response_id=response_id,
        warning_event=warning_event if attempted else None,
    )


def _usage_to_dict(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    payload: dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost_usd"):
        value = getattr(usage, key, None)
        if value is not None:
            payload[key] = value
    return payload or None


def extract_with_optional_llm(
    *,
    receipt_path: Path,
    document: DocumentExtraction,
    deterministic_extracted: dict[str, Any],
    settings: LLMSettings | None = None,
    client: LLMClient | None = None,
    downstream_validator: DownstreamValidator | None = None,
    llm_context: dict[str, Any] | None = None,
) -> LLMExtractionResult:
    """Return selected extraction using LLM when available, with safe fallback."""
    resolved_settings = settings or load_llm_settings()
    service = LLMExtractionService(settings=resolved_settings, client=client)
    attempt = service.attempt(
        receipt_path=receipt_path,
        document=document,
        llm_context=llm_context,
    )

    if not resolved_settings.enabled:
        return LLMExtractionResult(
            extracted=dict(deterministic_extracted),
            deterministic_extracted=dict(deterministic_extracted),
            extraction_mode="deterministic",
            llm_enabled=False,
            llm_attempted=False,
            llm_requested_mode=attempt.requested_mode,
            llm_used_mode=attempt.used_mode,
            llm_model=None,
        )

    if not attempt.success or attempt.response is None:
        return _fallback_result(
            deterministic_extracted=deterministic_extracted,
            settings=resolved_settings,
            attempted=attempt.attempted,
            requested_mode=attempt.requested_mode,
            used_mode=attempt.used_mode,
            reason=attempt.failure_reason or "llm_extraction_failed",
            source_file=receipt_path.name,
        )

    usage_payload = _usage_to_dict(attempt.response.usage)
    try:
        normalized = normalize_llm_payload(
            receipt_filename=receipt_path.name,
            payload=attempt.response.payload,
            deterministic_base=deterministic_extracted,
        )
    except LLMStructuredOutputError as exc:
        return _fallback_result(
            deterministic_extracted=deterministic_extracted,
            settings=resolved_settings,
            attempted=True,
            requested_mode=attempt.requested_mode,
            used_mode=attempt.used_mode,
            reason=f"invalid_structured_output:{exc}",
            source_file=receipt_path.name,
            usage=usage_payload,
            response_id=attempt.response.response_id,
        )

    if downstream_validator is not None:
        try:
            downstream_validator(normalized)
        except Exception as exc:
            return _fallback_result(
                deterministic_extracted=deterministic_extracted,
                settings=resolved_settings,
                attempted=True,
                requested_mode=attempt.requested_mode,
                used_mode=attempt.used_mode,
                reason=f"failed_downstream_validation:{type(exc).__name__}",
                source_file=receipt_path.name,
                usage=usage_payload,
                response_id=attempt.response.response_id,
            )

    return LLMExtractionResult(
        extracted=normalized,
        deterministic_extracted=dict(deterministic_extracted),
        extraction_mode="llm",
        llm_enabled=True,
        llm_attempted=True,
        llm_requested_mode=attempt.requested_mode,
        llm_used_mode=attempt.used_mode,
        llm_model=resolved_settings.model,
        llm_usage=usage_payload,
        llm_response_id=attempt.response.response_id,
    )
