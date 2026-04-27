from __future__ import annotations

from receipt_processor.extraction.transaction_type import normalize_transaction_type


def test_transaction_type_normalizes_known_values() -> None:
    assert normalize_transaction_type("food") == "Food"
    assert normalize_transaction_type("Transportation") == "Transportation"
    assert normalize_transaction_type("lodging") == "Lodging"
    assert normalize_transaction_type("other") == "Misc"


def test_transaction_type_uses_context_hints() -> None:
    assert normalize_transaction_type("", context_text="Uber trip downtown") == "Transportation"
    assert normalize_transaction_type("", context_text="Hotel invoice #123") == "Lodging"
    assert normalize_transaction_type("", context_text="Coffee shop receipt") == "Food"


def test_transaction_type_defaults_to_misc() -> None:
    assert normalize_transaction_type("") == "Misc"
    assert normalize_transaction_type("UnknownCategory") == "Misc"
