# Operations

## Operator Runbook

1. Activate virtual environment.
2. Place source receipts in `data/inbox`.
3. Optionally add contextual notes files (`notes.txt`, `<receipt>_notes.txt`) in the same folder.
4. Choose `models/model.csv` or `models/model.xlsx`.
5. Run CLI command to generate output file.
6. Review low-confidence rows and the sidecar exception file (`*_exceptions.csv`) for null/contradiction flags.
7. Review runtime logs under `logs/users/<user_id>/performance-YYYY-MM-DD.jsonl` for performance/debug diagnostics.

## Security Controls in Runtime

- Export sanitization neutralizes spreadsheet formula prefixes (`=`, `+`, `-`, `@`, tab, carriage return).
- Chat logs and governance artifacts use redaction rules for sensitive values.
- Do not place credentials in filenames, receipt images, or prompt text.
- Runtime logs intentionally avoid raw receipt text and focus on operational metadata.

## Human-in-the-Loop Controls

- No autonomous scope expansion without explicit approval.
- Exceptions must be reviewed before financial posting.
- Changes to extraction logic should update `docs/DECISIONS.md`.

## Recovery Steps

- If parsing quality degrades, inspect `data/output` and exception metadata.
- Validate model headers before each run.
- Keep original receipts unchanged in source folders.
