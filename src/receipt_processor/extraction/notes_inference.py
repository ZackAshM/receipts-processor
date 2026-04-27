"""Parse optional notes files for supplemental extraction hints."""

from __future__ import annotations

from pathlib import Path
import re

from receipt_processor.extraction.receipt_parser import parse_receipt_text
from receipt_processor.extraction.transaction_type import normalize_transaction_type

NOTE_NAME_TOKENS = ("note", "notes", "memo", "context")
IGNORED_FUZZY_TOKENS = set(NOTE_NAME_TOKENS) | {"receipt", "img", "image", "scan", "screenshot"}

FIELD_ALIASES = {
    "date": "date",
    "transaction_date": "date",
    "receipt_date": "date",
    "vendor": "vendor",
    "merchant": "vendor",
    "store": "vendor",
    "payee": "vendor",
    "amount": "amount",
    "total": "amount",
    "receipt_amount": "receipt_amount",
    "claimed_amount": "amount",
    "expense_type": "expense_type",
    "type": "expense_type",
    "category": "expense_type",
    "description": "description",
    "desc": "description",
}


def _candidate_note_files(input_dir: Path, receipt_path: Path) -> list[Path]:
    stem = receipt_path.stem
    explicit_candidates = [
        input_dir / "notes.txt",
        input_dir / "note.txt",
        input_dir / f"{stem}.txt",
        input_dir / f"{stem}_notes.txt",
        input_dir / f"{stem}-notes.txt",
        input_dir / f"{stem}.notes.txt",
    ]

    def token_set(text: str) -> set[str]:
        return {
            token
            for token in re.split(r"[^a-z0-9]+", text.lower())
            if len(token) >= 3 and token not in IGNORED_FUZZY_TOKENS
        }

    receipt_tokens = token_set(stem)
    fuzzy_candidates: list[Path] = []
    for path in input_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".txt":
            continue
        if not any(token in path.stem.lower() for token in NOTE_NAME_TOKENS):
            continue
        note_tokens = token_set(path.stem)
        if not receipt_tokens.intersection(note_tokens):
            continue
        fuzzy_candidates.append(path)

    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in explicit_candidates + fuzzy_candidates:
        if not path.exists():
            continue
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def _parse_key_value_lines(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key_raw, value_raw = line.split(":", 1)
        key = key_raw.strip().lower().replace(" ", "_")
        value = value_raw.strip()
        if not key or not value:
            continue
        mapped = FIELD_ALIASES.get(key)
        if not mapped:
            continue
        parsed[mapped] = value
    return parsed


def collect_note_context(input_dir: Path, receipt_path: Path) -> list[tuple[str, str]]:
    """Return note filename/text pairs relevant to the receipt."""
    entries: list[tuple[str, str]] = []
    for note_path in _candidate_note_files(input_dir, receipt_path):
        try:
            text = note_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not text.strip():
            continue
        entries.append((note_path.name, text))
    return entries


def infer_fields_from_notes(
    input_dir: Path,
    receipt_path: Path,
    note_context: list[tuple[str, str]] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Return inferred fields and matched note filenames for a receipt."""
    fields: dict[str, str] = {}
    matched_files: list[str] = []

    entries = note_context if note_context is not None else collect_note_context(input_dir, receipt_path)
    for note_name, text in entries:
        matched_files.append(note_name)
        explicit_fields = _parse_key_value_lines(text)
        heuristic_fields = parse_receipt_text(text)
        combined_fields: dict[str, str] = dict(explicit_fields)

        # Use heuristic fields only when explicit notes do not already provide a value.
        for key, value in heuristic_fields.items():
            if value and key not in combined_fields:
                combined_fields[key] = value

        # If notes explicitly provide vendor, ensure description reflects that vendor.
        if explicit_fields.get("vendor") and not explicit_fields.get("description"):
            expense_type = normalize_transaction_type(combined_fields.get("expense_type", "Misc"))
            combined_fields["description"] = f"{expense_type} - {explicit_fields['vendor']}"

        for key, value in combined_fields.items():
            if not value:
                continue
            if key in explicit_fields:
                fields[key] = value
                continue
            if key not in fields:
                fields[key] = value

    return fields, matched_files
