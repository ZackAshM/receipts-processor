from receipt_processor.extraction.filename_inference import infer_fields_from_filename
from receipt_processor.extraction.receipt_parser import parse_receipt_text


def test_parse_receipt_text_extracts_core_fields() -> None:
    text = """
    Lyft
    Trip Receipt
    Date: 06/25/2025
    Total $54.91
    """

    parsed = parse_receipt_text(text)

    assert parsed["vendor"] == "Lyft"
    assert parsed["date"] == "2025-06-25"
    assert parsed["amount"] == "54.91"
    assert parsed["description"] == "Transportation - Lyft"


def test_filename_inference_extracts_date_amount_vendor() -> None:
    inferred = infer_fields_from_filename(
        "2025-06-24_taqueria_san_luis_19.23.png",
        current_fields={},
    )

    assert inferred["date"] == "2025-06-24"
    assert inferred["amount"] == "19.23"
    assert inferred["vendor"] == "taqueria san luis"


def test_filename_inference_supports_compact_yyyymmdd_date() -> None:
    inferred = infer_fields_from_filename(
        "20250818-Food-GreatBasinBakery.pdf",
        current_fields={},
    )
    assert inferred["date"] == "2025-08-18"


def test_parse_receipt_text_supports_single_digit_month_day_dates() -> None:
    text = """
    GREAT BASIN BAKERY
    Ordered: 8/18/25 9:24 AM
    Total $22.12
    """
    parsed = parse_receipt_text(text)
    assert parsed["date"] == "2025-08-18"
