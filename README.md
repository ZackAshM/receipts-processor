# ReceiptProcessor

I used Codex to build ReceiptProcessor from scratch as an AI product management showcase. I defined the product goals, architecture direction, collaboration rules, and governance constraints while using Codex as an execution partner.

## Product Goal

I am building a receipt-to-expense pipeline that:
- Scans a target folder for receipt files (`.pdf`, `.jpeg`, `.jpg`, `.png`).
- Extracts expense data from mixed receipt types (paper scans, screenshots, printed emails).
- Uses filename hints when receipt content is incomplete.
- Produces `Expenses.xlsx` or `Expenses.csv` matching a provided model template.

## Current Capabilities

- PDF text extraction via `pypdf`.
- Image OCR via `pytesseract` + `Pillow`.
- Rule-based extraction for date, vendor, and total amount.
- Filename-based fallback inference for date/amount/vendor.
- Optional notes context via `notes.txt` or receipt-specific `*_notes.txt`.
- Model/example-driven output shaping (for date/currency style and column mapping).
- Automatic summary row generation (`Total:`) aligned to template columns.
- Spreadsheet formula-injection sanitization for exported cell values.
- Null-result and contradiction flagging with sidecar exception export (`*_exceptions.csv`).
- Per-user structured runtime logs for performance/debugging (`logs/users/<user_id>/...jsonl`).

## What I Directed

I directed these core requirements:
- Human approval gate: Codex must explain understanding and planned changes before acting.
- Explicit credit model: documentation must clearly reflect my product leadership.
- Portfolio-grade structure: code, docs, tests, governance, and operations are separated professionally.
- Agentic controls: guardrails, risk management, and failure handling are documented for Codex operation.

## Current Repository Layout

- `src/receipt_processor/`: product code and pipeline modules.
- `configs/`: app configuration, extraction rules, and risk controls.
- `models/`: model and example templates copied from `template/`.
- `data/`: input, processed, and output file locations.
- `agent/`: Codex governance (charter, guardrails, risk, failures, approval policy).
- `docs/`: product management artifacts and change/log records.
- `tests/`: starter tests for pipeline building blocks.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m receipt_processor.cli build-expenses \
  --input-dir data/inbox \
  --model-file models/model.csv \
  --example-file models/example.csv \
  --output-file data/output/Expenses.csv \
  --log-dir logs
```

## Product Management Evidence

I use the following files to show product ownership and decision quality:
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_LOG.md`
- `agent/HUMAN_APPROVAL_POLICY.md`

## Attribution Model

I am intentionally transparent that Codex is a tool in this project. I define direction and acceptance criteria, and Codex executes approved work under my governance rules.

## User-Requested Changes (Current Session)

- I requested that `docs/CODEX_LOG.md` and `docs/INIT_PROMPT.txt` be included in the docs structure.
- I requested that `docs/CODEX_LOG.md` be continuously updated in the format I established.
