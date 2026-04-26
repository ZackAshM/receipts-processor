from __future__ import annotations

from pathlib import Path

from receipt_processor.extraction.ocr_router import DocumentExtraction, OCRLine
from receipt_processor.extraction.structured_extractor import extract_structured_data
from receipt_processor.processing.expense_processor import process_structured_data


def test_structured_extractor_uses_highlighted_items_as_contributing() -> None:
    document = DocumentExtraction(
        raw_text=(
            "Example Restaurant\n"
            "Bread 1.30\n"
            "Wine 69.99\n"
            "Subtotal 71.29\n"
            "Tax 3.00\n"
            "Tip 5.00\n"
            "Amount Paid 79.29\n"
            "2026-04-26\n"
        ),
        ocr_lines=[
            OCRLine(text="Bread 1.30", is_highlighted=True),
            OCRLine(text="Wine 69.99", is_highlighted=False),
        ],
        highlight_detection_available=True,
    )

    extracted = extract_structured_data(receipt_path=Path("receipt1.png"), document=document)
    processed = process_structured_data(extracted)

    assert extracted["has_highlighted_contributions"] is True
    assert extracted["contributing_items_count"] == 1
    assert extracted["noncontributing_items_count"] == 1
    assert processed["true_expense"] < processed["receipt_expense"]
    assert processed["receipt_amount_if_different"] == processed["receipt_expense"]


def test_structured_extractor_defaults_all_items_to_contributing_without_highlights() -> None:
    document = DocumentExtraction(
        raw_text=(
            "Cafe Example\n"
            "Mocha 4.50\n"
            "Bagel 3.20\n"
            "Amount Paid 7.70\n"
            "2026-04-26\n"
        ),
        ocr_lines=[
            OCRLine(text="Mocha 4.50", is_highlighted=False),
            OCRLine(text="Bagel 3.20", is_highlighted=False),
        ],
        highlight_detection_available=True,
    )

    extracted = extract_structured_data(receipt_path=Path("receipt2.png"), document=document)
    assert extracted["has_highlighted_contributions"] is False
    assert extracted["contributing_items_count"] == 2
    assert extracted["noncontributing_items_count"] == 0


def test_receipt_amount_if_different_is_empty_when_amounts_match() -> None:
    extracted = {
        "transaction_type": "Food",
        "merchant_name": "Cafe",
        "contributing_items_total": 12.34,
        "noncontributing_items_total": 0.0,
        "contributing_items_count": 1,
        "noncontributing_items_count": 0,
        "contributing_items": [{"name": "Meal", "amount": 12.34}],
        "noncontributing_items": [],
        "used_keywords": {},
        "confidence": 0.9,
        "needs_review": False,
        "amount_paid": 12.34,
        "subtotal": None,
        "tax": None,
        "tip": None,
        "service_charge": None,
        "pre_tip_total": None,
    }
    processed = process_structured_data(extracted)
    assert processed["true_expense"] == 12.34
    assert processed["receipt_expense"] == 12.34
    assert processed["receipt_amount_if_different"] is None


def test_structured_extractor_prefers_rightmost_amount_in_tax_like_lines() -> None:
    document = DocumentExtraction(
        raw_text=(
            "IN-N-OUT BURGER\n"
            "COUNTER-Take Out 13.60\n"
            "TAX 8.375% 1.14\n"
            "Amount Due $14.74\n"
            "2025-08-17\n"
        ),
        ocr_lines=[],
        highlight_detection_available=False,
    )
    extracted = extract_structured_data(receipt_path=Path("sample.pdf"), document=document)
    processed = process_structured_data(extracted)

    assert extracted["tax"] == 1.14
    assert extracted["amount_paid"] == 14.74
    assert processed["subtotal"] == 13.6
    assert processed["true_expense"] == 14.74
