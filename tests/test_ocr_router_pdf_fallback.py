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
