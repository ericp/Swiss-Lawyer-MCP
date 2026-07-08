from pathlib import Path

import fitz

from backend.ingestion.extraction import extract_pages
from backend.models.document import PdfDocument


def test_extract_pages_preserves_page_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "federal" / "sample.pdf"
    pdf_path.parent.mkdir()
    pdf = fitz.open()
    page_one = pdf.new_page()
    page_one.insert_text((72, 72), "First page text")
    page_two = pdf.new_page()
    page_two.insert_text((72, 72), "Second page text")
    pdf.save(pdf_path)
    pdf.close()

    document = PdfDocument(path=pdf_path, source="sample.pdf", region="federal")

    pages = extract_pages(document)

    assert len(pages) == 2
    assert pages[0].source == "sample.pdf"
    assert pages[0].region == "federal"
    assert pages[0].page == 1
    assert "First page text" in pages[0].text
    assert pages[1].page == 2
    assert "Second page text" in pages[1].text
