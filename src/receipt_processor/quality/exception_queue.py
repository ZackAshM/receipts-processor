"""Build exception records for failed validations."""

from pathlib import Path


def build_exception_record(
    receipt_path: Path,
    record: dict,
    errors: list[str],
) -> dict:
    """Return enriched record for downstream manual review queue."""
    exception = dict(record)
    exception["_source_file"] = receipt_path.name
    exception["_status"] = "requires_review"
    exception["_errors"] = " | ".join(errors)
    return exception
