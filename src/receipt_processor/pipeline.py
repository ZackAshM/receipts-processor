"""Pipeline orchestration for receipt ingestion and export."""

from pathlib import Path

from receipt_processor.extraction.filename_inference import infer_fields_from_filename
from receipt_processor.extraction.ocr_router import extract_text
from receipt_processor.extraction.receipt_parser import parse_receipt_text
from receipt_processor.extraction.schema_mapper import map_to_model_columns
from receipt_processor.io.exporter import export_expenses
from receipt_processor.io.file_discovery import discover_receipt_files
from receipt_processor.io.template_loader import load_model_columns
from receipt_processor.quality.confidence import calculate_confidence
from receipt_processor.quality.exception_queue import build_exception_record
from receipt_processor.quality.validation import validate_expense_record


def run_pipeline(
    input_dir: Path,
    model_file: Path,
    example_file: Path,
    output_file: Path,
) -> None:
    """Extract receipt data and export records in model format."""
    model_columns = load_model_columns(model_file)
    _ = example_file

    mapped_rows = []
    for receipt_path in discover_receipt_files(input_dir):
        raw_text = extract_text(receipt_path)
        parsed = parse_receipt_text(raw_text)
        parsed.update(infer_fields_from_filename(receipt_path.name, parsed))

        record = map_to_model_columns(parsed, model_columns)
        record["_confidence"] = calculate_confidence(record)

        is_valid, errors = validate_expense_record(record)
        if not is_valid:
            mapped_rows.append(build_exception_record(receipt_path, record, errors))
            continue

        mapped_rows.append(record)

    export_expenses(mapped_rows, output_file)
