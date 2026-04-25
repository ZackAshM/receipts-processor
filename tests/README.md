# tests

Purpose:
- Test coverage for core pipeline behavior and security-sensitive paths.

Contents:
- `test_cli.py`: command-line invocation behavior and argument parsing.
- `test_file_discovery.py`: supported file filtering.
- `test_schema_mapping.py`: model-column mapping behavior.
- `test_exporter.py`: export behavior and spreadsheet injection sanitization.
- `test_notes_and_flags.py`: notes ingestion and null/contradiction flagging.
- `test_runtime_logger.py`: per-user runtime logging behavior.
- `test_risk_controls_and_exceptions.py`: confidence-threshold routing and exception CSV sanitization.
