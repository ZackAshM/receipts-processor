"""Convert raw receipt text into normalized expense fields."""

from __future__ import annotations

import re
from datetime import datetime

from receipt_processor.extraction.transaction_type import normalize_transaction_type

AMOUNT_RE = re.compile(r"(?:USD|\$)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})")

DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b"), "%Y-%m-%d"),
    (re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b"), "%m-%d-%Y"),
    (re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2})\b"), "%m-%d-%y"),
    (
        re.compile(
            r"\b("
            r"Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|"
            r"Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December"
            r")\s+(\d{1,2}),?\s+(\d{4})\b",
            re.IGNORECASE,
        ),
        "%b %d %Y",
    ),
]

TOTAL_PRIORITY = [
    "grand total",
    "amount due",
    "total due",
    "balance due",
    "total",
]
IGNORE_VENDOR_TOKENS = {
    "receipt",
    "invoice",
    "thank you",
    "www",
    "tel",
    "phone",
    "card",
    "visa",
    "mastercard",
    "subtotal",
    "tax",
    "total",
    "amount",
    "guest number",
    "cashier",
    "check",
    "server",
    "ordered",
    "transaction",
    "authorization",
    "approval",
    "terminal",
    "payment",
    "input type",
    "cardholder",
    "powered by",
    "auth",
}


def _clean_lines(raw_text: str) -> list[str]:
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _to_decimal_string(value: str) -> str:
    normalized = value.replace(",", "")
    amount = float(normalized)
    return f"{amount:.2f}"


def _extract_amount(lines: list[str]) -> str:
    lowered = [line.lower() for line in lines]
    for keyword in TOTAL_PRIORITY:
        for idx, line in enumerate(lowered):
            if keyword in line and "subtotal" not in line:
                amounts = AMOUNT_RE.findall(lines[idx])
                if amounts:
                    return _to_decimal_string(amounts[-1])

    all_amounts: list[float] = []
    for line in lines:
        for amount_text in AMOUNT_RE.findall(line):
            try:
                all_amounts.append(float(amount_text.replace(",", "")))
            except ValueError:
                continue

    if not all_amounts:
        return ""
    return f"{max(all_amounts):.2f}"


def _safe_parse_datetime(text: str, fmt: str) -> datetime | None:
    try:
        return datetime.strptime(text, fmt)
    except ValueError:
        return None


def _extract_date(raw_text: str) -> str:
    for pattern, fmt in DATE_PATTERNS:
        match = pattern.search(raw_text)
        if not match:
            continue

        if fmt == "%b %d %Y":
            month = match.group(1)[:3].title()
            day = f"{int(match.group(2)):02d}"
            year = match.group(3)
            parsed = _safe_parse_datetime(f"{month} {day} {year}", fmt)
        elif fmt == "%Y-%m-%d":
            parts = [group for group in match.groups()]
            parsed = _safe_parse_datetime("-".join(parts), fmt)
        elif fmt in {"%m-%d-%Y", "%m-%d-%y"}:
            month = f"{int(match.group(1)):02d}"
            day = f"{int(match.group(2)):02d}"
            year = match.group(3)
            parsed = _safe_parse_datetime(f"{month}-{day}-{year}", fmt)
        else:
            parsed = None

        if parsed:
            return parsed.strftime("%Y-%m-%d")

    return ""


def _extract_vendor(lines: list[str]) -> str:
    for line in lines[:8]:
        lowered = line.lower()
        if any(token in lowered for token in IGNORE_VENDOR_TOKENS):
            continue
        if sum(ch.isalpha() for ch in line) < 3:
            continue
        if len(line) > 80:
            continue
        return re.sub(r"\s+", " ", line).strip(" -")
    return ""


def _infer_expense_type(vendor: str, raw_text: str) -> str:
    return normalize_transaction_type("", context_text=f"{vendor} {raw_text}", default="")


def parse_receipt_text(raw_text: str) -> dict[str, str]:
    """Parse receipt text into normalized canonical fields."""
    if not raw_text.strip():
        return {}

    lines = _clean_lines(raw_text)
    if not lines:
        return {}

    vendor = _extract_vendor(lines)
    date_value = _extract_date(raw_text)
    amount_value = _extract_amount(lines)
    expense_type = _infer_expense_type(vendor, raw_text)

    parsed: dict[str, str] = {}
    if vendor:
        parsed["vendor"] = vendor
    if date_value:
        parsed["date"] = date_value
    if amount_value:
        parsed["amount"] = amount_value
    if expense_type:
        parsed["expense_type"] = expense_type
    if vendor:
        parsed["description"] = f"{expense_type} - {vendor}"

    return parsed
