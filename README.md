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
- Low-confidence routing enforced via `configs/risk_controls.yaml` thresholds.
- Structured runtime logs for performance/debugging (`logs/performance-YYYY-MM-DD.jsonl`).
- Optional log privacy mode to mask sensitive file-level identifiers in runtime telemetry.

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
pip install -e .
receipts_processor data/inbox \
  --model-file models/model.csv \
  --example-file models/example.csv \
  --output-type csv \
  --log-dir logs \
  --risk-controls-file configs/risk_controls.yaml
```

## Usage Guide (For End Users)

### 1) Prepare your receipts folder

- Supported files: `.pdf`, `.jpeg`, `.jpg`, `.png`
- You can place receipts in either:
  - the default folder: `data/inbox/`, or
  - any custom folder path (inside or outside this repo)
- Optional context files:
  - `notes.txt` (global notes for all receipts in that folder)
  - `<receipt_name>_notes.txt` (receipt-specific notes)

### 2) Run the app

Available CLI command names:
- `receipts_processor` (recommended)
- `receipt_processor` (alias)
- `receipt-processor` (alias)
- `receipts_processor_gui` (desktop GUI)

Use the default project folders:

```bash
receipts_processor data/inbox \
  --model-file models/model.csv \
  --example-file models/example.csv \
  --output-type csv \
  --log-dir logs \
  --risk-controls-file configs/risk_controls.yaml
```

Use a custom receipts folder:

```bash
receipts_processor /path/to/my-receipts \
  --model-file models/model.csv \
  --example-file models/example.csv \
  --output-type xlsx \
  --log-dir logs \
  --risk-controls-file configs/risk_controls.yaml
```

If `--output-file` is omitted, the default is:
- `<INPUT_DIR>/Expenses.<output-type>`
- `--output-type` defaults to `csv`

If `--output-file` has no extension, the app appends `.<output-type>`.

### 2b) GUI usage (optional)

Run:

```bash
receipts_processor_gui
```

If `_tkinter` import fails, install Tk support for your Python:
- Ubuntu/Debian: `sudo apt-get install python3-tk`
- Fedora: `sudo dnf install python3-tkinter`
- macOS (Homebrew): `brew install python-tk` (or `brew install tcl-tk`)
- If all else fails: install Python with tkinter supported from [python.org](https://www.python.org/downloads/) and recreate your venv

### 3) Review outputs

- Main export: `Expenses.csv` (or `.xlsx` if you choose that extension)
- Flagged records: `Expenses_exceptions.csv`
- Runtime performance/debug logs: `logs/performance-YYYY-MM-DD.jsonl`

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
