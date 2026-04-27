#!/usr/bin/env python3
"""Interactive first-run setup for ReceiptProcessor.

Goal: after cloning the repo, run this script once and be ready to run the app.
"""

from __future__ import annotations

import getpass
import re
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 11)


def _print_step(message: str) -> None:
    print(f"\n==> {message}")


def _run(cmd: list[str], *, cwd: Path) -> None:
    pretty = " ".join(cmd)
    print(f"$ {pretty}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _prompt_yes_no(question: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{question} {suffix} ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _prompt_text(question: str, *, default: str) -> str:
    raw = input(f"{question} [{default}] ").strip()
    return raw or default


def _venv_python_path(venv_dir: Path) -> Path:
    if sys.platform.startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _ensure_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        expected = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        found = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        raise SystemExit(f"Python {expected}+ is required. Found: {found}")


def _ensure_env_file(repo_root: Path) -> Path:
    env_path = repo_root / ".env"
    example_path = repo_root / ".env.example"
    if not example_path.exists():
        raise SystemExit("Missing .env.example. Cannot continue setup.")
    if not env_path.exists():
        shutil.copyfile(example_path, env_path)
        print("Created .env from .env.example")
    else:
        print("Using existing .env")
    return env_path


def _parse_dotenv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
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
        value = value.strip()
        if value and value[0] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            result[key] = value
    return result


def _format_dotenv_value(value: str) -> str:
    if not value:
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _set_dotenv_key(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(key)}\s*=")
    replacement = f"{key}={_format_dotenv_value(value)}"

    replaced = False
    for index, line in enumerate(lines):
        if pattern.match(line):
            lines[index] = replacement
            replaced = True
            break

    if not replaced:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(replacement)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ensure_runtime_directories(repo_root: Path) -> None:
    for relative in ("data/inbox", "data/output", "logs"):
        target = repo_root / relative
        target.mkdir(parents=True, exist_ok=True)


def _check_tkinter(venv_python: Path, repo_root: Path) -> bool:
    result = subprocess.run(
        [str(venv_python), "-c", "import tkinter"],
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _print_next_steps(*, repo_root: Path, tkinter_ok: bool) -> None:
    activate = "source .venv/bin/activate"
    if sys.platform.startswith("win"):
        activate = ".venv\\Scripts\\activate"

    _print_step("Setup complete")
    print("Next commands:")
    print(f"  cd {repo_root}")
    print(f"  {activate}")
    print("  receipts_processor data/inbox")
    if tkinter_ok:
        print("  receipts_processor_gui")
    else:
        print("  # GUI warning: tkinter not detected in this Python build")
        print("  # CLI is fully supported: receipts_processor data/inbox")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    _ensure_python_version()

    _print_step("ReceiptProcessor setup starting")
    print(f"Repository root: {repo_root}")

    venv_dir = repo_root / ".venv"
    if not venv_dir.exists():
        _print_step("Creating virtual environment")
        _run([sys.executable, "-m", "venv", ".venv"], cwd=repo_root)
    else:
        print("\n==> Virtual environment already exists (.venv)")

    venv_python = _venv_python_path(venv_dir)
    if not venv_python.exists():
        raise SystemExit(f"Virtual environment python not found: {venv_python}")

    _print_step("Installing dependencies")
    _run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo_root)
    _run([str(venv_python), "-m", "pip", "install", "-r", "requirements.lock.txt"], cwd=repo_root)
    _run([str(venv_python), "-m", "pip", "install", "-e", "."], cwd=repo_root)

    _print_step("Configuring .env")
    env_path = _ensure_env_file(repo_root)
    env_values = _parse_dotenv(env_path)

    current_enable_llm = env_values.get("ENABLE_LLM", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    enable_llm = _prompt_yes_no("Enable LLM support for data extraction?", default=current_enable_llm)
    _set_dotenv_key(env_path, "ENABLE_LLM", "true" if enable_llm else "false")

    if enable_llm:
        current_model = env_values.get("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"
        selected_model = _prompt_text("OpenRouter model to use?", default=current_model)
        _set_dotenv_key(env_path, "OPENROUTER_MODEL", selected_model)

        set_key_now = _prompt_yes_no("Enter OPENROUTER_API_KEY now?", default=False)
        if set_key_now:
            api_key = getpass.getpass("OPENROUTER_API_KEY: ").strip()
            if api_key:
                _set_dotenv_key(env_path, "OPENROUTER_API_KEY", api_key)
            else:
                print("No API key entered. Existing value kept.")
        else:
            print("Skipping API key prompt. Existing OPENROUTER_API_KEY value kept.")

    _print_step("Ensuring runtime directories")
    _ensure_runtime_directories(repo_root)

    _print_step("Checking tkinter support")
    tkinter_ok = _check_tkinter(venv_python, repo_root)
    if not tkinter_ok:
        print(
            "WARNING: tkinter support was not detected in this Python environment. "
            "The GUI may not work properly. CLI usage remains fully supported."
        )
    else:
        print("tkinter support detected.")

    _print_next_steps(repo_root=repo_root, tkinter_ok=tkinter_ok)


if __name__ == "__main__":
    main()
