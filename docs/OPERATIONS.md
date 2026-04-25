# Operations

## Operator Runbook

1. Activate virtual environment.
2. Place source receipts in `data/inbox`.
3. Choose `models/model.csv` or `models/model.xlsx`.
4. Run CLI command to generate output file.
5. Review low-confidence and exception records.

## Human-in-the-Loop Controls

- No autonomous scope expansion without explicit approval.
- Exceptions must be reviewed before financial posting.
- Changes to extraction logic should update `docs/DECISIONS.md`.

## Recovery Steps

- If parsing quality degrades, inspect `data/output` and exception metadata.
- Validate model headers before each run.
- Keep original receipts unchanged in source folders.
