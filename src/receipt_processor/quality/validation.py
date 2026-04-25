"""Validation checks for expense records."""

REQUIRED_FIELDS = ["date", "vendor", "amount"]


def validate_expense_record(record: dict) -> tuple[bool, list[str]]:
    """Return validation state and error messages."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field in record and record.get(field) in (None, ""):
            errors.append(f"Missing required field: {field}")

    return (len(errors) == 0, errors)
