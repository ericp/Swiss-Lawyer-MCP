from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
import httpx
import pytest
import yaml
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backend.api.app import create_app
from backend.ingestion.vector_store import ChromaChunkStore
from backend.memory.database import create_memory_engine, create_session_factory
from backend.synchronizer.discovery import discover_candidates_from_html
from backend.synchronizer.document_processor import (
    DocumentValidationError,
    validate_pdf_file,
)
from backend.synchronizer.html_extraction import extract_webpage
from backend.synchronizer.http_client import DomainValidationError, SyncHttpClient
from backend.synchronizer.models import CandidateStatus, ChangeStatus
from backend.synchronizer.regions import REGIONS, is_approved_url
from backend.synchronizer.source_registry import SourceRegistry, load_source_registry
from backend.synchronizer.synchronizer_service import SourceSynchronizer, classify_change
from backend.utils.config import SynchronizerSettings


@pytest.fixture()
def migrated_database(tmp_path: Path) -> str:
    database_url = f"sqlite:///{tmp_path / 'memory.db'}"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


def _settings(tmp_path: Path, registry_path: Path, database_url: str) -> SynchronizerSettings:
    return SynchronizerSettings(
        source_registry_path=registry_path,
        synchronized_pdf_path=tmp_path / "pdfs",
        synchronized_document_path=tmp_path / "documents",
        temporary_download_path=tmp_path / "tmp",
        sqlite_database_url=database_url,
        chroma_path=tmp_path / "chromadb",
        collection_name="test_collection",
        openai_api_key=None,
        max_document_bytes=5_000_000,
        chunk_size_words=80,
        chunk_overlap_words=10,
    )


def _write_registry(path: Path, sources: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"version": 1, "sources": sources}, sort_keys=False), encoding="utf-8")


def _source(
    *,
    source_id: str = "zh_driving",
    source_type: str = "pdf",
    url: str = "https://www.zh.ch/example/driving.pdf",
    enabled: bool = True,
    discovery_enabled: bool = False,
    local_filename: str = "driving.pdf",
) -> dict[str, Any]:
    return {
        "id": source_id,
        "enabled": enabled,
        "region": "zh",
        "authority": "Canton of Zurich",
        "procedure_types": ["driving_licence_exchange"],
        "source_type": source_type,
        "url": url,
        "language": "de",
        "local_filename": local_filename,
        "discovery_enabled": discovery_enabled,
    }


def _pdf_bytes(text: str = "Swiss permit text") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1)] for index, _text in enumerate(texts)]


class FakeCollection:
    def __init__(self, *, fail_add: bool = False) -> None:
        self.fail_add = fail_add
        self.added: dict[str, dict[str, Any]] = {}
        self.old_ids = ["old-1"]
        self.deleted: list[str] = []

    def add(self, *, ids, documents, embeddings, metadatas) -> None:
        if self.fail_add:
            raise RuntimeError("embedding insert failed")
        for index, chunk_id in enumerate(ids):
            self.added[chunk_id] = {
                "document": documents[index],
                "embedding": embeddings[index],
                "metadata": metadatas[index],
            }

    def get(self, where=None):
        return {"ids": list(self.old_ids)}

    def delete(self, ids) -> None:
        self.deleted.extend(ids)


class FakeHttpClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses

    def get(self, url: str, *, region: str, etag: str | None = None, last_modified: str | None = None):
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def _http_result(
    *,
    status_code: int = 200,
    content: bytes = b"",
    final_url: str = "https://www.zh.ch/example/driving.pdf",
    headers: dict[str, str] | None = None,
    content_type: str | None = "application/pdf",
):
    from backend.synchronizer.http_client import HttpFetchResult

    return HttpFetchResult(
        status_code=status_code,
        final_url=final_url,
        headers={key.lower(): value for key, value in (headers or {}).items()},
        content=content,
        content_type=content_type,
        content_length=len(content),
    )


def test_regions_and_domain_validation() -> None:
    assert set(REGIONS) >= {"federal", "zh", "vd", "ge", "ti"}
    assert is_approved_url("https://www.zh.ch/de/migration.html", region="zh")
    assert is_approved_url("https://www.sem.admin.ch/sem/en/home.html", region="federal")
    assert not is_approved_url("https://example.com/private.pdf", region="zh")
    assert not is_approved_url("http://www.zh.ch/insecure.pdf", region="zh")


def test_source_registry_loading_and_duplicate_rejection(tmp_path: Path) -> None:
    path = tmp_path / "sources.yaml"
    _write_registry(path, [_source()])
    registry = load_source_registry(path)

    assert registry.version == 1
    assert registry.sources[0].id == "zh_driving"

    _write_registry(path, [_source(), _source()])
    with pytest.raises(ValueError, match="Duplicate source id"):
        load_source_registry(path)


def test_unsafe_filename_and_path_traversal_rejection() -> None:
    with pytest.raises(ValueError, match="safe filename"):
        SourceRegistry.model_validate({"version": 1, "sources": [_source(local_filename="../x.pdf")]})


def test_redirect_outside_allowlist_rejection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith("https://www.zh.ch"):
            return httpx.Response(302, headers={"location": "https://example.com/file.pdf"})
        return httpx.Response(200, content=b"external")

    client = SyncHttpClient(client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True))

    with pytest.raises(DomainValidationError):
        client.get("https://www.zh.ch/start.pdf", region="zh")


def test_http_304_etag_last_modified_and_sha256_change_detection() -> None:
    assert classify_change(
        previous_sha256="a",
        previous_etag="etag",
        previous_last_modified="date",
        response_status=304,
        response_headers={},
        new_sha256=None,
    ) is ChangeStatus.UNCHANGED
    assert classify_change(
        previous_sha256="a",
        previous_etag="etag",
        previous_last_modified="date",
        response_status=200,
        response_headers={"etag": "new"},
        new_sha256="a",
    ) is ChangeStatus.UNCHANGED
    assert classify_change(
        previous_sha256="a",
        previous_etag="etag",
        previous_last_modified="date",
        response_status=200,
        response_headers={"last-modified": "new"},
        new_sha256="b",
    ) is ChangeStatus.CHANGED


def test_pdf_signature_validation_and_corrupt_rejection(tmp_path: Path) -> None:
    good_pdf = tmp_path / "good.pdf"
    good_pdf.write_bytes(_pdf_bytes())
    validate_pdf_file(good_pdf, content_type="application/pdf")

    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a pdf")
    with pytest.raises(DocumentValidationError):
        validate_pdf_file(bad_pdf, content_type="application/pdf")


def test_webpage_content_extraction_and_stable_hashing() -> None:
    html = """
    <html><head><title>Permit page</title><style>.x{}</style></head>
    <body><nav>Menu item</nav><header>Navigation</header>
    <main><h1>Driving licence exchange</h1><p>Exchange your foreign licence in Zurich.</p>
    <ul><li>Bring your identity document.</li></ul></main>
    <footer>Cookie settings</footer><script>bad()</script></body></html>
    """

    first = extract_webpage(html)
    second = extract_webpage(html.replace("\n", "   "))

    assert "Driving licence exchange" in first.content
    assert "Cookie settings" not in first.content
    assert first.content_sha256 == second.content_sha256


def test_new_pdf_indexing_and_changed_replacement(
    tmp_path: Path,
    migrated_database: str,
) -> None:
    registry_path = tmp_path / "sources.yaml"
    _write_registry(registry_path, [_source()])
    collection = FakeCollection()
    store = ChromaChunkStore(path=tmp_path / "chromadb", collection_name="x", collection=collection)
    service = SourceSynchronizer(
        settings=_settings(tmp_path, registry_path, migrated_database),
        session_factory=create_session_factory(create_memory_engine(migrated_database)),
        http_client=FakeHttpClient({
            "https://www.zh.ch/example/driving.pdf": _http_result(content=_pdf_bytes("New Zurich driving licence exchange text."))
        }),
        chunk_store=store,
        embedder=FakeEmbedder(),
    )

    report = service.sync_all()

    assert report.updated_count == 1
    assert collection.added
    assert collection.deleted == ["old-1"]
    assert (tmp_path / "pdfs" / "zh" / "driving.pdf").exists()


def test_old_chunks_retained_when_replacement_fails(
    tmp_path: Path,
    migrated_database: str,
) -> None:
    registry_path = tmp_path / "sources.yaml"
    _write_registry(registry_path, [_source(local_filename="failure.pdf")])
    collection = FakeCollection(fail_add=True)
    service = SourceSynchronizer(
        settings=_settings(tmp_path, registry_path, migrated_database),
        session_factory=create_session_factory(create_memory_engine(migrated_database)),
        http_client=FakeHttpClient({
            "https://www.zh.ch/example/driving.pdf": _http_result(content=_pdf_bytes("Failure document text."))
        }),
        chunk_store=ChromaChunkStore(path=tmp_path / "chromadb", collection_name="x", collection=collection),
        embedder=FakeEmbedder(),
    )

    report = service.sync_all()

    assert report.failed_count == 1
    assert collection.deleted == []


def test_unavailable_source_retains_last_version(
    tmp_path: Path,
    migrated_database: str,
) -> None:
    registry_path = tmp_path / "sources.yaml"
    _write_registry(registry_path, [_source()])
    service = SourceSynchronizer(
        settings=_settings(tmp_path, registry_path, migrated_database),
        session_factory=create_session_factory(create_memory_engine(migrated_database)),
        http_client=FakeHttpClient({
            "https://www.zh.ch/example/driving.pdf": _http_result(status_code=404, content=b"", content_type="text/html")
        }),
    )

    report = service.sync_all()

    assert report.failed_count == 1
    assert "unavailable" in report.events[0]


def test_synchronization_database_schema(migrated_database: str) -> None:
    inspector = inspect(create_memory_engine(migrated_database))
    assert set(inspector.get_table_names()) >= {
        "synchronized_sources",
        "synchronization_runs",
        "synchronization_events",
        "source_candidates",
    }


def test_landing_page_candidate_discovery_domain_filtering_and_deduplication() -> None:
    source = SourceRegistry.model_validate(
        {
            "version": 1,
            "sources": [
                _source(
                    source_type="landing_page",
                    url="https://www.zh.ch/de/migration.html",
                    local_filename="migration.html",
                    discovery_enabled=True,
                )
            ],
        }
    ).sources[0]
    html = """
    <a href="/de/migration/work-permit.pdf">Work permit PDF</a>
    <a href="https://example.com/work-permit.pdf">External work permit</a>
    <a href="/assets/logo.png">Logo</a>
    <a href="/de/migration/work-permit.pdf#top">Duplicate Work permit PDF</a>
    """

    candidates = discover_candidates_from_html(html, source=source)

    assert len(candidates) == 1
    assert candidates[0].canonical_url == "https://www.zh.ch/de/migration/work-permit.pdf"
    assert "work_permit" in candidates[0].inferred_procedure_types


def test_candidate_approval_and_rejection(
    tmp_path: Path,
    migrated_database: str,
) -> None:
    registry_path = tmp_path / "sources.yaml"
    _write_registry(
        registry_path,
        [
            _source(
                source_type="landing_page",
                url="https://www.zh.ch/de/migration.html",
                local_filename="migration.html",
                discovery_enabled=True,
            )
        ],
    )
    service = SourceSynchronizer(
        settings=_settings(tmp_path, registry_path, migrated_database),
        session_factory=create_session_factory(create_memory_engine(migrated_database)),
        http_client=FakeHttpClient({
            "https://www.zh.ch/de/migration.html": _http_result(
                content=b'<a href="/de/migration/work-permit.pdf">Work permit PDF</a>',
                final_url="https://www.zh.ch/de/migration.html",
                content_type="text/html",
            )
        }),
    )

    report = service.discover_all()
    candidates = service.list_candidates()
    approved = service.approve_candidate(candidates[0].id)

    assert report.discovered_candidate_count == 1
    assert approved.status is CandidateStatus.APPROVED
    assert any(source.id.startswith("candidate_") for source in load_source_registry(registry_path).sources)

    service = SourceSynchronizer(
        settings=_settings(tmp_path, registry_path, migrated_database),
        session_factory=create_session_factory(create_memory_engine(migrated_database)),
        http_client=FakeHttpClient({}),
    )
    rejected = service.reject_candidate(candidates[0].id, note="Already reviewed")
    assert rejected.status is CandidateStatus.REJECTED


def test_cli_scope_filtering_and_admin_endpoints_disabled_by_default(tmp_path: Path) -> None:
    sources = [_source(source_id="a", url="https://www.zh.ch/a.pdf"), _source(source_id="b", url="https://www.zh.ch/b.pdf")]
    registry = SourceRegistry.model_validate({"version": 1, "sources": sources})
    assert [source.id for source in registry.sources if source.region == "zh"] == ["a", "b"]

    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/v1/admin/synchronization/status").status_code == 404


def test_existing_manually_seeded_documents_remain_available() -> None:
    registry = load_source_registry(Path("data/pdfs/metadata/sources.yaml"))
    seed_sources = [source for source in registry.sources if source.source_type == "local_only"]

    assert seed_sources
    assert all(source.enabled is False for source in seed_sources)
    assert all(Path(source.url.removeprefix("local://")).exists() for source in seed_sources)
