from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from receipt_processor.llm.orchestrator import LLMExtractionResult
from receipt_processor.pipeline import run_pipeline
from receipt_processor.review.models import ReviewDecision, ReviewRequest


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_model_files(tmp_path: Path) -> tuple[Path, Path]:
    model_file = tmp_path / "model.csv"
    model_file.write_text(
        "Merchant,Amount\n"
        "{{merchant_name}},{{true_expense}}\n",
        encoding="utf-8",
    )
    example_file = tmp_path / "example.csv"
    example_file.write_text(
        "Merchant,Amount\n"
        "Cafe,$10.00\n",
        encoding="utf-8",
    )
    return model_file, example_file


def test_pipeline_logs_llm_fallback_warning_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "receipt_2026-04-26_10.50.png").write_bytes(b"not-an-image")
    (inbox / "receipt_2026-04-26_10.50_notes.txt").write_text(
        "vendor: Cafe\n"
        "date: 2026-04-26\n"
        "amount: 10.50\n"
        "expense_type: Food\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_model_files(tmp_path)
    output_file = tmp_path / "Expenses.csv"
    warning_events: list[dict[str, object]] = []

    def fake_extract_with_optional_llm(**kwargs) -> LLMExtractionResult:
        deterministic = kwargs["deterministic_extracted"]
        return LLMExtractionResult(
            extracted=dict(deterministic),
            deterministic_extracted=dict(deterministic),
            extraction_mode="llm_fallback",
            llm_enabled=True,
            llm_attempted=True,
            llm_requested_mode="text",
            llm_used_mode="text",
            llm_model="gpt-test",
            llm_failure_reason="rate_limit",
            warning_event={
                "warning_type": "llm_fallback",
                "source_file": kwargs["receipt_path"].name,
                "details": "rate_limit",
            },
        )

    monkeypatch.setattr("receipt_processor.pipeline.extract_with_optional_llm", fake_extract_with_optional_llm)

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output_file,
        log_dir=tmp_path / "logs",
        warning_handler=warning_events.append,
    )

    rows = _read_csv_rows(output_file)
    assert len(rows) == 1
    assert warning_events and warning_events[0]["warning_type"] == "llm_fallback"

    detailed = json.loads(output_file.with_name("Expenses_detailed.json").read_text(encoding="utf-8"))
    assert detailed["receipts"][0]["extraction"]["extraction_mode"] == "llm_fallback"


def test_pipeline_uses_llm_extraction_output_for_downstream_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "receipt.png").write_bytes(b"not-an-image")
    (inbox / "receipt_notes.txt").write_text(
        "vendor: Semantic Cafe\n"
        "date: 2026-04-26\n"
        "amount: 19.50\n"
        "expense_type: Food\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_model_files(tmp_path)
    output_file = tmp_path / "Expenses.csv"

    def fake_extract_with_optional_llm(**kwargs) -> LLMExtractionResult:
        deterministic = dict(kwargs["deterministic_extracted"])
        deterministic["merchant_name"] = "Semantic Cafe"
        deterministic["amount_paid"] = 19.50
        deterministic["transaction_type"] = "Food"
        deterministic["currency"] = "USD"
        deterministic["confidence"] = 0.95
        return LLMExtractionResult(
            extracted=deterministic,
            deterministic_extracted=kwargs["deterministic_extracted"],
            extraction_mode="llm",
            llm_enabled=True,
            llm_attempted=True,
            llm_requested_mode="text",
            llm_used_mode="text",
            llm_model="gpt-test",
            llm_usage={"total_tokens": 42},
            llm_response_id="resp_123",
        )

    monkeypatch.setattr("receipt_processor.pipeline.extract_with_optional_llm", fake_extract_with_optional_llm)

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output_file,
        log_dir=tmp_path / "logs",
    )

    rows = _read_csv_rows(output_file)
    assert len(rows) == 1
    assert rows[0]["Merchant"] == "Semantic Cafe"
    assert rows[0]["Amount"] == "$19.50"


def test_pipeline_emits_run_status_and_progress_events(
    tmp_path: Path,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "receipt_1_2026-04-26_10.50.png").write_bytes(b"not-an-image")
    (inbox / "receipt_1_2026-04-26_10.50_notes.txt").write_text(
        "vendor: Cafe\n"
        "date: 2026-04-26\n"
        "amount: 10.50\n"
        "expense_type: Food\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_model_files(tmp_path)
    output_file = tmp_path / "Expenses.csv"

    status_events: list[dict[str, object]] = []
    progress_events: list[dict[str, object]] = []

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output_file,
        log_dir=tmp_path / "logs",
        status_handler=status_events.append,
        progress_handler=progress_events.append,
    )

    assert status_events
    assert status_events[0]["event_type"] == "run_mode"
    assert status_events[0]["llm_mode"] == "deterministic"

    assert progress_events
    assert progress_events[-1]["event_type"] == "progress"
    assert progress_events[-1]["percent"] == 100


def test_pipeline_opens_llm_circuit_breaker_after_provider_failure_streak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for idx in range(1, 5):
        (inbox / f"receipt_{idx}.png").write_bytes(b"not-an-image")

    model_file, example_file = _build_model_files(tmp_path)
    output_file = tmp_path / "Expenses.csv"
    warning_events: list[dict[str, object]] = []
    settings_enabled_calls: list[bool] = []

    def fake_extract_with_optional_llm(**kwargs) -> LLMExtractionResult:
        settings_enabled_calls.append(bool(kwargs["settings"].enabled))
        deterministic = dict(kwargs["deterministic_extracted"])
        deterministic["merchant_name"] = "Fallback Cafe"
        deterministic["transaction_date"] = "2026-04-26"
        deterministic["transaction_type"] = "Food"
        deterministic["currency"] = "USD"
        deterministic["amount_paid"] = 10.00
        if kwargs["settings"].enabled:
            return LLMExtractionResult(
                extracted=deterministic,
                deterministic_extracted=kwargs["deterministic_extracted"],
                extraction_mode="llm_fallback",
                llm_enabled=True,
                llm_attempted=True,
                llm_requested_mode="text",
                llm_used_mode="text",
                llm_model="openrouter/free",
                llm_failure_reason="OpenRouter API HTTP error: status=429",
            )
        return LLMExtractionResult(
            extracted=deterministic,
            deterministic_extracted=kwargs["deterministic_extracted"],
            extraction_mode="deterministic",
            llm_enabled=False,
            llm_attempted=False,
            llm_requested_mode="text",
            llm_used_mode="",
            llm_model=None,
        )

    monkeypatch.setattr("receipt_processor.pipeline.extract_with_optional_llm", fake_extract_with_optional_llm)

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output_file,
        log_dir=tmp_path / "logs",
        enable_llm=True,
        warning_handler=warning_events.append,
    )

    assert settings_enabled_calls[:3] == [True, True, True]
    assert settings_enabled_calls[3] is False
    breaker_events = [
        event
        for event in warning_events
        if str(event.get("warning_type", "")) == "llm_circuit_breaker_opened"
    ]
    assert breaker_events


def test_pipeline_skips_exception_assist_after_provider_extraction_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    receipt_name = "20250817-Food-MountainRamblerBrewery.pdf"
    (inbox / receipt_name).write_bytes(b"%PDF-1.4")
    (inbox / "20250817-Food-MountainRamblerBrewery_notes.txt").write_text(
        "vendor: MOUNTAIN RAMBLER BREWERY\namount: 18.22\n",
        encoding="utf-8",
    )
    model_file, example_file = _build_model_files(tmp_path)
    output_file = tmp_path / "Expenses.csv"

    def fake_extract_with_optional_llm(**kwargs) -> LLMExtractionResult:
        deterministic = dict(kwargs["deterministic_extracted"])
        deterministic["merchant_name"] = "DRINKSPECIAL"
        deterministic["transaction_date"] = "2026-04-26"
        deterministic["transaction_type"] = "Food"
        deterministic["currency"] = "USD"
        deterministic["amount_paid"] = 18.22
        return LLMExtractionResult(
            extracted=deterministic,
            deterministic_extracted=kwargs["deterministic_extracted"],
            extraction_mode="llm_fallback",
            llm_enabled=True,
            llm_attempted=True,
            llm_requested_mode="text",
            llm_used_mode="text",
            llm_model="openrouter/free",
            llm_failure_reason="OpenRouter API HTTP error: status=429",
        )

    def fail_if_called(**kwargs):
        raise AssertionError("Exception assist should be skipped after provider extraction failure.")

    monkeypatch.setattr("receipt_processor.pipeline.extract_with_optional_llm", fake_extract_with_optional_llm)
    monkeypatch.setattr("receipt_processor.pipeline.attempt_llm_review_resolution", fail_if_called)

    def review_handler(request: ReviewRequest) -> ReviewDecision:
        assert request.issue_type == "contradiction_detected"
        return ReviewDecision(action="resolved", resolved_fields={"vendor": "MOUNTAIN RAMBLER BREWERY"})

    run_pipeline(
        input_dir=inbox,
        model_file=model_file,
        example_file=example_file,
        output_file=output_file,
        log_dir=tmp_path / "logs",
        enable_llm=True,
        llm_exception_assist=True,
        review_handler=review_handler,
    )

    rows = _read_csv_rows(output_file)
    assert len(rows) == 1
