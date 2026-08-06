"""Adapt the mature financial toolchain into the PRD v2 research contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ipo_financial_agent.models import MetricResult, StatementFact
from ipo_financial_agent.models_agent import FinancialFinding as LegacyFinancialFinding
from ipo_financial_agent.schemas import Evidence, Finding, ResearchTask


def fact_evidence_id(fact_id: str) -> str:
    return f"PDF_{fact_id}"


def metric_evidence_id(metric_id: str) -> str:
    return f"CALC_{metric_id}"


def register_financial_evidence(
    *,
    facts: Iterable[StatementFact],
    metrics: Iterable[MetricResult],
) -> list[Evidence]:
    """Convert deterministic facts first, then calculations with full lineage."""
    fact_items = list(facts)
    metric_items = list(metrics)
    fact_ids = {item.fact_id for item in fact_items}
    evidence: list[Evidence] = []
    for fact in fact_items:
        evidence.append(
            Evidence(
                evidence_id=fact_evidence_id(fact.fact_id),
                source_type="prospectus",
                title=f"{fact.statement_name}｜{fact.item_name}",
                content=(
                    f"{fact.period}：{fact.raw_value}"
                    f"{(' ' + fact.unit) if fact.unit else ''}"
                ),
                page_number=fact.page,
                section=fact.statement_name,
                raw_value=fact.value,
                source_quality="A",
                created_by="financial",
            )
        )
    for metric in metric_items:
        inputs = [
            fact_evidence_id(item)
            for item in metric.source_fact_ids
            if item in fact_ids
        ]
        if not inputs:
            continue
        evidence.append(
            Evidence(
                evidence_id=metric_evidence_id(metric.metric_id),
                source_type="calculation",
                title=f"{metric.metric_name}｜{metric.period}",
                content=f"{metric.metric_name}（{metric.period}）={metric.display_value}",
                formula=metric.formula,
                input_evidence_ids=inputs,
                raw_value=metric.value,
                source_quality="A",
                created_by="financial",
            )
        )
    return evidence


def convert_selling_expense_rule(
    *,
    task: ResearchTask,
    rule_result: LegacyFinancialFinding,
    metrics: Iterable[MetricResult],
) -> Finding:
    """Convert RA-001 into one complete, reviewable Financial Finding."""
    if task.target_agent != "financial":
        raise ValueError("Financial finding requires a financial ResearchTask")
    if rule_result.rule_id != "RA-001" or not rule_result.triggered:
        raise ValueError("expected a triggered RA-001 rule result")
    ratio_metrics = sorted(
        [item for item in metrics if item.metric_code == "selling_expense_ratio"],
        key=lambda item: item.period,
    )
    if len(ratio_metrics) < 2:
        raise ValueError("RA-001 conversion requires at least two period metrics")
    calculation_ids = [metric_evidence_id(item.metric_id) for item in ratio_metrics]
    input_ids = [
        fact_evidence_id(fact_id)
        for metric in ratio_metrics
        for fact_id in metric.source_fact_ids
    ]
    trend = "，".join(
        f"{item.period}年{item.display_value}" for item in ratio_metrics
    )
    severity_map = {
        "critical": "high",
        "high": "high",
        "warning": "medium",
        "info": "low",
    }
    interpretation = rule_result.interpretation.strip() or (
        "销售费用率连续上升表明获客和市场拓展投入增加；是否属于增长投入或效率恶化，"
        "必须结合新增客户、销售人员、新市场收入贡献及同行水平进一步核验。"
    )
    return Finding(
        finding_id="FIN_RA_001",
        task_id=task.task_id,
        agent="financial",
        topic="selling_expense_quality",
        title=rule_result.name,
        statement=f"报告期销售费用率为{trend}，呈连续上升趋势。",
        evidence_ids=list(dict.fromkeys([*input_ids, *calculation_ids])),
        interpretation=interpretation,
        alternative_explanations=list(rule_result.possible_explanations),
        required_checks=list(rule_result.required_evidence),
        cross_check_topics=[
            "customer_growth",
            "market_expansion",
            "peer_selling_expense_ratio",
        ],
        risk_level=severity_map.get(rule_result.severity, "medium"),
        confidence="high" if len(ratio_metrics) >= 3 else "medium",
    )


def select_supported_rule(findings: Iterable[Any]) -> LegacyFinancialFinding:
    """Select the single golden-path rule supported in phase one."""
    for item in findings:
        if getattr(item, "rule_id", "") == "RA-001" and getattr(item, "triggered", False):
            return item
    raise ValueError("golden-path rule RA-001 was not triggered")
