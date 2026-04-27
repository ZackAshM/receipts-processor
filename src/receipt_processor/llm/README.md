# src/receipt_processor/llm

Purpose:
- Optional LLM-based semantic extraction that augments (but never replaces) deterministic reliability guarantees.

Contents:
- `config.py`: environment-driven settings (`ENABLE_LLM`, `ENABLE_LLM_EXCEPTION_ASSIST`, `OPENROUTER_*`, `LLM_INPUT_MODE`).
- `client_base.py`: provider-agnostic client protocol and LLM-specific exceptions.
- `openrouter_client.py`: isolated OpenRouter HTTP client wrapper.
- `schema.py`: strict normalization/validation of LLM JSON into the app's extraction schema.
- `extractor.py`: input-mode routing (`text`, `file`, `auto`), OCR-aware text preparation, and provider call execution.
- `orchestrator.py`: clean extraction interface used by the pipeline, including deterministic fallback on any LLM failure.
- `review_assist.py`: optional conservative LLM-first exception-resolution helper for obvious contradiction/low-confidence choices.

Behavior:
- Default mode is deterministic only (`ENABLE_LLM=false`).
- CLI and GUI auto-load a local `.env` file from the current working directory.
- Environment settings are defaults and can be overridden per run via CLI/GUI runtime flags.
- When enabled, OpenRouter extraction attempts semantic field capture (merchant/date/type/amount candidates, line-item candidates).
- In `auto` mode, direct file input is attempted first for image/PDF files, then falls back to local OCR/text extraction mode when needed.
- LLM request context includes filename hints, matched notes text, and detected statement excerpts from the input folder.
- Prompting is tuned for app intent: semantic candidate extraction only, fixed transaction-type choices (`Food`, `Transportation`, `Lodging`, `Misc`), and no derived business-rule arithmetic.
- Optional review assist is intentionally modest: it can only select from explicit review options; if it abstains (not obvious) or returns invalid/ambiguous output, user review remains in control.
- Provider calls include transient-error retries (e.g., 429/5xx/timeouts) to improve stability.
- Final arithmetic/business rules remain deterministic in processing modules.
- Any LLM issue (missing key, timeout, API error, invalid structured output, unsupported direct file mode, downstream validation failure) triggers deterministic fallback.
- Fallbacks are logged as warnings without exposing credentials.
