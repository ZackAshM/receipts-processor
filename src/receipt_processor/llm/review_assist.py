"""Optional LLM-first assist for obvious exception-resolution choices."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from receipt_processor.llm.client_base import (
    LLMConfigurationError,
    LLMProviderError,
    LLMUsage,
)
from receipt_processor.llm.config import LLMSettings
from receipt_processor.llm.openrouter_client import OpenRouterClient
from receipt_processor.review.models import ReviewDecision, ReviewRequest

SUPPORTED_ISSUE_TYPES = {"contradiction_detected", "low_confidence"}
SENSITIVE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|bearer\s+[A-Za-z0-9._~+/=-]{16,})",
    re.IGNORECASE,
)
NUMERIC_STRING_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class LLMReviewAssistResult:
    """Outcome of one optional LLM exception-assist attempt."""

    attempted: bool
    resolved: bool
    reason: str
    decision: ReviewDecision | None = None
    usage: dict[str, Any] | None = None
    response_id: str | None = None


def _redact_sensitive(message: str) -> str:
    if not message:
        return ""
    return SENSITIVE_PATTERN.sub("<REDACTED_SECRET>", message)


def _usage_to_dict(usage: LLMUsage | None) -> dict[str, Any] | None:
    if usage is None:
        return None
    payload: dict[str, Any] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost_usd"):
        value = getattr(usage, key, None)
        if value is not None:
            payload[key] = value
    return payload or None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _is_numeric_like(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if not any(char.isdigit() for char in text):
        return False

    normalized = text.lower().strip()
    normalized = re.sub(r"\b(?:usd|eur|gbp|cad|aud|chf|jpy)\b", "", normalized)
    normalized = normalized.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
    normalized = normalized.replace(",", "").replace(" ", "")
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    if normalized.endswith("%"):
        normalized = normalized[:-1]

    return bool(NUMERIC_STRING_RE.fullmatch(normalized))


def _request_has_numeric_decision_options(request: ReviewRequest) -> bool:
    for field in request.fields:
        for option in field.options:
            if _is_numeric_like(str(option.value or "")):
                return True
    return False


def _build_request_payload(
    *,
    request: ReviewRequest,
    source_fields: dict[str, dict[str, str]],
    receipt_filename: str,
) -> dict[str, Any]:
    fields_payload: list[dict[str, Any]] = []
    for field in request.fields:
        options_payload = [
            {
                "source": str(option.source or "").strip(),
                "value": str(option.value or "").strip(),
                "label": str(option.label or "").strip(),
            }
            for option in field.options
            if str(option.value or "").strip()
        ]
        fields_payload.append(
            {
                "name": field.name,
                "display_name": field.display_name,
                "options": options_payload,
                "allow_manual": bool(field.allow_manual),
            }
        )

    clean_source_fields: dict[str, dict[str, str]] = {}
    for source_name, values in source_fields.items():
        if not isinstance(values, dict):
            continue
        clean_values: dict[str, str] = {}
        for key, value in values.items():
            text = str(value or "").strip()
            if text:
                clean_values[str(key).strip()] = text
        if clean_values:
            clean_source_fields[str(source_name).strip()] = clean_values

    return {
        "receipt_filename": receipt_filename,
        "issue_type": request.issue_type,
        "title": request.title,
        "message": request.message,
        "fields": fields_payload,
        "source_fields": clean_source_fields,
    }


def _validate_resolution(
    *,
    request: ReviewRequest,
    response_payload: dict[str, Any],
) -> tuple[dict[str, str], float | None, str]:
    action = str(response_payload.get("action", "")).strip().lower()
    if action != "resolve":
        return {}, _to_float(response_payload.get("confidence")), "abstained"

    confidence = _to_float(response_payload.get("confidence"))
    raw_fields = response_payload.get("resolved_fields")
    if not isinstance(raw_fields, dict):
        return {}, confidence, "invalid_resolved_fields_shape"

    allowed_values: dict[str, set[str]] = {}
    for field in request.fields:
        allowed_values[field.name] = {
            str(option.value).strip()
            for option in field.options
            if str(option.value).strip()
        }

    resolved_fields: dict[str, str] = {}
    for key, value in raw_fields.items():
        field = str(key or "").strip()
        selected = str(value or "").strip()
        if not field or not selected:
            continue
        allowed = allowed_values.get(field, set())
        if not allowed:
            continue
        if selected in allowed:
            resolved_fields[field] = selected

    if not resolved_fields:
        return {}, confidence, "no_valid_option_selected"

    return resolved_fields, confidence, "resolved"


def attempt_llm_review_resolution(
    *,
    request: ReviewRequest,
    source_fields: dict[str, dict[str, str]],
    receipt_filename: str,
    settings: LLMSettings,
    client: OpenRouterClient | None = None,
) -> LLMReviewAssistResult:
    """Attempt conservative LLM auto-resolution for obvious exception choices."""
    if not settings.enabled:
        return LLMReviewAssistResult(attempted=False, resolved=False, reason="llm_disabled")
    if not settings.enable_exception_assist:
        return LLMReviewAssistResult(
            attempted=False,
            resolved=False,
            reason="llm_exception_assist_disabled",
        )
    if request.issue_type not in SUPPORTED_ISSUE_TYPES:
        return LLMReviewAssistResult(
            attempted=False,
            resolved=False,
            reason="unsupported_issue_type",
        )
    if not request.fields:
        return LLMReviewAssistResult(attempted=False, resolved=False, reason="no_review_fields")
    if _request_has_numeric_decision_options(request):
        return LLMReviewAssistResult(
            attempted=False,
            resolved=False,
            reason="numeric_decisions_require_user",
        )

    has_option_candidates = any(field.options for field in request.fields)
    if not has_option_candidates:
        return LLMReviewAssistResult(
            attempted=False,
            resolved=False,
            reason="no_option_candidates",
        )
    if not settings.has_api_key:
        return LLMReviewAssistResult(attempted=True, resolved=False, reason="missing_api_key")

    payload = _build_request_payload(
        request=request,
        source_fields=source_fields,
        receipt_filename=receipt_filename,
    )
    try:
        resolved_client = client or OpenRouterClient(
            api_key=settings.api_key,
            timeout_seconds=settings.timeout_seconds,
            base_url=settings.base_url,
            app_referer=settings.app_referer,
            app_title=settings.app_title,
            pdf_engine=settings.pdf_engine,
            input_cost_per_1k_tokens=settings.input_cost_per_1k_tokens,
            output_cost_per_1k_tokens=settings.output_cost_per_1k_tokens,
        )
        response = resolved_client.assist_review_resolution(
            model=settings.model,
            review_payload=payload,
        )
        resolved_fields, confidence, reason = _validate_resolution(
            request=request,
            response_payload=response.payload,
        )
        if not resolved_fields:
            return LLMReviewAssistResult(
                attempted=True,
                resolved=False,
                reason=reason,
                usage=_usage_to_dict(response.usage),
                response_id=response.response_id,
            )
        return LLMReviewAssistResult(
            attempted=True,
            resolved=True,
            reason=f"resolved_confidence_{confidence:.2f}" if confidence is not None else "resolved",
            decision=ReviewDecision(action="resolved", resolved_fields=resolved_fields),
            usage=_usage_to_dict(response.usage),
            response_id=response.response_id,
        )
    except (LLMConfigurationError, LLMProviderError) as exc:
        return LLMReviewAssistResult(
            attempted=True,
            resolved=False,
            reason=_redact_sensitive(str(exc)) or type(exc).__name__,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        return LLMReviewAssistResult(
            attempted=True,
            resolved=False,
            reason=f"unexpected_llm_error:{type(exc).__name__}",
        )
