# ReceiptProcessor

I used Codex to build ReceiptProcessor from scratch as an AI product project. I defined the product goals, architecture direction, collaboration rules, and governance constraints while using Codex as an execution partner.

This is my first project of this sort, so I am using it as an educational opportunity to learn/understand workflow creation and management of AI application in industry-grade software development.

Disclaimer: This is not guaranteed to perform perfectly for all receipts. Do your due diligence and check the totals. This app just makes it faster to itemize.

## Project Overview

I am building a receipt-to-expense pipeline that:
- Scans a folder for receipt files (`.pdf`, `.jpeg`, `.jpg`, `.png`).
- Extracts expense information from mixed receipt formats.
- Includes filename and optional `notes.txt` or bank/credit statement files to include as additional context in data extraction.
- Produces `Expenses.csv` or `Expenses.xlsx` based on a customizable model template contract.

## Installation & Setup

Clone this repository:

```bash
git clone https://github.com/ZackAshM/receipts-processor.git
cd receipts-processor
```

### Option A: One-step interactive setup (recommended)

```bash
python setup_project.py
```

This script:
- creates `.venv` if needed,
- installs dependencies and the package,
- creates/updates `.env`,
- asks if you want LLM support enabled,
- checks for `tkinter` and warns if GUI support may be unavailable.

### Option B: Manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
pip install -e .
```

## Usage Guide

### 1) Prepare your receipts folder (default path: `data/inbox/`)

- Supported files: `.pdf`, `.jpeg`, `.jpg`, `.png`
- Optional context files in the same folder:
  - `notes.txt` (global context)
  - `<receipt_name>_notes.txt` (receipt-specific context)

### 2) Run from CLI

Default run:

```bash
receipts_processor data/inbox
```

Custom run:

```bash
receipts_processor /path/to/my-receipts \
  --model-file models/model.csv \
  --example-file models/example.csv \
  --output-type xlsx
```

Notes:
- If `--output-file` is omitted, output defaults to `<INPUT_DIR>/Expenses.<output-type>`.
- `--output-type` defaults to `csv`.

### 3) Run GUI (optional)

```bash
receipts_processor_gui
```

If `tkinter` is missing, CLI still works. Install Tk support for your Python build to use the GUI.

### 4) Optional LLM extraction

The app works without LLM. To enable LLM behavior, set these in `.env`:
- `ENABLE_LLM=true|false`
- `OPENROUTER_API_KEY=<your token>`
- `OPENROUTER_MODEL=<model slug>` (default `openrouter/free`)

Per-run overrides are available in CLI flags and GUI Advanced options.

### 5) Outputs

- Main export: `Expenses.csv` or `Expenses.xlsx`
- Exceptions sidecar: `Expenses_exceptions.csv`
- Detailed sidecar: `Expenses_detailed.json`
- Readable summary sidecar: `Expenses_summary.md`
- Runtime logs: `logs/performance-YYYY-MM-DD.jsonl`

---

## What I Directed

I directed the project across product, architecture, security, and operations:
- Defined the product contract: template-driven outputs (`{{keywords}}`, `<operations>`) and model-first flexibility.
- Enforced governance: human approval flow, explicit attribution, and append-only Codex interaction logging.
- Set extraction strategy: deterministic-first reliability with optional LLM semantic extraction and strict fallback behavior.
- Required review controls: contradiction/null handling with user-in-the-loop resolution for critical values.
- Required security guardrails: redaction policy, sensitive-context controls, spreadsheet injection protections, and safer logging practices.
- Directed operational maturity: CI/security checks, dependency auditing, and reproducible setup guidance.
- Prioritized onboarding UX: clone-to-run startup script and clear user instructions for CLI and GUI.

## Key Capabilities

- Deterministic extraction from OCR/PDF text, filename hints, and notes context.
- Optional OpenRouter-backed LLM extraction with graceful deterministic fallback.
- Structured extraction and processing pipeline for derived expense values.
- Template renderer that fills model-defined keywords/operations.
- Exception routing and review flow for contradictions, low confidence, and null results.
- Runtime observability with structured logs and sidecar outputs.

## Repository Layout

- `src/receipt_processor/`: core application code
- `models/`: model and example templates
- `configs/`: runtime control files
- `data/`: inbox/output folders
- `tests/`: automated tests
- `docs/`: product, architecture, and decision history
- `agent/`: Codex governance and guardrail docs

## Attribution Model

I am intentionally transparent that Codex is a tool in this project. I define direction and acceptance criteria, and Codex executes approved work under my governance rules.
