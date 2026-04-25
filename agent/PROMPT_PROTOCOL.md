# Prompt Protocol

## Prompt Intake

- Capture objective, constraints, and success criteria.
- Identify explicit user-requested changes.
- Highlight assumptions before execution.

## Response Structure

- Restate understanding in concise form.
- Describe proposed changes before editing.
- Confirm post-change outcomes and unresolved risks.

## Traceability

- Align implementation notes with `docs/CHANGELOG.md`.
- Keep user-owned direction visible in product docs.
- Update `docs/CODEX_LOG.md` in append-only mode.
- When needed, apply one-response-lag logging by appending the previous exchange before sending the next response.
- Sanitize `docs/CODEX_LOG.md` entries to avoid leaking sensitive values (absolute paths, credentials, secrets, and tokens).
- Enforce git authority boundaries: no `git push`, no staging untracked files, and no commits unless explicitly requested by the developer.
