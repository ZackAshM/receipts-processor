"""Local .env loading helpers with safe override behavior."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DotenvLoadResult:
    """Result metadata for .env loading attempts."""

    path: str
    loaded: bool
    backend: str
    variables_applied: int


def _strip_wrapping_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _manual_load_dotenv(path: Path, *, override: bool) -> int:
    applied = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        # Keep quoted values intact; otherwise trim trailing inline comments.
        value = value.strip()
        if value and value[0] in {"'", '"'}:
            parsed_value = _strip_wrapping_quotes(value)
        else:
            parsed_value = value.split(" #", 1)[0].rstrip()

        if not override and key in os.environ:
            continue
        os.environ[key] = parsed_value
        applied += 1
    return applied


def load_local_dotenv(path: Path | None = None, *, override: bool = False) -> DotenvLoadResult:
    """Load `.env` from current working directory (or supplied path).

    Safe default: `override=False`, so exported OS env vars win over `.env` values.
    """
    env_path = path or (Path.cwd() / ".env")
    if not env_path.exists():
        return DotenvLoadResult(
            path=str(env_path),
            loaded=False,
            backend="none",
            variables_applied=0,
        )

    try:
        from dotenv import load_dotenv

        loaded = bool(load_dotenv(dotenv_path=env_path, override=override))
        return DotenvLoadResult(
            path=str(env_path),
            loaded=loaded,
            backend="python-dotenv",
            variables_applied=-1 if loaded else 0,
        )
    except Exception:
        # Fallback parser keeps app startup robust even if dotenv import breaks.
        applied = _manual_load_dotenv(env_path, override=override)
        return DotenvLoadResult(
            path=str(env_path),
            loaded=applied > 0,
            backend="builtin",
            variables_applied=applied,
        )
