from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from receipt_processor.extraction import ocr_router


def test_extract_text_from_pdf_falls_back_to_embedded_image_ocr(monkeypatch) -> None:
    class _FakeImage:
        data = b"fake-image-bytes"

    class _FakePage:
        def extract_text(self) -> str:
            return ""

        @property
        def images(self):
            return [_FakeImage()]

    class _FakeReader:
        def __init__(self, _path: str):
            self.pages = [_FakePage()]

    fake_pypdf = SimpleNamespace(PdfReader=_FakeReader)
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    monkeypatch.setattr(
        ocr_router,
        "_extract_text_from_image_bytes",
        lambda _data: "Amount Due $14.74",
    )

    extracted = ocr_router._extract_text_from_pdf(Path("dummy.pdf"))
    assert "14.74" in extracted


def test_extract_text_from_pdf_uses_ocr_when_text_is_too_short(monkeypatch) -> None:
    class _FakeImage:
        data = b"fake-image-bytes"

    class _FakePage:
        def extract_text(self) -> str:
            return "Tax"

        @property
        def images(self):
            return [_FakeImage()]

    class _FakeReader:
        def __init__(self, _path: str):
            self.pages = [_FakePage()]

    fake_pypdf = SimpleNamespace(PdfReader=_FakeReader)
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    monkeypatch.setenv("RECEIPT_PROCESSOR_PDF_MIN_TEXT_CHARS", "10")
    monkeypatch.setattr(
        ocr_router,
        "_extract_text_from_image_bytes",
        lambda _data: "Amount Paid 22.12",
    )

    extracted = ocr_router._extract_text_from_pdf(Path("dummy.pdf"))
    assert "Tax" in extracted
    assert "22.12" in extracted


def test_extract_text_from_pdf_skips_ocr_when_text_is_sufficient(monkeypatch) -> None:
    class _FakeImage:
        data = b"fake-image-bytes"

    class _FakePage:
        def extract_text(self) -> str:
            return "This receipt has enough text to skip OCR fallback behavior."

        @property
        def images(self):
            return [_FakeImage()]

    class _FakeReader:
        def __init__(self, _path: str):
            self.pages = [_FakePage()]

    fake_pypdf = SimpleNamespace(PdfReader=_FakeReader)
    monkeypatch.setitem(sys.modules, "pypdf", fake_pypdf)
    monkeypatch.setenv("RECEIPT_PROCESSOR_PDF_MIN_TEXT_CHARS", "10")

    def _fail_if_called(_data: bytes) -> str:
        raise AssertionError("Expected OCR bytes extractor not to be called.")

    monkeypatch.setattr(ocr_router, "_extract_text_from_image_bytes", _fail_if_called)

    extracted = ocr_router._extract_text_from_pdf(Path("dummy.pdf"))
    assert "enough text" in extracted
