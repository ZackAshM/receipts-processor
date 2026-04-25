# Operations

## Operator Runbook

1. Activate virtual environment.
2. Place source receipts in `data/inbox`.
3. Optionally add contextual notes files (`notes.txt`, `<receipt>_notes.txt`) in the same folder.
4. Choose `models/model.csv` or `models/model.xlsx`.
5. Run CLI command to generate output file.
6. Review low-confidence rows and the sidecar exception file (`*_exceptions.csv`) for null/contradiction flags.

## Security Controls in Runtime

- Export sanitization neutralizes spreadsheet formula prefixes (`=`, `+`, `-`, `@`, tab, carriage return).
- Chat logs and governance artifacts use redaction rules for sensitive values.
- Do not place credentials in filenames, receipt images, or prompt text.

## Human-in-the-Loop Controls

- No autonomous scope expansion without explicit approval.
- Exceptions must be reviewed before financial posting.
- Changes to extraction logic should update `docs/DECISIONS.md`.

## Recovery Steps

- If parsing quality degrades, inspect `data/output` and exception metadata.
- Validate model headers before each run.
- Keep original receipts unchanged in source folders.
