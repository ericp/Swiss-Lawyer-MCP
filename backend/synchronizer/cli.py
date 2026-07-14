"""Command line interface for source synchronization."""

from __future__ import annotations

import argparse
import json
import logging

from backend.ingestion.embeddings import OpenAIEmbedder
from backend.ingestion.vector_store import ChromaChunkStore
from backend.memory.database import create_memory_engine, create_session_factory
from backend.synchronizer.http_client import SyncHttpClient
from backend.synchronizer.models import CandidateStatus
from backend.synchronizer.synchronizer_service import SourceSynchronizer
from backend.utils.config import load_synchronizer_settings


def build_service() -> SourceSynchronizer:
    settings = load_synchronizer_settings()
    engine = create_memory_engine(settings.sqlite_database_url)
    embedder = (
        OpenAIEmbedder(api_key=settings.openai_api_key, model=settings.embedding_model)
        if settings.openai_api_key
        else None
    )
    return SourceSynchronizer(
        settings=settings,
        session_factory=create_session_factory(engine),
        http_client=SyncHttpClient(
            timeout_seconds=settings.http_timeout_seconds,
            retry_count=settings.retry_count,
            retry_backoff_seconds=settings.retry_backoff_seconds,
            user_agent=settings.user_agent,
            max_response_bytes=settings.max_document_bytes,
        ),
        chunk_store=ChromaChunkStore(
            path=settings.chroma_path,
            collection_name=settings.collection_name,
        ),
        embedder=embedder,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Swiss Lawyer MCP synchronizer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")

    sync_parser = subparsers.add_parser("sync")
    sync_scope = sync_parser.add_mutually_exclusive_group()
    sync_scope.add_argument("--all", action="store_true")
    sync_scope.add_argument("--region")
    sync_scope.add_argument("--source")

    discover_parser = subparsers.add_parser("discover")
    discover_scope = discover_parser.add_mutually_exclusive_group()
    discover_scope.add_argument("--all", action="store_true")
    discover_scope.add_argument("--region")
    discover_scope.add_argument("--source")

    subparsers.add_parser("status")

    candidates_parser = subparsers.add_parser("candidates")
    candidate_subparsers = candidates_parser.add_subparsers(dest="candidate_command", required=True)
    candidate_subparsers.add_parser("list")
    approve_parser = candidate_subparsers.add_parser("approve")
    approve_parser.add_argument("candidate_id")
    reject_parser = candidate_subparsers.add_parser("reject")
    reject_parser.add_argument("candidate_id")
    reject_parser.add_argument("--note")

    cleanup_parser = subparsers.add_parser("cleanup")
    cleanup_parser.add_argument("--dry-run", action="store_true", required=True)

    args = parser.parse_args()
    service = build_service()

    if args.command == "validate":
        registry = service.validate_registry()
        print(json.dumps({"valid": True, "source_count": len(registry.sources)}, indent=2))
    elif args.command == "sync":
        if args.region:
            report = service.sync_region(args.region)
        elif args.source:
            report = service.sync_source(args.source)
        else:
            report = service.sync_all()
        print(report.model_dump_json(indent=2))
    elif args.command == "discover":
        if args.region:
            report = service.discover_region(args.region)
        elif args.source:
            report = service.discover_source(args.source)
        else:
            report = service.discover_all()
        print(report.model_dump_json(indent=2))
    elif args.command == "status":
        print(json.dumps(service.status(), indent=2))
    elif args.command == "candidates":
        if args.candidate_command == "list":
            candidates = service.list_candidates(status=CandidateStatus.PENDING)
            print(json.dumps([candidate.model_dump(mode="json") for candidate in candidates], indent=2))
        elif args.candidate_command == "approve":
            print(service.approve_candidate(args.candidate_id).model_dump_json(indent=2))
        elif args.candidate_command == "reject":
            print(service.reject_candidate(args.candidate_id, note=args.note).model_dump_json(indent=2))
    elif args.command == "cleanup":
        print(json.dumps({"dry_run": True, "message": "No cleanup performed."}, indent=2))


if __name__ == "__main__":
    main()
