"""Map parsed fields into target model columns."""


def map_to_model_columns(parsed_fields: dict, model_columns: list[str]) -> dict:
    """Create an output record respecting model columns."""
    record = {column: parsed_fields.get(column, "") for column in model_columns}

    # Keep additional parsed fields for traceability when model has no direct column.
    extras = {
        key: value
        for key, value in parsed_fields.items()
        if key not in record and value not in (None, "")
    }
    if extras:
        record["_extras"] = str(extras)

    return record
