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
- `test_llm_config.py`: environment-driven LLM config defaults and parsing.
- `test_llm_orchestrator.py`: optional LLM success/fallback behavior and downstream validation fallback.
- `test_pipeline_llm_integration.py`: pipeline integration for LLM warning flow and LLM-to-output conversion.
- `test_llm_runtime_overrides.py`: runtime override precedence over environment defaults.
- `test_llm_review_assist.py`: conservative LLM exception-assist option-resolution gating.
- `test_env_loader.py`: automatic `.env` loading behavior and override safety.
- `test_transaction_type.py`: canonical transaction-type normalization and defaults.
