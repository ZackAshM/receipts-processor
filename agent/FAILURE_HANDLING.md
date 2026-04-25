# Failure Handling

## Failure Classes

- Input failure: unreadable file, unsupported format, missing file.
- Extraction failure: OCR/text parsing returns insufficient data.
- Mapping failure: required model columns cannot be populated.
- Export failure: target file write errors or unsupported output extension.

## Handling Policy

- Fail one record, continue batch when possible.
- Persist exception metadata for manual intervention.
- Surface clear error reasons in output metadata.

## Escalation

- If repeated extraction failures exceed threshold, pause rollout and request human review.
- If model schema changes unexpectedly, stop export and request template confirmation.
