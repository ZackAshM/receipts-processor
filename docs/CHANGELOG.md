# Changelog

## 2026-04-26

### Added
- Enforced strict template token behavior: unknown `{{...}}` and `<...>` tokens now fail the run before export.
- Added regression tests for unknown keyword and unknown operation token failures.
- Added `requirements.lock.txt` for pinned/reproducible installs.
- Added SBOM generation/upload in security CI workflow (`sbom.cdx.json` artifact).
- Added CI guard to fail if `docs/CODEX_LOG.md` contains unredacted absolute paths.
- Added optional LLM extraction package (`src/receipt_processor/llm/`) with provider wrapper, schema normalization, and orchestration.
- Added environment-based LLM config in `.env.example` (`ENABLE_LLM`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `LLM_INPUT_MODE`).
- Added fallback/diagnostic tests for LLM disabled, success, provider failure, invalid structured output, unsupported file mode, and downstream validation fallback.
- Added pipeline integration tests for LLM fallback warnings and LLM-to-downstream conversion.
- Added OpenRouter-first client implementation with direct image/PDF file-input support.
- Added runtime LLM override controls in CLI (`--enable-llm/--disable-llm`, `--llm-model`, `--llm-input-mode`) and GUI Advanced options.
- Added tests for LLM runtime override precedence over environment defaults.
- Added automatic `.env` loading for CLI/GUI startup with safe precedence (`override=False` behavior).
- Added environment-loader module and tests for non-overwrite/overwrite behavior.
- Added canonical transaction-type normalization (`Food`, `Transportation`, `Lodging`, `Misc`) with dedicated tests.
- Added richer LLM context assembly (filename + notes + statement excerpts) for semantic extraction requests.
- Added prompt refinements for app-intent extraction and fixed transaction-type choice constraints.
- Added optional conservative LLM exception assist (`ENABLE_LLM_EXCEPTION_ASSIST`) for contradiction/low-confidence review pre-resolution.
- Added CLI/GUI runtime override controls for LLM exception assist.
- Added tests for LLM exception-assist resolution gating and pipeline integration.
- Added run-start mode/status reporting callbacks and per-receipt progress events (`<filename> [x% / 100%]`) surfaced in CLI/GUI.
- Added LLM stability hardening: transient provider retries and run-level circuit-breaker fallback to deterministic mode after repeated provider failures.
- Added safeguard to skip LLM exception assist on receipts where LLM extraction already failed for provider/API reasons.
- Added parser hardening for varied OpenRouter response shapes (including tool-call arguments and fenced JSON extraction).

### Changed
- Updated architecture and quality docs to reflect current template-driven runtime checks (and optional/non-gating validation module status).
- Updated configuration docs to clearly distinguish active runtime config (`risk_controls.yaml`) from reserved/reference stubs (`app.yaml`, `extraction_rules.yaml`).
- Updated root README to remove stale `template/` reference and clarify model/config descriptions.
- Redacted existing absolute filepaths from `docs/CODEX_LOG.md` to align with governance policy.
- Removed committed build artifacts under `src/receipt_processor.egg-info/`.
- Added `.gitignore` rule for `*.egg-info/`.
- Updated pipeline extraction flow to use a single optional LLM extraction interface with guaranteed deterministic fallback on any LLM failure.
- Switched optional LLM provider configuration from OpenAI-style env vars to OpenRouter env vars.
- Updated LLM mode behavior so `auto` defaults to direct file mode (image/PDF) with automatic text-mode fallback when file-mode capability is unavailable.
- Added OCR-aware text sufficiency checks before text-mode LLM extraction retries.
- Updated CLI/GUI warning output to surface when LLM fallback is used.
- Updated pipeline run configuration to apply per-run LLM overrides over environment defaults.
- Updated documentation to clarify that `.env` is auto-loaded from current working directory.
- Updated extraction flow so unknown transaction type remains blank during early review gating and resolves to canonical `Misc` in processing.
- Updated observability docs to describe extraction strategy and LLM diagnostics logging.
- Updated pipeline review flow so LLM exception assist only auto-applies explicit option-based resolutions, otherwise falls back to user review.
- Updated LLM exception assist behavior to remove fixed confidence-threshold gating; assist now resolves only by explicit option selection and abstains/falls back to user review when not obvious.

## 2026-04-25

### Added
- Created initial repository scaffold for ReceiptProcessor.
- Initialized `.venv` for isolated project runtime.
- Added package layout under `src/receipt_processor`.
- Added starter configs, tests, and data folders.
- Added product docs (`PRD`, `ARCHITECTURE`, `DECISIONS`, `OPERATIONS`).
- Added agent governance docs under `agent/`.
- Added `docs/CODEX_LOG.md` workflow integration and preserved `docs/INIT_PROMPT.txt`.

### User-Requested Adjustments
- Included and preserved `docs/INIT_PROMPT.txt` as a static initialization artifact.
- Continued `docs/CODEX_LOG.md` using the heading-and-response format the user established.
- Updated logging policy to append-only maintenance with one-response-lag updates.
- Added explicit halt-until-resume control to governance documentation.
- Redacted sensitive data in `docs/CODEX_LOG.md` (including absolute filepaths) and codified ongoing log sanitization rules.
- Added git authority guardrails: developer-only `git push`, developer-only staging of untracked files/directories, and commit creation by Codex only on explicit developer request.
- Implemented core extraction pipeline content: PDF/image text extraction, rule-based parsing, filename fallback inference, and model/example-driven schema mapping.
- Implemented spreadsheet formula-injection defenses at export time.
- Added subfolder `README.md` files to document purpose and contents across major project areas.
- Added optional notes-file ingestion (`notes.txt`, receipt-specific notes names) for extraction enrichment.
- Added null-result flagging and contradiction detection between file text, filename inference, and notes context.
- Added sidecar exception export (`*_exceptions.csv`) for flagged records.
- Added structured runtime logging in JSONL format for performance evaluation and debugging.
- Added spreadsheet sanitization for exception sidecar CSV exports.
- Enforced low-confidence routing using loaded runtime thresholds from `configs/risk_controls.yaml`.
- Added optional log privacy mode to mask file identifiers in telemetry.
- Updated runtime logging layout to write directly under `logs/` and removed `user_id` from emitted telemetry events.
- Added GitHub Actions workflows for automated CI tests and dependency vulnerability scanning.
- Added deterministic structured extraction and processing modules, including highlight-aware contribution logic for OCR image lines.
- Added model-template rendering support for `{{keyword}}` placeholders and `<operation>` summary tokens.
- Added run-level detailed sidecar export (`*_detailed.json`) containing per-receipt extracted + processed data and summary totals.
- Updated CLI UX to support direct positional invocation (`receipts_processor <input_dir>`) with optional flags.
- Changed CLI default output location to `<input_dir>/Expenses.csv` when `--output-file` is omitted.
- Added `--output-type` (`csv` default, optional `xlsx`) for output format selection.
- Added desktop GUI entrypoint with folder picker and Advanced options panel (`receipts_processor_gui`).
- Added graceful GUI startup handling for environments without `tkinter` (clear fallback guidance).

### Attribution
- Direction and requirements defined by user.
- Scaffold and implementation executed by Codex after user approval.
