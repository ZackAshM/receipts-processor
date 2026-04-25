# Changelog

## 2026-04-25

### Added
- Created initial repository scaffold for ReceiptProcessor.
- Initialized `.venv` for isolated project runtime.
- Added package layout under `src/receipt_processor`.
- Added starter configs, tests, and data folders.
- Added product docs (`PRD`, `ARCHITECTURE`, `DECISIONS`, `OPERATIONS`).
- Added agent governance docs under `agent/`.
- Added `docs/CODEX_LOG.md` workflow integration and preserved `docs/INIT_PROMPT.txt`.

### User-Requested Adjustments
- Included and preserved `docs/INIT_PROMPT.txt` as a static initialization artifact.
- Continued `docs/CODEX_LOG.md` using the heading-and-response format the user established.
- Updated logging policy to append-only maintenance with one-response-lag updates.
- Added explicit halt-until-resume control to governance documentation.
- Redacted sensitive data in `docs/CODEX_LOG.md` (including absolute filepaths) and codified ongoing log sanitization rules.
- Added git authority guardrails: developer-only `git push`, developer-only staging of untracked files/directories, and commit creation by Codex only on explicit developer request.

### Attribution
- Direction and requirements defined by user.
- Scaffold and implementation executed by Codex after user approval.
