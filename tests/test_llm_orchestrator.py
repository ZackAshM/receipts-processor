from __future__ import annotations

from pathlib import Path

from receipt_processor.extraction.ocr_router import DocumentExtraction
from receipt_processor.llm.client_base import LLMExtractionResponse, LLMProviderError, LLMUsage
from receipt_processor.llm.config import LLMInputMode, LLMSettings
from receipt_processor.llm.orchestrator import extract_with_optional_llm


def _base_extracted(filename: str = "receipt.png") -> dict[str, object]:
    return {
        "filename": filename,
        "document_type": "receipt",
        "merchant_name": "",
        "transaction_date": "",
        "transaction_type": "",
        "currency": "",
        "line_items": [],
        "subtotal": None,
        "tax": None,
        "tip": None,
        "service_charge": None,
        "pre_tip_total": None,
        "amount_paid": None,
        "used_keywords": {},
        "confidence": 0.0,
        "needs_review": False,
        "highlight_detection_available": False,
        "has_highlighted_contributions": False,
        "raw_text_length": 0,
    }


class _SuccessfulClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.text_calls = 0
        self.file_calls = 0
        self.last_text_context = ""
        self.last_file_context = ""

    def extract_from_text(
        self,
        *,
        model: str,
        filename: str,
        text: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        self.text_calls += 1
        self.last_text_context = context_text
        return LLMExtractionResponse(
            payload=self.payload,
            usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30, estimated_cost_usd=0.0015),
            response_id="resp_text_123",
        )

    def extract_from_file(
        self,
        *,
        model: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        self.file_calls += 1
        self.last_file_context = context_text
        return LLMExtractionResponse(
            payload=self.payload,
            usage=LLMUsage(prompt_tokens=8, completion_tokens=16, total_tokens=24, estimated_cost_usd=0.0012),
            response_id="resp_file_456",
        )


class _FailingClient:
    def extract_from_text(
        self,
        *,
        model: str,
        filename: str,
        text: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        raise LLMProviderError("rate_limit")

    def extract_from_file(
        self,
        *,
        model: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        raise LLMProviderError("rate_limit")


class _FileFailsTextSucceedsClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.text_calls = 0
        self.file_calls = 0

    def extract_from_text(
        self,
        *,
        model: str,
        filename: str,
        text: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        self.text_calls += 1
        return LLMExtractionResponse(payload=self.payload, usage=LLMUsage(total_tokens=10), response_id="text_ok")

    def extract_from_file(
        self,
        *,
        model: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        self.file_calls += 1
        raise LLMProviderError("model_does_not_support_file_mode")


class _FlakyTextClient:
    def __init__(self, payload: dict[str, object], fail_count: int) -> None:
        self.payload = payload
        self.fail_count = fail_count
        self.text_calls = 0

    def extract_from_text(
        self,
        *,
        model: str,
        filename: str,
        text: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        self.text_calls += 1
        if self.text_calls <= self.fail_count:
            raise LLMProviderError("OpenRouter API HTTP error: status=429")
        return LLMExtractionResponse(payload=self.payload, usage=LLMUsage(total_tokens=11), response_id="retry_ok")

    def extract_from_file(
        self,
        *,
        model: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        context_text: str = "",
    ) -> LLMExtractionResponse:
        raise LLMProviderError("not_used")


def test_llm_disabled_uses_deterministic_path(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Sample text", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    settings = LLMSettings(enabled=False, api_key="", model="gpt-test", input_mode=LLMInputMode.text)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
    )

    assert result.extraction_mode == "deterministic"
    assert result.llm_attempted is False
    assert result.extracted == deterministic
    assert result.warning_event is None


def test_llm_enabled_success_uses_llm_output(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Merchant LLM Cafe\nAmount Paid 12.34", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    client = _SuccessfulClient(
        {
            "merchant_name": "LLM Cafe",
            "transaction_type": "Food",
            "amount_paid": 12.34,
            "currency": "USD",
            "used_keywords": {"amount_paid": "Amount Paid 12.34"},
            "confidence": 0.91,
        }
    )
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.text)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
    )

    assert result.extraction_mode == "llm"
    assert result.llm_attempted is True
    assert result.extracted["merchant_name"] == "LLM Cafe"
    assert result.extracted["amount_paid"] == 12.34
    assert result.extracted["currency"] == "USD"
    assert client.text_calls == 1
    assert client.file_calls == 0
    assert result.warning_event is None


def test_llm_enabled_missing_key_falls_back(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Sample text", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    settings = LLMSettings(enabled=True, api_key="", model="gpt-test", input_mode=LLMInputMode.text)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
    )

    assert result.extraction_mode == "llm_fallback"
    assert result.llm_attempted is True
    assert result.llm_failure_reason == "missing_api_key"
    assert result.extracted == deterministic
    assert result.warning_event is not None


def test_llm_provider_failure_falls_back(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Sample text", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.text)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=_FailingClient(),
    )

    assert result.extraction_mode == "llm_fallback"
    assert result.llm_failure_reason == "rate_limit"
    assert result.extracted == deterministic


def test_invalid_llm_structured_output_falls_back(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Sample text", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    client = _SuccessfulClient({})
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.text)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
    )

    assert result.extraction_mode == "llm_fallback"
    assert "invalid_structured_output" in str(result.llm_failure_reason)
    assert result.extracted == deterministic


def test_failed_downstream_validation_falls_back(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Sample text", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    client = _SuccessfulClient({"merchant_name": "Cafe", "amount_paid": 5.0})
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.text)

    def failing_validator(_payload: dict[str, object]) -> None:
        raise ValueError("bad downstream shape")

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
        downstream_validator=failing_validator,
    )

    assert result.extraction_mode == "llm_fallback"
    assert result.llm_failure_reason == "failed_downstream_validation:ValueError"
    assert result.extracted == deterministic


def test_auto_mode_uses_file_for_images(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Text exists too", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    client = _SuccessfulClient({"merchant_name": "Cafe", "amount_paid": 5.0})
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.auto)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
    )

    assert result.extraction_mode == "llm"
    assert client.file_calls == 1
    assert client.text_calls == 0


def test_llm_context_is_included_in_requests(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="Primary receipt text", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    client = _SuccessfulClient({"merchant_name": "Cafe", "amount_paid": 5.0})
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.text)
    llm_context = {
        "filename": receipt.name,
        "notes": [{"filename": "notes.txt", "text": "Team dinner with client"}],
        "statements": [{"filename": "statement.pdf", "text": "Pending charge 5.00"}],
    }

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
        llm_context=llm_context,
    )

    assert result.extraction_mode == "llm"
    assert "notes_context" in client.last_text_context
    assert "statement_context" in client.last_text_context


def test_auto_mode_uses_file_for_pdfs(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.pdf"
    receipt.write_bytes(b"%PDF-1.4")
    document = DocumentExtraction(raw_text="PDF text exists", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    client = _SuccessfulClient({"merchant_name": "Cafe", "amount_paid": 5.0})
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.auto)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
    )

    assert result.extraction_mode == "llm"
    assert client.file_calls == 1


def test_file_mode_pdf_can_fallback_to_text_input(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.pdf"
    receipt.write_bytes(b"%PDF-1.4")
    document = DocumentExtraction(raw_text="PDF text", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.file)

    client = _FileFailsTextSucceedsClient({"merchant_name": "Cafe", "amount_paid": 7.25})

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
    )

    assert result.extraction_mode == "llm"
    assert result.extracted["merchant_name"] == "Cafe"
    assert result.extracted["amount_paid"] == 7.25
    assert client.file_calls == 1
    assert client.text_calls == 1


def test_text_mode_retries_transient_provider_failures(tmp_path: Path, monkeypatch) -> None:
    receipt = tmp_path / "receipt.png"
    receipt.write_bytes(b"png")
    document = DocumentExtraction(raw_text="merchant cafe", ocr_lines=[], highlight_detection_available=False)
    deterministic = _base_extracted(receipt.name)
    settings = LLMSettings(enabled=True, api_key="test-key", model="gpt-test", input_mode=LLMInputMode.text)
    client = _FlakyTextClient({"merchant_name": "Retry Cafe", "amount_paid": 9.5}, fail_count=2)

    monkeypatch.setattr("receipt_processor.llm.extractor.time.sleep", lambda _: None)

    result = extract_with_optional_llm(
        receipt_path=receipt,
        document=document,
        deterministic_extracted=deterministic,
        settings=settings,
        client=client,
    )

    assert result.extraction_mode == "llm"
    assert result.extracted["merchant_name"] == "Retry Cafe"
    assert client.text_calls == 3
