# Decisions

## D-0001: Human Approval Gate Is Mandatory
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: No code or file changes are executed before explicit approval.

## D-0002: Transparent Attribution in User POV
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Repository documentation should showcase AI product management leadership.

## D-0003: Agentic Governance Artifacts
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Guardrails, risk controls, and failure playbooks improve reliability and auditability.

## D-0004: Canonical AI Product Structure
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Professional structure improves maintainability and portfolio quality.

## D-0005: Codex Log Maintenance Protocol
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Every user prompt and Codex response should be captured in `docs/CODEX_LOG.md` using the established date-time heading format.

## D-0006: Append-Only, One-Response-Lag Logging
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: To avoid full-file rewrites and platform timing limits, `docs/CODEX_LOG.md` should be maintained by appending only missing exchanges, using one-response-lag updates when necessary.

## D-0007: Halt-Until-Resume Control
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Project implementation work must pause on explicit halt instructions and resume only after explicit user authorization.

## D-0008: Sensitive Data Redaction in Chat Logs
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: `docs/CODEX_LOG.md` must redact sensitive content (such as absolute filepaths and credentials) while preserving useful conversational traceability.

## D-0009: Git Authority Separation
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Git authority is split to keep developer control over push operations and untracked staging, while allowing Codex to commit only when explicitly requested.

## D-0010: Notes Context and Anomaly Flagging (Non-LLM)
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: The pipeline should support optional notes context and reliably flag null-result and contradiction cases without requiring an LLM API in the baseline branch.

## D-0011: Per-User Structured Performance Logging
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Runtime JSONL telemetry per user improves app performance evaluation and debugging while keeping logs local and operationally focused.

## D-0012: Exception Export Sanitization Parity
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Exception CSV exports must apply spreadsheet-safety sanitization equivalent to main exports to prevent formula injection from untrusted values.

## D-0013: Enforced Risk Controls at Runtime
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Confidence thresholds defined in `configs/risk_controls.yaml` must be enforced in pipeline routing so low-confidence records are queued for review.

## D-0014: Direct Positional CLI Entry
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: End users should be able to run the app as `receipts_processor <receipts_folder>` with optional flags for model/output/log/risk controls.

## D-0015: Output Defaults to Input Folder
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: When `--output-file` is not provided, placing `Expenses.csv` in the input receipts folder improves default UX and reduces required CLI arguments.

## D-0016: Output Type CLI Flag
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Users should be able to choose output format via `--output-type` (`csv` default, `xlsx` optional) without always specifying a full output filename.

## D-0017: Desktop GUI Surface
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Add a GUI in addition to CLI so users can select receipt folders via OS picker and access less common options from an Advanced panel.

## D-0018: Strict Template Token Enforcement
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Unknown `{{keyword}}` or `<operation>` template tokens must fail the run instead of silently exporting blank values.

## D-0019: Configuration Surface Clarity
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Only runtime-wired configs should be documented as active; non-wired config files must be clearly marked as reserved/reference.

## D-0020: Redaction Policy Enforcement in CODEX_LOG
- Status: Accepted
- Requested by: User
- Implemented by: Codex
- Rationale: Chat logs must not contain sensitive absolute paths, and CI should fail when unredacted absolute paths are detected.
