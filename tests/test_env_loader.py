from __future__ import annotations

import os
from pathlib import Path

from receipt_processor.config.env_loader import load_local_dotenv


def test_load_local_dotenv_reads_from_cwd(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ENABLE_LLM=true\n"
        "OPENROUTER_MODEL=anthropic/claude-3.5-sonnet\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENABLE_LLM", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    result = load_local_dotenv(override=False)

    assert result.loaded is True
    assert result.path == str(env_file)
    assert os.getenv("ENABLE_LLM") == "true"
    assert os.getenv("OPENROUTER_MODEL") == "anthropic/claude-3.5-sonnet"


def test_load_local_dotenv_does_not_override_existing_env(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENROUTER_MODEL=google/gemini-2.5-flash\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

    load_local_dotenv(override=False)

    assert os.getenv("OPENROUTER_MODEL") == "anthropic/claude-3.5-sonnet"


def test_load_local_dotenv_with_override_replaces_existing_env(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENROUTER_MODEL=google/gemini-2.5-flash\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

    load_local_dotenv(override=True)

    assert os.getenv("OPENROUTER_MODEL") == "google/gemini-2.5-flash"
