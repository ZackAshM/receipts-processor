"""Environment-based configuration for optional LLM extraction."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class LLMInputMode(str, Enum):
    """Supported strategies for preparing LLM input."""

    text = "text"
    file = "file"
    auto = "auto"

    @classmethod
    def parse(cls, raw: str | None) -> "LLMInputMode":
        candidate = (raw or "").strip().lower() or cls.auto.value
        try:
            return cls(candidate)
        except ValueError:
            return cls.auto


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_float(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        return default


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class LLMSettings:
    """Resolved LLM settings from environment variables."""

    enabled: bool = False
    api_key: str = ""
    model: str = "google/gemini-2.5-flash"
    input_mode: LLMInputMode = LLMInputMode.auto
    base_url: str = "https://openrouter.ai/api/v1"
    app_referer: str = ""
    app_title: str = "ReceiptProcessor"
    pdf_engine: str = ""
    timeout_seconds: float = 30.0
    max_input_chars: int = 12000
    input_cost_per_1k_tokens: float | None = None
    output_cost_per_1k_tokens: float | None = None
    enable_exception_assist: bool = False

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key.strip())

    def redacted(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "enable_exception_assist": self.enable_exception_assist,
            "model": self.model,
            "input_mode": self.input_mode.value,
            "base_url": self.base_url,
            "app_referer_set": bool(self.app_referer),
            "app_title": self.app_title,
            "pdf_engine": self.pdf_engine,
            "timeout_seconds": self.timeout_seconds,
            "max_input_chars": self.max_input_chars,
            "has_api_key": self.has_api_key,
        }


def load_llm_settings() -> LLMSettings:
    """Load optional LLM settings from process environment."""
    enabled = _parse_bool(os.environ.get("ENABLE_LLM"), default=False)
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("OPENROUTER_MODEL", "").strip() or "google/gemini-2.5-flash"
    input_mode = LLMInputMode.parse(os.environ.get("LLM_INPUT_MODE"))
    base_url = os.environ.get("OPENROUTER_BASE_URL", "").strip() or "https://openrouter.ai/api/v1"
    app_referer = os.environ.get("OPENROUTER_HTTP_REFERER", "").strip()
    app_title = os.environ.get("OPENROUTER_APP_TITLE", "").strip() or "ReceiptProcessor"
    pdf_engine = os.environ.get("OPENROUTER_PDF_ENGINE", "").strip()
    timeout_seconds = max(1.0, _parse_float(os.environ.get("LLM_TIMEOUT_SECONDS"), 30.0))
    max_input_chars = max(2000, _parse_int(os.environ.get("LLM_MAX_INPUT_CHARS"), 12000))

    input_cost = os.environ.get("OPENROUTER_INPUT_COST_PER_1K_TOKENS", "").strip()
    output_cost = os.environ.get("OPENROUTER_OUTPUT_COST_PER_1K_TOKENS", "").strip()
    enable_exception_assist = _parse_bool(
        os.environ.get("ENABLE_LLM_EXCEPTION_ASSIST"),
        default=False,
    )
    input_cost_value = _parse_float(input_cost, -1.0) if input_cost else None
    output_cost_value = _parse_float(output_cost, -1.0) if output_cost else None
    if input_cost_value is not None and input_cost_value < 0:
        input_cost_value = None
    if output_cost_value is not None and output_cost_value < 0:
        output_cost_value = None

    return LLMSettings(
        enabled=enabled,
        api_key=api_key,
        model=model,
        input_mode=input_mode,
        base_url=base_url,
        app_referer=app_referer,
        app_title=app_title,
        pdf_engine=pdf_engine,
        timeout_seconds=timeout_seconds,
        max_input_chars=max_input_chars,
        input_cost_per_1k_tokens=input_cost_value,
        output_cost_per_1k_tokens=output_cost_value,
        enable_exception_assist=enable_exception_assist,
    )
