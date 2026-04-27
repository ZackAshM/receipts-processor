from __future__ import annotations

from receipt_processor.gui import _manual_entry_became_non_empty


def test_manual_entry_transition_from_empty_selects_manual() -> None:
    assert _manual_entry_became_non_empty("", "value") is True
    assert _manual_entry_became_non_empty("   ", " value ") is True


def test_manual_entry_transition_does_not_force_manual_when_already_non_empty() -> None:
    assert _manual_entry_became_non_empty("value", "value2") is False
    assert _manual_entry_became_non_empty("value", "value") is False
    assert _manual_entry_became_non_empty("value", "   ") is False
