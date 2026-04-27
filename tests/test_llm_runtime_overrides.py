from __future__ import annotations

from receipt_processor.pipeline import _resolve_llm_settings


def test_runtime_llm_overrides_default_to_environment(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LLM", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("LLM_INPUT_MODE", "text")

    settings, overrides = _resolve_llm_settings(
        enable_llm=None,
        llm_model=None,
        llm_input_mode=None,
        llm_exception_assist=None,
    )

    assert settings.enabled is False
    assert settings.model == "google/gemini-2.5-flash"
    assert settings.input_mode.value == "text"
    assert overrides == {}


def test_runtime_llm_overrides_take_precedence(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_LLM", "false")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("LLM_INPUT_MODE", "auto")
    monkeypatch.setenv("ENABLE_LLM_EXCEPTION_ASSIST", "false")

    settings, overrides = _resolve_llm_settings(
        enable_llm=True,
        llm_model="anthropic/claude-3.5-sonnet",
        llm_input_mode="file",
        llm_exception_assist=True,
    )

    assert settings.enabled is True
    assert settings.model == "anthropic/claude-3.5-sonnet"
    assert settings.input_mode.value == "file"
    assert settings.enable_exception_assist is True
    assert overrides == {
        "enable_llm": True,
        "llm_model": "anthropic/claude-3.5-sonnet",
        "llm_input_mode": "file",
        "llm_exception_assist": True,
    }
