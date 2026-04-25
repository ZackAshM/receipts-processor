from receipt_processor.extraction.schema_mapper import map_to_model_columns


def test_map_to_model_columns_keeps_target_order() -> None:
    parsed = {"vendor": "Shop", "amount": "12.33", "date": "2026-04-25", "currency": "USD"}
    columns = ["date", "vendor", "amount"]

    result = map_to_model_columns(parsed, columns)

    assert list(result.keys())[:3] == ["date", "vendor", "amount"]
    assert result["date"] == "2026-04-25"
    assert "_extras" in result
