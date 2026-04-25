# Risk Register

## R-001: OCR Misread Produces Incorrect Amount
- Likelihood: Medium
- Impact: High
- Mitigation: Confidence scoring + manual review threshold.

## R-002: Schema Drift Between Model and Output
- Likelihood: Medium
- Impact: Medium
- Mitigation: Load model headers dynamically and map fields explicitly.

## R-003: Incomplete Receipts
- Likelihood: High
- Impact: Medium
- Mitigation: Filename inference + exception queue.

## R-004: Unauthorized Agent Actions
- Likelihood: Low
- Impact: High
- Mitigation: Mandatory human-approval policy and change logging.
