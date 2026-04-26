# review

Purpose:
- Defines shared interactive review contracts and handlers used by both CLI and GUI.
- Supports deterministic user-in-the-loop resolution for extraction issues.

Contents:
- `models.py`: shared request/decision dataclasses and `RunCancelledError`.
- `cli_resolver.py`: CLI prompt flow for choosing source value, manual input, skip receipt, or cancel run.

Behavior contract:
- `resolved`: user provided field values and pipeline continues.
- `skip_receipt`: pipeline sends receipt to exception flow.
- `cancel_run`: pipeline terminates immediately.
