from __future__ import annotations

from pydantic import BaseModel, Field

from .models import EvalCase, ExpectedMetric


class EvaluationScore(BaseModel):
    verified_metric_count: int = 0
    metric_matches: int = 0
    metric_accuracy: float | None = None
    verified_finding_count: int = 0
    finding_matches: int = 0
    finding_partial_matches: int = 0
    finding_recall: float | None = None
    finding_weighted_score: float | None = None
    evidence_page_accuracy: float | None = None
    unsupported_finding_rate: float | None = None
    details: list[str] = Field(default_factory=list)


def _metric_matches(expected: ExpectedMetric, predicted: dict) -> bool:
    if str(predicted.get("metric_code")) != expected.metric_code:
        return False
    if str(predicted.get("period")) != expected.period:
        return False
    try:
        value = float(predicted["value"])
    except (KeyError, TypeError, ValueError):
        return False
    allowed = (
        expected.tolerance
        if expected.tolerance_mode == "absolute"
        else expected.tolerance * max(abs(expected.value), 1.0)
    )
    return abs(value - expected.value) <= allowed


def _risk_distance(expected: str, predicted: str | None) -> int:
    levels = {"low": 0, "medium": 1, "high": 2}
    if predicted not in levels:
        return 99
    return abs(levels[expected] - levels[predicted])


def score_prediction(case: EvalCase, prediction: dict) -> EvaluationScore:
    metrics = list(prediction.get("metrics", []))
    findings = list(prediction.get("findings", []))
    gold_metrics = [x for x in case.expected_metrics if x.status == "verified"]
    gold_findings = [x for x in case.expected_findings if x.status == "verified"]

    metric_matches = sum(
        any(_metric_matches(expected, item) for item in metrics)
        for expected in gold_metrics
    )
    finding_matches = 0
    partial_matches = 0
    page_matches = 0
    for expected in gold_findings:
        candidates = [x for x in findings if x.get("topic") == expected.topic]
        exact = [
            item
            for item in candidates
            if _risk_distance(expected.risk_level, item.get("risk_level")) == 0
        ]
        adjacent = [
            item
            for item in candidates
            if _risk_distance(expected.risk_level, item.get("risk_level")) == 1
        ]
        if exact:
            finding_matches += 1
        elif adjacent or candidates:
            partial_matches += 1
        if any(set(x.get("pages", [])) & set(expected.pages) for x in candidates):
            page_matches += 1

    unsupported = sum(not item.get("evidence_ids") for item in findings)
    return EvaluationScore(
        verified_metric_count=len(gold_metrics),
        metric_matches=metric_matches,
        metric_accuracy=metric_matches / len(gold_metrics) if gold_metrics else None,
        verified_finding_count=len(gold_findings),
        finding_matches=finding_matches,
        finding_partial_matches=partial_matches,
        finding_recall=(finding_matches + partial_matches) / len(gold_findings)
        if gold_findings
        else None,
        finding_weighted_score=(finding_matches + 0.5 * partial_matches)
        / len(gold_findings)
        if gold_findings
        else None,
        evidence_page_accuracy=page_matches / len(gold_findings) if gold_findings else None,
        unsupported_finding_rate=unsupported / len(findings) if findings else 0.0,
    )
