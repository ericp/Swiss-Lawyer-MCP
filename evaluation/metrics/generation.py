"""Grounded generation metrics."""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult, contains_text, get_field, non_applicable, source_text
from evaluation.models import EvaluationCase, EvaluationCaseResult


def _answer_text(result: EvaluationCaseResult) -> str:
    return source_text(result)


def _fact_description(fact: dict) -> str:
    return str(fact.get("description") or fact.get("fact_id") or "")


def _is_insufficient(result: EvaluationCaseResult) -> bool:
    answer = result.generated_answer
    if get_field(answer, "insufficient_context", False):
        return True
    return "does not contain enough information" in _answer_text(result).lower()


class RequiredFactCoverage(Metric):
    metric_name = "required_fact_coverage"
    category = "generation"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        facts = case.expected_answer_facts
        if not facts:
            return non_applicable(self.metric_name, reason="No expected answer facts")
        text = _answer_text(result)
        matched = [_fact_description(fact) for fact in facts if contains_text(text, _fact_description(fact))]
        return MetricResult(metric_name=self.metric_name, value=len(matched) / len(facts), details={"matched": matched})


class ForbiddenFactRate(Metric):
    metric_name = "forbidden_fact_rate"
    category = "generation"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        facts = case.forbidden_answer_facts
        if not facts:
            return non_applicable(self.metric_name, reason="No forbidden answer facts")
        text = _answer_text(result)
        found = [_fact_description(fact) for fact in facts if contains_text(text, _fact_description(fact))]
        return MetricResult(metric_name=self.metric_name, value=len(found) / len(facts), details={"found": found})


class GroundedClaimCoverage(Metric):
    metric_name = "grounded_claim_coverage"
    category = "generation"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        claims = _claim_count(result)
        if claims == 0:
            return non_applicable(self.metric_name, reason="No generated answer claims")
        citation_count = len(result.sources) or len(get_field(result.generated_answer, "cited_sources", []))
        return MetricResult(metric_name=self.metric_name, value=min(1.0, citation_count / claims), details={"claims": claims, "citations": citation_count})


class UnsupportedClaimRate(Metric):
    metric_name = "unsupported_claim_rate"
    category = "generation"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        coverage = GroundedClaimCoverage().compute(case, result)
        if not coverage.applicable or coverage.value is None:
            return non_applicable(self.metric_name, reason=coverage.details.get("reason", "Grounded coverage unavailable"))
        return MetricResult(metric_name=self.metric_name, value=1.0 - coverage.value, details=coverage.details)


class AnswerCompleteness(Metric):
    metric_name = "answer_completeness"
    category = "generation"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        critical = [fact for fact in case.expected_answer_facts if fact.get("importance") == "critical"]
        facts = critical or case.expected_answer_facts
        if not facts:
            return non_applicable(self.metric_name, reason="No expected answer facts")
        text = _answer_text(result)
        matched = [_fact_description(fact) for fact in facts if contains_text(text, _fact_description(fact))]
        return MetricResult(metric_name=self.metric_name, value=len(matched) / len(facts), details={"matched": matched, "critical_only": bool(critical)})


class InsufficientContextAccuracy(Metric):
    metric_name = "insufficient_context_accuracy"
    category = "generation"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        predicted = _is_insufficient(result)
        return MetricResult(metric_name=self.metric_name, value=1.0 if predicted is case.should_abstain else 0.0, details={"expected_abstain": case.should_abstain, "predicted_abstain": predicted})


def _claim_count(result: EvaluationCaseResult) -> int:
    answer = result.generated_answer
    if answer is None:
        return 0
    steps = get_field(answer, "procedure_steps", [])
    notes = get_field(answer, "important_notes", [])
    prose = " ".join(str(get_field(answer, field, "")) for field in ["answer", "explanation"])
    sentence_count = len([part for part in prose.replace("\n", " ").split(".") if part.strip()])
    return max(1, sentence_count + len(steps) + len(notes))


GENERATION_METRICS: list[Metric] = [
    RequiredFactCoverage(),
    ForbiddenFactRate(),
    GroundedClaimCoverage(),
    UnsupportedClaimRate(),
    AnswerCompleteness(),
    InsufficientContextAccuracy(),
]
