"""Confidence scoring for extracted records."""


def calculate_confidence(record: dict) -> float:
    """Compute simple confidence as ratio of non-empty model fields."""
    if not record:
        return 0.0

    non_empty = 0
    for key, value in record.items():
        if key.startswith("_"):
            continue
        if value not in (None, ""):
            non_empty += 1

    total = sum(1 for key in record if not key.startswith("_"))
    if total == 0:
        return 0.0

    return round(non_empty / total, 4)
