#!/usr/bin/env python3
"""Redact sensitive content in CODEX_LOG-style chat transcripts."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REDACTED_PATH = "<REDACTED_PATH>"
REDACTED_SECRET = "<REDACTED_SECRET>"
REDACTED_PASSWORD = "<REDACTED_PASSWORD>"
REDACTED_EMAIL = "<REDACTED_EMAIL>"
REDACTED_BLOB = "<REDACTED_BLOB>"

PATTERN_REPLACEMENTS = [
    # Private keys and similar PEM blobs
    (
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        REDACTED_BLOB,
    ),
    # Common API key token shapes
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), REDACTED_SECRET),
    # GitHub personal and fine-grained tokens
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), REDACTED_SECRET),
    # AWS access keys
    (re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"), REDACTED_SECRET),
    # JWT-like tokens
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]{8,}\.[A-Za-z0-9._-]{8,}\b"),
        REDACTED_SECRET,
    ),
    # Bearer tokens
    (
        re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9._~+/=-]{16,})"),
        r"\1" + REDACTED_SECRET,
    ),
    # Key/value secrets
    (
        re.compile(
            r"""(?ix)
            \b(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret)\b
            \s*[:=]\s*
            (["'])?
            [^\s,"'}]+
            \2?
            """
        ),
        lambda m: f"{m.group(1)}={REDACTED_SECRET}",
    ),
    # Password assignments
    (
        re.compile(
            r"""(?ix)
            \b(password|passwd|pwd)\b
            \s*[:=]\s*
            (["'])?
            [^\s,"'}]+
            \2?
            """
        ),
        lambda m: f"{m.group(1)}={REDACTED_PASSWORD}",
    ),
    # file:// URIs
    (re.compile(r"\bfile://[^\s)\]>\"'`]+"), REDACTED_PATH),
    # macOS/Linux absolute paths in common sensitive roots
    (
        re.compile(
            r"(?<![A-Za-z0-9_.-])/(?:Users|home|private|var|etc|opt|tmp|Volumes|mnt)/[^\s)\]>\"'`]+"
        ),
        REDACTED_PATH,
    ),
    # Windows absolute paths
    (
        re.compile(r"\b[A-Za-z]:\\(?:[^\\\s]+\\)*[^\\\s)\]>\"'`]+"),
        REDACTED_PATH,
    ),
    # Email addresses
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        REDACTED_EMAIL,
    ),
]


def redact_text(text: str) -> tuple[str, int]:
    redacted = text
    replacements = 0
    for pattern, replacement in PATTERN_REPLACEMENTS:
        redacted, count = pattern.subn(replacement, redacted)
        replacements += count
    return redacted, replacements


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Redact sensitive content in a chat log. "
            "Set --lines to a positive integer; values greater than the file length "
            "effectively process the whole file."
        )
    )
    parser.add_argument(
        "--file",
        default="docs/CODEX_LOG.md",
        help="Path to the log file to redact (default: docs/CODEX_LOG.md).",
    )
    parser.add_argument(
        "--lines",
        type=int,
        required=True,
        help="Number of trailing lines to redact. Use a very large value to process the whole file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.lines <= 0:
        raise SystemExit("--lines must be a positive integer.")

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    start_idx = max(0, len(lines) - args.lines)

    prefix = "".join(lines[:start_idx])
    target = "".join(lines[start_idx:])
    redacted_target, replacements = redact_text(target)

    updated = prefix + redacted_target
    if updated != original:
        path.write_text(updated, encoding="utf-8")

    processed_scope = f"last {args.lines} lines"
    print(
        f"Redaction complete for {path}: replacements={replacements}, scope={processed_scope}, "
        f"changed={'yes' if updated != original else 'no'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
