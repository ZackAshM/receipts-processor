"""Sanitization helpers for LLM context payloads."""

from __future__ import annotations

import re

AMOUNT_RE = re.compile(r"(?<!\w)[+-]?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})\b|(?<!\w)[+-]?\$?\d+\.\d{2}\b")
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"\d{1,2}[A-Za-z]{3}\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
    re.IGNORECASE,
)
TRANSACTION_HINT_RE = re.compile(
    r"\b(?:purchase|debit|credit|payment|refund|charge|pos|ach|transfer|withdrawal|deposit|"
    r"merchant|store|airlines?|hotel|uber|lyft|taxi|restaurant|cafe|fuel|grocery|statement activity)\b",
    re.IGNORECASE,
)
NON_TRANSACTION_HINT_RE = re.compile(
    r"\b(?:account number|acct\.?\s*#?|routing number|iban|swift|customer service|available balance|"
    r"ending balance|beginning balance|credit limit|minimum payment|payment due|apr|interest charge|"
    r"statement period|address|phone|email|rewards summary)\b",
    re.IGNORECASE,
)
CARD_NUMBER_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
LONG_ID_RE = re.compile(r"\b\d{8,17}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b")


def _normalize_line(value: str) -> str:
    return " ".join(value.strip().split())


def _looks_like_transaction_line(line: str) -> bool:
    if NON_TRANSACTION_HINT_RE.search(line):
        return False
    has_amount = bool(AMOUNT_RE.search(line))
    has_date = bool(DATE_RE.search(line))
    has_hint = bool(TRANSACTION_HINT_RE.search(line))
    return has_amount and (has_date or has_hint)


def _redact_sensitive_tokens(line: str) -> str:
    redacted = line
    redacted = EMAIL_RE.sub("<REDACTED_EMAIL>", redacted)
    redacted = PHONE_RE.sub("<REDACTED_PHONE>", redacted)
    redacted = CARD_NUMBER_RE.sub("<REDACTED_CARD>", redacted)
    redacted = LONG_ID_RE.sub("<REDACTED_ID>", redacted)
    return redacted


def sanitize_statement_text(raw_text: str, *, max_chars: int = 2200) -> str:
    """Keep likely transaction lines and redact sensitive non-transaction identifiers."""
    if not raw_text:
        return ""

    kept_lines: list[str] = []
    seen: set[str] = set()
    for raw_line in raw_text.splitlines():
        line = _normalize_line(raw_line)
        if not line:
            continue
        if not _looks_like_transaction_line(line):
            continue
        sanitized = _redact_sensitive_tokens(line)
        if not sanitized or sanitized in seen:
            continue
        seen.add(sanitized)
        kept_lines.append(sanitized)

    if not kept_lines:
        return ""
    compact = "\n".join(kept_lines)
    return compact[: max(200, int(max_chars))]
