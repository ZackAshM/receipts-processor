from __future__ import annotations

from receipt_processor.llm.config import LLMInputMode, load_llm_settings


def test_llm_config_defaults_disabled(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_LLM", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("LLM_INPUT_MODE", raising=False)
    monkeypatch.delenv("ENABLE_LLM_EXCEPTION_ASSIST", raising=False)

    settings = load_llm_settings()
    assert settings.enabled is False
    assert settings.has_api_key is False
    assert settings.input_mode == LLMInputMode.auto
    assert settings.enable_exception_assist is False


def test_llm_config_parses_explicit_values(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LLM", "true")
    monkeypatch.setenv("OPENROUTER_API_KEY", "abc123")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
    monkeypatch.setenv("LLM_INPUT_MODE", "auto")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLM_MAX_INPUT_CHARS", "9000")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENROUTER_HTTP_REFERER", "https://example.app")
    monkeypatch.setenv("OPENROUTER_APP_TITLE", "ReceiptProcessor Test")
    monkeypatch.setenv("OPENROUTER_PDF_ENGINE", "mistral-ocr")
    monkeypatch.setenv("OPENROUTER_INPUT_COST_PER_1K_TOKENS", "0.005")
    monkeypatch.setenv("OPENROUTER_OUTPUT_COST_PER_1K_TOKENS", "0.015")
    monkeypatch.setenv("ENABLE_LLM_EXCEPTION_ASSIST", "true")

    settings = load_llm_settings()
    assert settings.enabled is True
    assert settings.has_api_key is True
    assert settings.model == "anthropic/claude-3.5-sonnet"
    assert settings.input_mode == LLMInputMode.auto
    assert settings.timeout_seconds == 45.0
    assert settings.max_input_chars == 9000
    assert settings.base_url == "https://openrouter.ai/api/v1"
    assert settings.app_referer == "https://example.app"
    assert settings.app_title == "ReceiptProcessor Test"
    assert settings.pdf_engine == "mistral-ocr"
    assert settings.input_cost_per_1k_tokens == 0.005
    assert settings.output_cost_per_1k_tokens == 0.015
    assert settings.enable_exception_assist is True


def test_llm_config_invalid_input_mode_falls_back_to_auto(monkeypatch) -> None:
    monkeypatch.setenv("LLM_INPUT_MODE", "invalid")
    settings = load_llm_settings()
    assert settings.input_mode == LLMInputMode.auto
