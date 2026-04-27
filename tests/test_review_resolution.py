from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from receipt_processor.llm.review_assist import LLMReviewAssistResult
from receipt_processor.pipeline import run_pipeline
from receipt_processor.review.models import ReviewDecision, ReviewRequest, RunCancelledError


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_minimal_model_files(tmp_path: Path) -> tuple[Path, Path]:
    model_file = tmp_path / "model.csv"
    model_file.write_text(
        "Date,Description,Amt Claimed (USD)\n"
        "{{transaction_date}},{{description}},{{true_expense}}\n",
        encoding="utf-8",
    )

    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Date,Description,Amt Claimed (USD)\n"
        "2025 06 24,Transportation - Lyft,$19.23\n",
        encoding="utf-8",
    )
    return model_file, example_file


def _build_amount_only_model_files(tmp_path: Path) -> tuple[Path, Path]:
    model_file = tmp_path / "model_amount.csv"
    model_file.write_text(
        "Amt Claimed (USD)\n"
        "{{true_expense}}\n",
        encoding="utf-8",
    )

    example_file = tmp_path / "example_amount.csv"
    example_file.write_text(
        "Amt Claimed (USD)\n$19.23\n",
        encoding="utf-8",
    )
    return model_file, example_file


def test_review_handler_can_resolve_contradiction_and_continue(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "trip_2025-06-24_19.23.png").write_bytes(b"not-an-image")
    (inbox / "trip_2025-06-24_19.23_notes.txt").write_text(
        "vendor: Lyft\n"
        "date: 2025-06-24\n"
        "amount: 20.00\n"
        "expense_type: Transportation\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_minimal_model_files(tmp_path)
    output = tmp_path / "Expenses.csv"

    def review_handler(request: ReviewRequest) -> ReviewDecision:
        if request.issue_type == "contradiction_detected":
            return ReviewDecision(
                action="resolved",
                resolved_fields={"vendor": "Lyft", "amount": "19.23"},
            )
        return ReviewDecision(action="resolved", resolved_fields={})

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output,
        log_dir=tmp_path / "logs",
        review_handler=review_handler,
    )

    rows = _read_csv_rows(output)
    assert len(rows) == 1
    assert rows[0]["Amt Claimed (USD)"] == "$19.23"

    exceptions_file = output.with_name("Expenses_exceptions.csv")
    assert not exceptions_file.exists()


def test_llm_exception_assist_can_resolve_contradiction_before_user_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "trip_2025-06-24_19.23.png").write_bytes(b"not-an-image")
    (inbox / "trip_2025-06-24_19.23_notes.txt").write_text(
        "vendor: Lyft\n"
        "date: 2025-06-24\n"
        "amount: 20.00\n"
        "expense_type: Transportation\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_minimal_model_files(tmp_path)
    output = tmp_path / "Expenses.csv"

    def fake_assist(**kwargs) -> LLMReviewAssistResult:
        request = kwargs["request"]
        assert request.issue_type == "contradiction_detected"
        return LLMReviewAssistResult(
            attempted=True,
            resolved=True,
            reason="resolved_confidence_0.95",
            decision=ReviewDecision(
                action="resolved",
                resolved_fields={"vendor": "Lyft", "amount": "19.23"},
            ),
            usage={"total_tokens": 10},
            response_id="assist_001",
        )

    monkeypatch.setattr("receipt_processor.pipeline.attempt_llm_review_resolution", fake_assist)

    def review_handler(_: ReviewRequest) -> ReviewDecision:
        raise AssertionError("User review should not be invoked when LLM assist resolves clearly.")

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output,
        log_dir=tmp_path / "logs",
        enable_llm=True,
        llm_exception_assist=True,
        review_handler=review_handler,
    )

    rows = _read_csv_rows(output)
    assert len(rows) == 1
    assert rows[0]["Amt Claimed (USD)"] == "$19.23"


def test_llm_exception_assist_abstain_reports_and_falls_back_to_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "trip_2025-06-24_19.23.png").write_bytes(b"not-an-image")
    (inbox / "trip_2025-06-24_19.23_notes.txt").write_text(
        "vendor: Lyft\n"
        "date: 2025-06-24\n"
        "amount: 20.00\n"
        "expense_type: Transportation\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_minimal_model_files(tmp_path)
    output = tmp_path / "Expenses.csv"
    warning_events: list[dict[str, object]] = []

    def fake_assist(**kwargs) -> LLMReviewAssistResult:
        request = kwargs["request"]
        assert request.issue_type == "contradiction_detected"
        return LLMReviewAssistResult(
            attempted=True,
            resolved=False,
            reason="abstained",
        )

    monkeypatch.setattr("receipt_processor.pipeline.attempt_llm_review_resolution", fake_assist)

    def review_handler(request: ReviewRequest) -> ReviewDecision:
        assert request.issue_type == "contradiction_detected"
        return ReviewDecision(
            action="resolved",
            resolved_fields={"vendor": "Lyft", "amount": "19.23"},
        )

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output,
        log_dir=tmp_path / "logs",
        enable_llm=True,
        llm_exception_assist=True,
        review_handler=review_handler,
        warning_handler=warning_events.append,
    )

    rows = _read_csv_rows(output)
    assert len(rows) == 1
    assert rows[0]["Amt Claimed (USD)"] == "$19.23"

    assist_warnings = [
        event
        for event in warning_events
        if str(event.get("warning_type", "")) == "llm_exception_assist_fallback"
    ]
    assert assist_warnings


def test_review_handler_can_skip_receipt_to_exception_flow(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "trip_2025-06-24_19.23.png").write_bytes(b"not-an-image")
    (inbox / "trip_2025-06-24_19.23_notes.txt").write_text(
        "vendor: Lyft\n"
        "date: 2025-06-24\n"
        "amount: 20.00\n"
        "expense_type: Transportation\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_minimal_model_files(tmp_path)
    output = tmp_path / "Expenses.csv"

    def review_handler(_: ReviewRequest) -> ReviewDecision:
        return ReviewDecision(action="skip_receipt")

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output,
        log_dir=tmp_path / "logs",
        review_handler=review_handler,
    )

    rows = _read_csv_rows(output)
    assert rows == []

    exceptions = _read_csv_rows(output.with_name("Expenses_exceptions.csv"))
    assert len(exceptions) == 1
    assert exceptions[0]["issue_type"] == "contradiction_detected"


def test_review_handler_can_cancel_full_run(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "trip_2025-06-24_19.23.png").write_bytes(b"not-an-image")
    (inbox / "trip_2025-06-24_19.23_notes.txt").write_text(
        "vendor: Lyft\n"
        "date: 2025-06-24\n"
        "amount: 20.00\n"
        "expense_type: Transportation\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_minimal_model_files(tmp_path)
    output = tmp_path / "Expenses.csv"

    def review_handler(_: ReviewRequest) -> ReviewDecision:
        return ReviewDecision(action="cancel_run")

    with pytest.raises(RunCancelledError):
        run_pipeline(
            input_dir=inbox,
            model_file=model_file,
            example_file=example_file,
            output_file=output,
            log_dir=tmp_path / "logs",
            review_handler=review_handler,
        )

    assert not output.exists()


def test_non_required_contradictions_are_logged_but_do_not_block_output(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "trip_2025-06-24_19.23.png").write_bytes(b"not-an-image")
    (inbox / "trip_2025-06-24_19.23_notes.txt").write_text(
        "vendor: Lyft\n"
        "date: 2025-06-24\n"
        "amount: 19.23\n"
        "expense_type: Transportation\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_amount_only_model_files(tmp_path)
    output = tmp_path / "Expenses.csv"
    warning_events: list[dict[str, object]] = []

    def review_handler(_: ReviewRequest) -> ReviewDecision:
        raise AssertionError("Review handler should not be called for non-required contradictions.")

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output,
        log_dir=tmp_path / "logs",
        enable_llm=False,
        review_handler=review_handler,
        warning_handler=warning_events.append,
    )

    rows = _read_csv_rows(output)
    assert len(rows) == 1
    assert rows[0]["Amt Claimed (USD)"] == "$19.23"

    exceptions_file = output.with_name("Expenses_exceptions.csv")
    assert not exceptions_file.exists()

    detailed_file = output.with_name("Expenses_detailed.json")
    payload = json.loads(detailed_file.read_text(encoding="utf-8"))
    assert payload["receipts"][0]["status"] == "processed"
    assert payload["receipts"][0]["blocking_contradictions"] == []
    assert payload["receipts"][0]["non_blocking_contradictions"]
    assert len(warning_events) == 1
    assert warning_events[0]["warning_type"] == "non_blocking_contradictions"
