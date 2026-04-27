"""LLM extraction service responsible for provider interactions only."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from receipt_processor.extraction.ocr_router import DocumentExtraction, extract_document
from receipt_processor.io.format_detector import detect_receipt_format
from receipt_processor.llm.client_base import (
    LLMClient,
    LLMConfigurationError,
    LLMExtractionResponse,
    LLMProviderError,
    LLMUnsupportedInputError,
)
from receipt_processor.llm.config import LLMInputMode, LLMSettings
from receipt_processor.llm.openrouter_client import OpenRouterClient

SENSITIVE_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|bearer\s+[A-Za-z0-9._~+/=-]{16,})",
    re.IGNORECASE,
)
TRANSIENT_PROVIDER_PATTERNS = (
    "status=429",
    "status=500",
    "status=502",
    "status=503",
    "status=504",
    "rate_limit",
    "timeout",
    "connection",
    "temporarily unavailable",
    "operation was aborted",
)
CAPABILITY_FILE_MODE_HINTS = (
    "does_not_support_file_mode",
    "unsupported direct-file mime type",
    "unsupported_file_type_for_direct_mode",
    "does not support file mode",
)
MAX_PROVIDER_RETRIES = 2
RETRY_BACKOFF_SECONDS = (0.4, 1.0, 2.0)


@dataclass(frozen=True)
class LLMAttemptResult:
    """Outcome of one LLM extraction attempt."""

    attempted: bool
    success: bool
    requested_mode: str
    used_mode: str | None
    response: LLMExtractionResponse | None = None
    failure_reason: str | None = None


def _redact_sensitive(message: str) -> str:
    if not message:
        return ""
    return SENSITIVE_PATTERN.sub("<REDACTED_SECRET>", message)


def _mime_type_for_file(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".pdf":
        return "application/pdf"
    return None


def _is_transient_provider_error(message: str) -> bool:
    lowered = str(message or "").strip().lower()
    if not lowered:
        return False
    return any(pattern in lowered for pattern in TRANSIENT_PROVIDER_PATTERNS)


def _is_file_mode_capability_error(message: str) -> bool:
    lowered = str(message or "").strip().lower()
    if not lowered:
        return False
    return any(pattern in lowered for pattern in CAPABILITY_FILE_MODE_HINTS)


class LLMExtractionService:
    """Executes LLM semantic extraction with mode routing and safe errors."""

    def __init__(
        self,
        *,
        settings: LLMSettings,
        client: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client

    def _client_or_raise(self) -> LLMClient:
        if self._client is not None:
            return self._client
        self._client = OpenRouterClient(
            api_key=self.settings.api_key,
            timeout_seconds=self.settings.timeout_seconds,
            base_url=self.settings.base_url,
            app_referer=self.settings.app_referer,
            app_title=self.settings.app_title,
            pdf_engine=self.settings.pdf_engine,
            input_cost_per_1k_tokens=self.settings.input_cost_per_1k_tokens,
            output_cost_per_1k_tokens=self.settings.output_cost_per_1k_tokens,
        )
        return self._client

    def _resolve_mode(self, receipt_path: Path) -> LLMInputMode:
        requested = self.settings.input_mode
        if requested != LLMInputMode.auto:
            return requested
        file_kind = detect_receipt_format(receipt_path)
        if file_kind in {"image", "pdf"}:
            return LLMInputMode.file
        return LLMInputMode.text

    @staticmethod
    def _render_context_text(llm_context: dict[str, Any] | None, *, max_chars: int) -> str:
        if not llm_context:
            return ""

        sections: list[str] = []
        filename = str(llm_context.get("filename", "")).strip()
        if filename:
            sections.append(f"filename_hint: {filename}")

        notes = llm_context.get("notes")
        if isinstance(notes, list) and notes:
            note_chunks: list[str] = []
            for entry in notes:
                if not isinstance(entry, dict):
                    continue
                note_name = str(entry.get("filename", "")).strip() or "notes"
                note_text = str(entry.get("text", "")).strip()
                if not note_text:
                    continue
                note_chunks.append(f"[{note_name}] {note_text}")
            if note_chunks:
                sections.append("notes_context:\n" + "\n".join(note_chunks))

        statements = llm_context.get("statements")
        if isinstance(statements, list) and statements:
            statement_chunks: list[str] = []
            for entry in statements:
                if not isinstance(entry, dict):
                    continue
                statement_name = str(entry.get("filename", "")).strip() or "statement"
                statement_text = str(entry.get("text", "")).strip()
                if not statement_text:
                    continue
                statement_chunks.append(f"[{statement_name}] {statement_text}")
            if statement_chunks:
                sections.append("statement_context:\n" + "\n".join(statement_chunks))

        rendered = "\n\n".join(section for section in sections if section.strip()).strip()
        if not rendered:
            return ""
        return rendered[:max_chars]

    def _prepare_text_input(self, receipt_path: Path, document: DocumentExtraction) -> str:
        raw_text = (document.raw_text or "").strip()
        if len(raw_text) >= max(40, self.settings.max_input_chars // 300):
            return raw_text

        # If extracted text is suspiciously short, re-run OCR router once so text mode
        # can still benefit from OCR fallback logic before we send content to the model.
        refreshed = extract_document(receipt_path)
        refreshed_text = (refreshed.raw_text or "").strip()
        if refreshed_text:
            return refreshed_text
        return raw_text

    def _attempt_text_mode(
        self,
        *,
        client: LLMClient,
        receipt_path: Path,
        document: DocumentExtraction,
        llm_context: dict[str, Any] | None,
    ) -> LLMExtractionResponse:
        raw_text = self._prepare_text_input(receipt_path, document)
        if not raw_text:
            raise LLMProviderError("empty_text_input_after_ocr_check")
        max_total_chars = max(1000, int(self.settings.max_input_chars))
        context_budget = max(500, int(max_total_chars * 0.35))
        context_text = self._render_context_text(llm_context, max_chars=context_budget)
        text_budget = max(800, max_total_chars - len(context_text))
        truncated_text = raw_text[:text_budget]
        return self._call_with_retries(
            lambda: client.extract_from_text(
                model=self.settings.model,
                filename=receipt_path.name,
                text=truncated_text,
                context_text=context_text,
            )
        )

    def _call_with_retries(self, call: Callable[[], LLMExtractionResponse]) -> LLMExtractionResponse:
        attempt = 0
        while True:
            try:
                return call()
            except LLMProviderError as exc:
                attempt += 1
                message = str(exc)
                if attempt > MAX_PROVIDER_RETRIES or not _is_transient_provider_error(message):
                    raise
                delay = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
                time.sleep(delay)

    def attempt(
        self,
        *,
        receipt_path: Path,
        document: DocumentExtraction,
        llm_context: dict[str, Any] | None = None,
    ) -> LLMAttemptResult:
        requested_mode = self.settings.input_mode.value
        if not self.settings.enabled:
            return LLMAttemptResult(
                attempted=False,
                success=False,
                requested_mode=requested_mode,
                used_mode=None,
                failure_reason="llm_disabled",
            )
        if not self.settings.has_api_key:
            return LLMAttemptResult(
                attempted=True,
                success=False,
                requested_mode=requested_mode,
                used_mode=None,
                failure_reason="missing_api_key",
            )

        resolved_mode = self._resolve_mode(receipt_path)
        used_mode = resolved_mode.value
        try:
            client = self._client_or_raise()
            if resolved_mode == LLMInputMode.text:
                response = self._attempt_text_mode(
                    client=client,
                    receipt_path=receipt_path,
                    document=document,
                    llm_context=llm_context,
                )
            else:
                mime_type = _mime_type_for_file(receipt_path)
                if not mime_type:
                    raise LLMUnsupportedInputError(
                        f"unsupported_file_type_for_direct_mode:{receipt_path.suffix.lower() or 'unknown'}"
                    )
                context_text = self._render_context_text(
                    llm_context,
                    max_chars=max(500, int(self.settings.max_input_chars * 0.35)),
                )
                try:
                    response = self._call_with_retries(
                        lambda: client.extract_from_file(
                            model=self.settings.model,
                            filename=receipt_path.name,
                            file_bytes=receipt_path.read_bytes(),
                            mime_type=mime_type,
                            context_text=context_text,
                        )
                    )
                except LLMUnsupportedInputError as file_exc:
                    # Capability-aware fallback: if direct file mode is not supported,
                    # retry using OCR/local text extraction input.
                    try:
                        response = self._attempt_text_mode(
                            client=client,
                            receipt_path=receipt_path,
                            document=document,
                            llm_context=llm_context,
                        )
                        used_mode = LLMInputMode.text.value
                    except LLMProviderError as text_exc:
                        raise LLMProviderError(
                            "file_mode_failed_then_text_failed:"
                            f"{str(file_exc)} | {str(text_exc)}"
                        ) from text_exc
                except LLMProviderError as file_exc:
                    if not _is_file_mode_capability_error(str(file_exc)):
                        # Provider/API failures should not trigger another LLM call path.
                        raise
                    try:
                        response = self._attempt_text_mode(
                            client=client,
                            receipt_path=receipt_path,
                            document=document,
                            llm_context=llm_context,
                        )
                        used_mode = LLMInputMode.text.value
                    except LLMProviderError as text_exc:
                        raise LLMProviderError(
                            "file_mode_failed_then_text_failed:"
                            f"{str(file_exc)} | {str(text_exc)}"
                        ) from text_exc

            return LLMAttemptResult(
                attempted=True,
                success=True,
                requested_mode=requested_mode,
                used_mode=used_mode,
                response=response,
            )
        except (LLMConfigurationError, LLMUnsupportedInputError, LLMProviderError) as exc:
            return LLMAttemptResult(
                attempted=True,
                success=False,
                requested_mode=requested_mode,
                used_mode=used_mode,
                failure_reason=_redact_sensitive(str(exc)) or type(exc).__name__,
            )
        except Exception as exc:  # pragma: no cover - defensive catch for unknown client failures
            return LLMAttemptResult(
                attempted=True,
                success=False,
                requested_mode=requested_mode,
                used_mode=used_mode,
                failure_reason=f"unexpected_llm_error:{type(exc).__name__}",
            )
