"""Build and export exception records for manual review."""

from __future__ import annotations

import csv

from pathlib import Path


def build_exception_record(
    receipt_path: Path,
    record: dict,
    errors: list[str],
) -> dict:
    """Return enriched record for downstream manual review queue."""
    exception = dict(record)
    exception["source_file"] = receipt_path.name
    exception["status"] = "requires_review"
    exception["errors"] = " | ".join(errors)
    return exception


def export_exception_records(exception_records: list[dict], output_file: Path) -> None:
    """Write exception records to a sidecar CSV file."""
    if not exception_records:
        return

    output_file.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for record in exception_records:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)

    with output_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(exception_records)
