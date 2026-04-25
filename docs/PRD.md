# Product Requirements Document (PRD)

## Ownership Statement

I am the product owner for ReceiptProcessor. I used Codex as my implementation tool while I defined scope, architecture intent, quality criteria, and governance rules.

## Problem Statement

I need a reliable way to convert mixed-format receipt inputs into a normalized expense ledger that matches a target accounting template.

## Goals

- Ingest receipts from a folder containing PDF and common image formats.
- Extract key expense fields from each receipt.
- Use filename-based inference when receipt content is incomplete.
- Export to CSV or XLSX with a schema aligned to a model file.

## Non-Goals (Phase 1)

- No production-grade multi-provider OCR orchestration yet.
- No autonomous write actions without explicit human approval.
- No hidden automation that bypasses governance files.

## Users

- AI product manager demonstrating product-definition and execution governance.
- Operator reviewing exceptions and low-confidence outputs.

## Success Criteria

- Pipeline runs end-to-end on a sample inbox.
- Output file aligns to model columns.
- Exceptions are captured for manual review.
- Documentation clearly attributes strategic decisions to me.
