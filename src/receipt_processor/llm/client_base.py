"""Provider-agnostic client interfaces and LLM-specific exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(Exception):
    """Base exception type for optional LLM extraction errors."""


class LLMConfigurationError(LLMError):
    """Raised when required runtime/provider configuration is missing."""


class LLMProviderError(LLMError):
    """Raised for provider/API errors, timeouts, or malformed responses."""


class LLMUnsupportedInputError(LLMError):
    """Raised when requested input mode is not supported by the provider client."""


class LLMStructuredOutputError(LLMError):
    """Raised when provider output is missing required structured shape."""


@dataclass(frozen=True)
class LLMUsage:
    """Token/cost diagnostics returned by provider calls."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True)
class LLMExtractionResponse:
    """Structured payload and diagnostics returned by a provider client."""

    payload: dict[str, Any]
    usage: LLMUsage | None = None
    response_id: str | None = None


class LLMClient(Protocol):
    """Minimal interface that extraction orchestrators depend on."""

    def extract_from_text(
        self,
        *,
        model: str,
        filename: str,
        text: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        """Extract structured semantic fields from text input."""

    def extract_from_file(
        self,
        *,
        model: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        """Extract structured semantic fields from direct file/image input."""
