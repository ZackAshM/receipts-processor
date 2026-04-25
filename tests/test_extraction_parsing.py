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
