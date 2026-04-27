from __future__ import annotations

from receipt_processor.llm.context_sanitizer import sanitize_statement_text


def test_sanitize_statement_text_keeps_transaction_lines_only() -> None:
    raw = """
    Statement period: 01/01/2026 - 01/31/2026
    Account Number: 1234 5678 9012 3456
    01/12/2026 UBER TRIP $15.23
    01/13/2026 PAYMENT RECEIVED $-25.00
    Credit limit: $5000.00
    """

    sanitized = sanitize_statement_text(raw)

    assert "UBER TRIP" in sanitized
    assert "PAYMENT RECEIVED" in sanitized
    assert "Account Number" not in sanitized
    assert "Credit limit" not in sanitized


def test_sanitize_statement_text_redacts_sensitive_tokens_in_kept_lines() -> None:
    raw = "01/12/2026 STORE PURCHASE $15.23 card 4111 1111 1111 1111 john@example.com 555-111-2222"

    sanitized = sanitize_statement_text(raw)

    assert "<REDACTED_CARD>" in sanitized
    assert "<REDACTED_EMAIL>" in sanitized
    assert "<REDACTED_PHONE>" in sanitized
    assert "4111" not in sanitized
    assert "john@example.com" not in sanitized


def test_sanitize_statement_text_returns_empty_when_no_transaction_lines() -> None:
    raw = """
    Statement period: 01/01/2026 - 01/31/2026
    Minimum payment due: $25.00
    Customer service: 800-555-1212
    """

    assert sanitize_statement_text(raw) == ""


def test_sanitize_statement_text_respects_max_chars() -> None:
    raw = "\n".join(
        [f"01/{day:02d}/2026 STORE PURCHASE ${day}.00" for day in range(1, 25)]
    )

    sanitized = sanitize_statement_text(raw, max_chars=220)

    assert len(sanitized) <= 220
