from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ipo_financial_agent.models import MetricResult, StatementFact
from ipo_financial_agent.models_agent import FinancialFinding
from ipo_financial_agent.schemas import (
    ManagerContext,
    ManagerFinancialSummary,
    ManagerObservation,
    ManagerTrendPoint,
)


def _compact(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _page_text(pages: list[Any], keywords: tuple[str, ...], limit: int) -> str:
    for page in pages:
        text = getattr(page, "text", "")
        if any(word in text for word in keywords):
            return _compact(text, limit)
    return ""


def _metric_points(metrics: list[MetricResult], code: str) -> tuple[ManagerTrendPoint, ...]:
    return tuple(
        ManagerTrendPoint(
            name=item.metric_name,
            period=item.period,
            value=item.value,
            display_value=item.display_value,
        )
        for item in sorted(metrics, key=lambda value: value.period)
        if item.metric_code == code and item.status == "ok"
    )


def _fact_points(
    facts: Iterable[StatementFact], tag: str, name: str
) -> tuple[ManagerTrendPoint, ...]:
    selected: dict[str, StatementFact] = {}
    for item in facts:
        if item.canonical_tag != tag or item.value is None:
            continue
        current = selected.get(item.period)
        if current is None or (item.confidence, -item.page, item.fact_id) > (
            current.confidence, -current.page, current.fact_id
        ):
            selected[item.period] = item
    return tuple(
        ManagerTrendPoint(
            name=name,
            period=period,
            value=item.value,
            display_value=f"{item.raw_value}{(' ' + item.unit) if item.unit else ''}",
        )
        for period, item in sorted(selected.items())
    )


def build_manager_context(
    *, company_name: str, pages: list[Any], section_hits: list[Any],
    facts: Iterable[StatementFact], metrics: Iterable[MetricResult],
    forensic_results: Iterable[FinancialFinding],
) -> ManagerContext:
    """Serialize a small immutable context from deterministic outputs only."""
    fact_items = list(facts)
    metric_items = list(metrics)
    outlines = tuple(dict.fromkeys(
        _compact(getattr(item, "title", ""), 120)
        for item in section_hits if getattr(item, "title", "")
    ))[:40]
    balance_points = tuple(
        point
        for tag, name in (
            ("cash", "现金"), ("trade_receivable", "应收账款"),
            ("inventory", "存货"), ("total_assets", "总资产"),
            ("total_liabilities", "总负债"),
        )
        for point in _fact_points(fact_items, tag, name)[-2:]
    )
    summary = ManagerFinancialSummary(
        reporting_periods=tuple(sorted({item.period for item in fact_items})),
        revenue_trend=_fact_points(fact_items, "revenue", "营业收入"),
        gross_margin_trend=_metric_points(metric_items, "gross_margin"),
        net_profit_trend=_fact_points(fact_items, "net_profit", "净利润"),
        operating_cash_flow_trend=_fact_points(
            fact_items, "operating_cash_flow", "经营活动现金流"
        ),
        balance_sheet_highlights=balance_points,
        triggered_observations=tuple(
            ManagerObservation(
                rule_id=item.rule_id,
                name=item.name,
                severity=item.severity,
                description=item.description,
            )
            for item in forensic_results if item.triggered
        ),
    )
    return ManagerContext(
        company_name=company_name,
        company_overview=_page_text(
            pages, ("公司资料", "概览", "Overview", "COMPANY"), 1200
        ),
        business_summary=_page_text(
            pages, ("业务模式", "我们的业务", "Business Model", "BUSINESS"), 1600
        ),
        document_outline=outlines,
        risk_factor_summary=tuple(
            filter(None, (
                _page_text(pages, ("风险因素", "RISK FACTORS"), 1200),
            ))
        ),
        financial_summary=summary,
    )
