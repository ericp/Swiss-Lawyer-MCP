"""Citation and source-attribution metrics."""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult, get_field, non_applicable, result_identifier, source_id
from evaluation.metrics.generation import _claim_count
from evaluation.models import EvaluationCase, EvaluationCaseResult


def _citations(result: EvaluationCaseResult) -> list[object]:
    if result.sources:
        return result.sources
    return list(get_field(result.generated_answer, "cited_sources", []) or [])


def _retrieved_source_ids(result: EvaluationCaseResult) -> set[str]:
    items = result.vector_results + result.bm25_results + result.hybrid_results + result.reranked_results
    ids = {source_id(item) for item in items}
    ids.update(result_identifier(item) for item in items)
    ids.discard(None)
    ids.discard("")
    return {str(item) for item in ids}


def _citation_source(citation: object) -> str | None:
    return source_id(citation) or result_identifier(citation) or None


class CitationPresence(Metric):
    metric_name = "citation_presence"
    category = "citations"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if result.generated_answer is None and not case.expected_source_ids:
            return non_applicable(self.metric_name, reason="No generated answer or expected citations")
        return MetricResult(metric_name=self.metric_name, value=1.0 if _citations(result) else 0.0)


class CitationCoverage(Metric):
    metric_name = "citation_coverage"
    category = "citations"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        claims = _claim_count(result)
        if claims == 0:
            return non_applicable(self.metric_name, reason="No generated answer claims")
        return MetricResult(metric_name=self.metric_name, value=min(1.0, len(_citations(result)) / claims), details={"claims": claims, "citations": len(_citations(result))})


class CitationSourceAccuracy(Metric):
    metric_name = "citation_source_accuracy"
    category = "citations"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        citations = _citations(result)
        if not citations:
            return non_applicable(self.metric_name, reason="No citations")
        allowed = _retrieved_source_ids(result) | set(case.expected_source_ids)
        if not allowed:
            return non_applicable(self.metric_name, reason="No retrieved or expected sources")
        correct = [_citation_source(citation) for citation in citations if _citation_source(citation) in allowed]
        return MetricResult(metric_name=self.metric_name, value=len(correct) / len(citations), details={"allowed": sorted(allowed), "correct": correct})


class CitationSupportAccuracy(Metric):
    metric_name = "citation_support_accuracy"
    category = "citations"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        citations = _citations(result)
        expected = set(case.expected_source_ids)
        if not citations or not expected:
            return non_applicable(self.metric_name, reason="No citations or expected sources")
        supported = [_citation_source(citation) for citation in citations if _citation_source(citation) in expected]
        return MetricResult(metric_name=self.metric_name, value=len(supported) / len(citations), details={"supported": supported})


class CitationMetadataCompleteness(Metric):
    metric_name = "citation_metadata_completeness"
    category = "citations"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        citations = _citations(result)
        if not citations:
            return non_applicable(self.metric_name, reason="No citations")
        complete = 0
        for citation in citations:
            has_source = bool(_citation_source(citation))
            has_region = bool(get_field(citation, "region"))
            has_location = bool(get_field(citation, "page") or get_field(citation, "section"))
            has_url_when_present = "official_url" not in _keys(citation) or bool(get_field(citation, "official_url"))
            if has_source and has_region and has_location and has_url_when_present:
                complete += 1
        return MetricResult(metric_name=self.metric_name, value=complete / len(citations), details={"complete": complete, "total": len(citations)})


class FabricatedCitationRate(Metric):
    metric_name = "fabricated_citation_rate"
    category = "citations"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        citations = _citations(result)
        if not citations:
            return non_applicable(self.metric_name, reason="No citations")
        allowed = _retrieved_source_ids(result) | set(case.expected_source_ids)
        fabricated = [_citation_source(citation) for citation in citations if _citation_source(citation) not in allowed]
        return MetricResult(metric_name=self.metric_name, value=len(fabricated) / len(citations), details={"fabricated": fabricated})


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value)
    if hasattr(value, "model_dump"):
        return set(value.model_dump())
    return set()


CITATION_METRICS: list[Metric] = [
    CitationPresence(),
    CitationCoverage(),
    CitationSourceAccuracy(),
    CitationSupportAccuracy(),
    CitationMetadataCompleteness(),
    FabricatedCitationRate(),
]
