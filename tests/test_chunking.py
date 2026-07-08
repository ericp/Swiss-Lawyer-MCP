import pytest

from backend.ingestion.chunking import chunk_pages
from backend.models.document import ExtractedPage


def test_chunk_pages_generates_overlapping_chunks_with_metadata() -> None:
    page = ExtractedPage(
        source="family_reunification.pdf",
        region="federal",
        page=3,
        text=" ".join(f"word{i}" for i in range(1, 11)),
    )

    chunks = chunk_pages([page], chunk_size_words=6, overlap_words=2)

    assert len(chunks) == 2
    assert chunks[0].text == "word1 word2 word3 word4 word5 word6"
    assert chunks[1].text == "word5 word6 word7 word8 word9 word10"
    assert chunks[0].metadata.source == "family_reunification.pdf"
    assert chunks[0].metadata.region == "federal"
    assert chunks[0].metadata.page == 3
    assert chunks[0].id.startswith("federal:family_reunification.pdf:p3:c1:")


def test_chunk_pages_skips_empty_pages() -> None:
    page = ExtractedPage(source="empty.pdf", region="vd", page=1, text="   ")

    assert chunk_pages([page]) == []


def test_chunk_pages_rejects_invalid_overlap() -> None:
    page = ExtractedPage(source="sample.pdf", region="ge", page=1, text="hello")

    with pytest.raises(ValueError):
        chunk_pages([page], chunk_size_words=10, overlap_words=10)
