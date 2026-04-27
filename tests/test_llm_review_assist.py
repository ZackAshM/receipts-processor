from __future__ import annotations

from receipt_processor.llm.client_base import LLMExtractionResponse, LLMUsage
from receipt_processor.llm.config import LLMInputMode, LLMSettings
from receipt_processor.llm.review_assist import attempt_llm_review_resolution
from receipt_processor.review.models import ReviewField, ReviewOption, ReviewRequest


class _AssistClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0

    def assist_review_resolution(
        self,
        *,
        model: str,
        review_payload: dict[str, object],
    ) -> LLMExtractionResponse:
        self.calls += 1
        return LLMExtractionResponse(
            payload=dict(self.payload),
            usage=LLMUsage(total_tokens=22),
            response_id="assist_123",
        )


def _settings(*, enabled: bool, assist: bool) -> LLMSettings:
    return LLMSettings(
        enabled=enabled,
        api_key="test-key",
        model="google/gemini-2.5-flash",
        input_mode=LLMInputMode.auto,
        enable_exception_assist=assist,
    )


def _request() -> ReviewRequest:
    return ReviewRequest(
        issue_type="contradiction_detected",
        title="Contradiction Detected",
        message="Choose one source value.",
        receipt_filename="receipt.png",
        fields=[
            ReviewField(
                name="vendor",
                display_name="Vendor",
                options=[
                    ReviewOption(source="file", value="DRINKSPECIAL"),
                    ReviewOption(source="filename", value="BURGERJOINT"),
                    ReviewOption(source="notes", value="BURGERSHACK"),
                ],
            )
        ],
    )


def test_review_assist_resolves_obvious_value() -> None:
    result = attempt_llm_review_resolution(
        request=_request(),
        source_fields={
            "file": {"vendor": "DRINKSPECIAL"},
            "filename": {"vendor": "BURGERJOINT"},
            "notes": {"vendor": "BURGERSHACK"},
        },
        receipt_filename="receipt.png",
        settings=_settings(enabled=True, assist=True),
        client=_AssistClient(
            {
                "action": "resolve",
                "confidence": 0.95,
                "resolved_fields": {"vendor": "BURGERJOINT"},
                "reason": "filename and merchant pattern align",
            }
        ),
    )

    assert result.attempted is True
    assert result.resolved is True
    assert result.decision is not None
    assert result.decision.resolved_fields["vendor"] == "BURGERJOINT"
    assert result.usage is not None


def test_review_assist_abstains_when_value_not_in_options() -> None:
    result = attempt_llm_review_resolution(
        request=_request(),
        source_fields={
            "file": {"vendor": "DRINKSPECIAL"},
            "filename": {"vendor": "BURGERJOINT"},
            "notes": {"vendor": "BURGERSHACK"},
        },
        receipt_filename="receipt.png",
        settings=_settings(enabled=True, assist=True),
        client=_AssistClient(
            {
                "action": "resolve",
                "confidence": 0.98,
                "resolved_fields": {"vendor": "UNKNOWN_VENDOR"},
                "reason": "guess",
            }
        ),
    )

    assert result.attempted is True
    assert result.resolved is False
    assert result.decision is None
    assert result.reason == "no_valid_option_selected"


def test_review_assist_can_resolve_without_confidence_threshold() -> None:
    result = attempt_llm_review_resolution(
        request=_request(),
        source_fields={
            "file": {"vendor": "DRINKSPECIAL"},
            "filename": {"vendor": "BURGERJOINT"},
            "notes": {"vendor": "BURGERSHACK"},
        },
        receipt_filename="receipt.png",
        settings=_settings(enabled=True, assist=True),
        client=_AssistClient(
            {
                "action": "resolve",
                "confidence": 0.12,
                "resolved_fields": {"vendor": "BURGERSHACK"},
                "reason": "obvious from notes reference",
            }
        ),
    )

    assert result.attempted is True
    assert result.resolved is True
    assert result.decision is not None
    assert result.decision.resolved_fields["vendor"] == "BURGERSHACK"


def test_review_assist_skips_numeric_decisions_for_user() -> None:
    request = ReviewRequest(
        issue_type="contradiction_detected",
        title="Amount Contradiction",
        message="Choose one amount.",
        receipt_filename="receipt.png",
        fields=[
            ReviewField(
                name="amount",
                display_name="Amount",
                options=[
                    ReviewOption(source="file", value="$12.50"),
                    ReviewOption(source="filename", value="12.30"),
                    ReviewOption(source="notes", value="(13.00)"),
                ],
            )
        ],
    )
    client = _AssistClient(
        {
            "action": "resolve",
            "confidence": 0.95,
            "resolved_fields": {"amount": "$12.50"},
            "reason": "irrelevant",
        }
    )
    result = attempt_llm_review_resolution(
        request=request,
        source_fields={
            "file": {"amount": "$12.50"},
            "filename": {"amount": "12.30"},
            "notes": {"amount": "(13.00)"},
        },
        receipt_filename="receipt.png",
        settings=_settings(enabled=True, assist=True),
        client=client,
    )

    assert result.attempted is False
    assert result.resolved is False
    assert result.reason == "numeric_decisions_require_user"
    assert client.calls == 0
