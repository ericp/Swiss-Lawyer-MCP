from pathlib import Path

from backend.ingestion.discovery import discover_pdfs


def test_discover_pdfs_recursively_preserves_source_and_region(tmp_path: Path) -> None:
    pdf_root = tmp_path / "pdfs"
    federal = pdf_root / "federal"
    zurich = pdf_root / "zh"
    federal.mkdir(parents=True)
    zurich.mkdir(parents=True)
    (federal / "family_reunification.pdf").write_bytes(b"%PDF-1.7")
    (zurich / "registration_zurich.pdf").write_bytes(b"%PDF-1.7")
    (zurich / "notes.txt").write_text("not a pdf", encoding="utf-8")

    documents = discover_pdfs(pdf_root)

    assert [document.source for document in documents] == [
        "family_reunification.pdf",
        "registration_zurich.pdf",
    ]
    assert [document.region for document in documents] == ["federal", "zh"]


def test_discover_pdfs_returns_empty_list_for_missing_root(tmp_path: Path) -> None:
    assert discover_pdfs(tmp_path / "missing") == []
