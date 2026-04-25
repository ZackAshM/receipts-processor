from pathlib import Path

from receipt_processor.io.file_discovery import discover_receipt_files


def test_discover_receipt_files(tmp_path: Path) -> None:
    (tmp_path / "receipt1.pdf").write_text("x")
    (tmp_path / "receipt2.png").write_text("x")
    (tmp_path / "notes.txt").write_text("x")

    files = discover_receipt_files(tmp_path)
    names = [f.name for f in files]

    assert names == ["receipt1.pdf", "receipt2.png"]
