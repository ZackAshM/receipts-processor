# Guardrails

## Behavioral Guardrails

- Do not perform edits before explicit approval.
- Do not hide limitations or uncertain assumptions.
- Do not claim results without verifiable evidence.

## Technical Guardrails

- Preserve source receipts; never overwrite originals.
- Route unsupported formats to exception handling.
- Track confidence and validation outcomes per record.
- Do not execute `git push`; this action is reserved for the developer.
- Do not run `git add` on untracked files or directories; this action is reserved for the developer.
- Do not create commits unless explicitly requested by the developer.

## Documentation Guardrails

- Attribute product direction to the user.
- Record requested changes in docs and logs.
- Keep governance files current when process rules change.
