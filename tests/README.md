# tests

Purpose:
- Test coverage for core pipeline behavior and security-sensitive paths.

Contents:
- `test_cli.py`: command-line invocation behavior and argument parsing.
- `test_interface_options.py`: shared output path/type resolution rules.
- `test_file_discovery.py`: supported file filtering.
- `test_schema_mapping.py`: model-column mapping behavior.
- `test_exporter.py`: export behavior and spreadsheet injection sanitization.
- `test_notes_and_flags.py`: notes ingestion and null/contradiction flagging.
- `test_runtime_logger.py`: runtime logging behavior and privacy-mode redaction.
- `test_risk_controls_and_exceptions.py`: confidence-threshold routing and exception CSV sanitization.
- `test_template_renderer.py`: model-template keyword and operation rendering behavior.
- `test_structured_extraction_and_processing.py`: deterministic structured extraction and processing rules.
- `test_detailed_json_output.py`: run-level detailed JSON sidecar emission.
