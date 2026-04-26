# models

Purpose:
- Defines the deterministic output-template contract for `model.csv` / `model.xlsx`.
- Enables custom model design using keyword placeholders.

Contents:
- `model.csv` / `model.xlsx`: target export schema (your desired output columns/format).
- `example.csv` / `example.xlsx`: sample row formatting guidance.

## Deterministic Template Contract

Use keyword placeholders with this syntax:
- `{{keyword_name}}`

Rules:
- Cells containing `{{...}}` are treated as dynamic keyword placeholders.
- Text outside placeholders is treated as literal text.
- You can combine literal text + placeholders in one cell.
- Unknown placeholders are expected to be flagged for review by the pipeline.

Examples:
- `{{transaction_date}}`
- `{{true_expense}}`
- `{{transaction_type}} - {{merchant_name}}`
- `Company Card - {{merchant_name}}`

## Supported Keywords (Current Contract)

Core identity:
- `filename`: source file name for traceability.
- `document_type`: detected document type (`receipt`, `email`, `statement`, etc.).
- `merchant_name`: vendor/merchant name inferred from text and/or filename context.
- `transaction_date`: normalized transaction date.
- `transaction_type`: deterministic category (for example `Food`, `Transportation`).
- `currency`: detected or inferred currency code/symbol context (for example `USD`).

Line-item contribution summary:
- `contributing_items_total`: sum of amounts considered contributing.
- `noncontributing_items_total`: sum of amounts considered non-contributing.
- `contributing_items_count`: number of contributing line items.
- `noncontributing_items_count`: number of non-contributing line items.
- `contributing_items_json`: JSON string of contributing item entries (name + amount + metadata).
- `noncontributing_items_json`: JSON string of non-contributing item entries (name + amount + metadata).
- `contributing_item_names`: delimited list of contributing item names.
- `noncontributing_item_names`: delimited list of non-contributing item names.

Totals and charges:
- `subtotal`: subtotal before tax/tip when detected.
- `tax`: tax amount when detected.
- `tip`: tip/gratuity amount when detected.
- `service_charge`: service charge/fee when detected.
- `pre_tip_total`: total before tip (when detectable from keywords/math).
- `amount_paid`: paid total on the receipt.

Processed fields:
- `true_expense`: normalized claimed expense after deterministic processing rules.
- `receipt_expense`: normalized receipt amount (usually paid total).
- `receipt_amount_if_different`: empty when `true_expense == receipt_expense`; otherwise equals `receipt_expense`.
- `description`: deterministic description, typically `<transaction_type> - <merchant_name>`.

Quality and traceability:
- `confidence`: deterministic confidence score for the extracted+processed result.
- `needs_review`: review flag set when confidence/rules indicate manual check.
- `used_keywords_json`: JSON string showing keyword evidence snippets used for field extraction.

## Operation Placeholders (Run-Level Aggregates)

In addition to per-receipt keywords, the template can include reserved operation placeholders:
- `<total_expenses>`: sum of all `true_expense` values in the run.
- `<total_receipt_expenses>`: sum of all `receipt_expense` values in the run.
- `<total_contributing_items>`: sum of all `contributing_items_total` values in the run.
- `<total_noncontributing_items>`: sum of all `noncontributing_items_total` values in the run.
- `<receipt_count>`: total number of processed receipts in the run.

Operation placeholders are intended for report-level summary rows/fields.

## Recommended Model Design

- Keep headers as your target output labels (human-readable).
- Put placeholders in row cells where dynamic values should be inserted.
- Use literal text for fixed values (department labels, reimbursement class, etc.).
- Prefer `{{true_expense}}` for claimed expense and `{{receipt_expense}}` for paid/receipt total when your model separates them.
- Use operation placeholders like `<total_expenses>` in summary rows.

## Example Pattern

For a model with columns:
- `Date`, `Description`, `Amt Claimed (USD)`, `Receipt Amt (USD)`, `Notes`

An example template row could be:
- `{{transaction_date}}`, `{{description}}`, `{{true_expense}}`, `{{receipt_expense}}`, `File: {{filename}}`

An example summary row could include:
- `TOTAL`, `All Receipts`, `<total_expenses>`, `<total_receipt_expenses>`, `Count: <receipt_count>`

This contract is intentionally deterministic so future extraction/processing logic can map fields consistently without LLM inference.
