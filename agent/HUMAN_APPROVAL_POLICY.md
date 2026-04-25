# Human Approval Policy

## Required Process

1. Codex summarizes current understanding.
2. Codex lists planned changes.
3. User approves, modifies, or rejects.
4. Codex executes only approved scope.

## Scope Controls

- Any net-new file creation requires prior approval.
- Any policy or governance change requires prior approval.
- Any potentially destructive action requires explicit consent.
- If the user issues a halt instruction, implementation work stays paused until explicit resume.

## Git Authority Controls

- Only the developer may run `git push`.
- Only the developer may run `git add` for untracked files or directories.
- Codex may create commits only when the developer explicitly requests a commit.
- When a commit is requested, Codex must avoid staging untracked files and operate only within the developer's git authority limits.

## Audit Requirements

- Keep `docs/CODEX_LOG.md` updated with prompt/response history.
- Use append-only updates to `docs/CODEX_LOG.md`; do not rewrite the full chat log unless explicitly requested.
- Use one-response-lag logging when end-of-response file edits are impossible: append the previous assistant/user exchange at the beginning of the next response cycle.
- Redact sensitive content in `docs/CODEX_LOG.md` before writing entries (for example: absolute filepaths, secrets, passwords, API keys, tokens, private identifiers).
- Record major decision outcomes in `docs/DECISIONS.md`.
