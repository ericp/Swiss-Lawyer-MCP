"""CLI smoke test for Phase 5 grounded answer generation."""

from __future__ import annotations

import argparse
import json

from pydantic import ValidationError

from backend.clarification.clarification_engine import ClarificationEngine
from backend.clarification.intent_classifier import IntentClassifier
from backend.generation.answer_generator import GroundedAnswerGenerator
from backend.ingestion.embeddings import OpenAIEmbedder
from backend.models.generation import GeneratedAnswer
from backend.models.user_profile import UserProfile
from backend.reranking.reranker import CrossEncoderReranker
from backend.reranking.reranking_service import RerankingService
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.vector import VectorRetriever
from backend.utils.config import (
    load_generation_settings,
    load_retrieval_settings,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run clarification, retrieval, reranking, and grounded generation."
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="Can a Brazilian citizen work in Switzerland?",
    )
    parser.add_argument(
        "--profile-json",
        default='{"nationality":"Brazil","employment_status":"Swiss job offer","purpose_of_stay":"work","intended_canton":"Zurich"}',
        help="Completed user profile as JSON.",
    )
    parser.add_argument("--retrieval-top-k", type=int, default=None)
    parser.add_argument("--rerank-top-k", type=int, default=None)
    args = parser.parse_args()

    try:
        profile = UserProfile.model_validate(json.loads(args.profile_json))
    except (json.JSONDecodeError, ValidationError) as error:
        raise SystemExit(f"Invalid --profile-json: {error}") from error

    classifier = IntentClassifier()
    clarification_engine = ClarificationEngine()
    detected_intent = classifier.classify(args.question)
    clarification = clarification_engine.evaluate(
        user_question=args.question,
        detected_intent=detected_intent,
        user_profile=profile,
    )
    if clarification.needs_clarification:
        print("Clarification is required before answer generation.")
        for question in clarification.clarification_questions:
            print(f"- {question.question}")
        return

    retrieval_settings = load_retrieval_settings()
    generation_settings = load_generation_settings()
    retrieval_top_k = args.retrieval_top_k or retrieval_settings.top_k
    rerank_top_k = args.rerank_top_k or retrieval_settings.rerank_top_k

    embedder = OpenAIEmbedder(
        api_key=retrieval_settings.openai_api_key,
        model=retrieval_settings.embedding_model,
    )
    hybrid_retriever = HybridRetriever(
        vector_retriever=VectorRetriever(
            path=retrieval_settings.chroma_path,
            collection_name=retrieval_settings.collection_name,
            embedder=embedder,
        ),
        bm25_retriever=BM25Retriever(
            path=retrieval_settings.chroma_path,
            collection_name=retrieval_settings.collection_name,
        ),
    )
    reranking_service = RerankingService(
        hybrid_retriever=hybrid_retriever,
        reranker=CrossEncoderReranker(model_name=retrieval_settings.rerank_model),
    )
    _, rerank_result = reranking_service.retrieve_and_rerank(
        args.question,
        retrieval_top_k=retrieval_top_k,
        rerank_top_k=rerank_top_k,
    )

    generator = GroundedAnswerGenerator(
        api_key=generation_settings.openai_api_key,
        model=generation_settings.model,
    )
    answer = generator.generate(
        user_question=args.question,
        detected_intent=detected_intent,
        user_profile=profile,
        reranked_chunks=rerank_result.chunks,
    )

    _print_answer(answer)


def _print_answer(answer: GeneratedAnswer) -> None:
    print("\nAnswer")
    print(answer.answer)
    print("\nExplanation")
    print(answer.explanation)
    print("\nProcedure")
    if answer.procedure_steps:
        for index, step in enumerate(answer.procedure_steps, start=1):
            print(f"{index}. {step}")
    else:
        print("No procedure steps available from the retrieved context.")
    print("\nImportant Notes")
    for note in answer.important_notes:
        print(f"- {note}")
    print(f"\nConfidence: {answer.confidence}")
    print(f"Insufficient context: {answer.insufficient_context}")
    print("\nSources")
    for source in answer.cited_sources:
        page = f", page {source.page}" if source.page is not None else ""
        region = f", region {source.region}" if source.region else ""
        print(f"- {source.source}{page}{region}")


if __name__ == "__main__":
    main()
