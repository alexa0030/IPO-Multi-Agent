from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from ipo_financial_agent.models import MetricResult, StatementFact


def _period_sort_key(period: str) -> tuple[int, ...]:
    values = [int(value) for value in re.findall(r"\d+", period)]
    if not values:
        return (9999, 99, 99)
    while len(values) < 3:
        values.append(12 if len(values) == 1 else 31)
    return tuple(values[:3])


def _metric_id(document_id: str, code: str, period: str) -> str:
    seed = f"{document_id}|{code}|{period}"
    return "metric_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:14]


def _format_percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _format_ratio(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}x"


class MetricEngine:
    """只用已抽取事实计算指标，不调用大模型。"""

    def calculate(
        self,
        document_id: str,
        facts: list[StatementFact],
        reporting_entity: str | None = None,
    ) -> list[MetricResult]:
        issuer = reporting_entity or next((fact.company for fact in facts if fact.company), None)
        by_tag: dict[str, dict[str, StatementFact]] = defaultdict(dict)
        for fact in facts:
            if fact.value is None or fact.canonical_tag == "other":
                continue
            if issuer and fact.reporting_entity and fact.reporting_entity != issuer:
                continue
            current = by_tag[fact.canonical_tag].get(fact.period)
            if current is None or self._fact_priority(fact) > self._fact_priority(current):
                by_tag[fact.canonical_tag][fact.period] = fact

        periods = sorted(
            {period for values in by_tag.values() for period in values},
            key=_period_sort_key,
        )
        metrics: list[MetricResult] = []

        metrics.extend(self._growth_metrics(document_id, by_tag, "revenue", "收入增长率", "revenue_growth"))
        metrics.extend(self._growth_metrics(document_id, by_tag, "net_profit", "净利润增长率", "net_profit_growth"))
        metrics.extend(self._growth_metrics(document_id, by_tag, "trade_receivable", "应收账款增长率", "receivable_growth"))
        metrics.extend(self._growth_metrics(document_id, by_tag, "inventory", "存货增长率", "inventory_growth"))

        for period in periods:
            metrics.extend(
                filter(
                    None,
                    [
                        self._ratio_metric(document_id, by_tag, period, "gross_profit", "revenue", "毛利率", "gross_margin", "毛利/收入", _format_percent),
                        self._ratio_metric(document_id, by_tag, period, "net_profit", "revenue", "净利率", "net_margin", "净利润/收入", _format_percent),
                        self._ratio_metric(document_id, by_tag, period, "selling_expense", "revenue", "销售费用率", "selling_expense_ratio", "销售费用/收入", _format_percent, absolute_numerator=True),
                        self._ratio_metric(document_id, by_tag, period, "administrative_expense", "revenue", "管理费用率", "administrative_expense_ratio", "管理费用/收入", _format_percent, absolute_numerator=True),
                        self._ratio_metric(document_id, by_tag, period, "research_expense", "revenue", "研发费用率", "research_expense_ratio", "研发费用/收入", _format_percent, absolute_numerator=True),
                        self._ratio_metric(document_id, by_tag, period, "operating_cash_flow", "net_profit", "净现比", "ocf_to_net_profit", "经营现金流/净利润", _format_ratio),
                        self._ratio_metric(document_id, by_tag, period, "current_assets", "current_liabilities", "流动比率", "current_ratio", "流动资产/流动负债", _format_ratio),
                        self._debt_ratio(document_id, by_tag, period),
                        self._cash_short_debt(document_id, by_tag, period),
                    ],
                )
            )

        return sorted(metrics, key=lambda item: (_period_sort_key(item.period), item.metric_code))

    @staticmethod
    def _fact_priority(fact: StatementFact) -> tuple[float, int, int]:
        """Prefer issuer consolidated facts, then the earliest primary statement.

        Prospectuses may append parent-company or acquired-subsidiary statements
        after the issuer accounts.  Page order is a deterministic tie-breaker;
        ratio inputs still retain source_table_id for lineage inspection.
        """
        scope = fact.entity_scope or ""
        scope_priority = 2 if scope == "集团/合并" else 1 if scope else 0
        return (fact.confidence, scope_priority, -fact.page)

    def _growth_metrics(
        self,
        document_id: str,
        by_tag: dict[str, dict[str, StatementFact]],
        tag: str,
        name: str,
        code: str,
    ) -> list[MetricResult]:
        facts = sorted(by_tag.get(tag, {}).values(), key=lambda item: _period_sort_key(item.period))
        results: list[MetricResult] = []
        for previous, current in zip(facts, facts[1:]):
            if previous.value in (None, 0) or current.value is None:
                continue
            value = (current.value - previous.value) / abs(previous.value)
            results.append(
                MetricResult(
                    metric_id=_metric_id(document_id, code, current.period),
                    document_id=document_id,
                    metric_name=name,
                    metric_code=code,
                    period=current.period,
                    value=value,
                    display_value=_format_percent(value),
                    formula="(本期-上期)/|上期|",
                    source_fact_ids=[previous.fact_id, current.fact_id],
                    source_pages=sorted({previous.page, current.page}),
                )
            )
        return results

    def _ratio_metric(
        self,
        document_id: str,
        by_tag: dict[str, dict[str, StatementFact]],
        period: str,
        numerator_tag: str,
        denominator_tag: str,
        name: str,
        code: str,
        formula: str,
        formatter,
        absolute_numerator: bool = False,
    ) -> MetricResult | None:
        numerator = by_tag.get(numerator_tag, {}).get(period)
        denominator = by_tag.get(denominator_tag, {}).get(period)
        if numerator is None or denominator is None or denominator.value in (None, 0) or numerator.value is None:
            return None
        numerator_value = abs(numerator.value) if absolute_numerator else numerator.value
        value = numerator_value / denominator.value
        return MetricResult(
            metric_id=_metric_id(document_id, code, period),
            document_id=document_id,
            metric_name=name,
            metric_code=code,
            period=period,
            value=value,
            display_value=formatter(value),
            formula=formula,
            source_fact_ids=[numerator.fact_id, denominator.fact_id],
            source_pages=sorted({numerator.page, denominator.page}),
        )

    def _debt_ratio(
        self,
        document_id: str,
        by_tag: dict[str, dict[str, StatementFact]],
        period: str,
    ) -> MetricResult | None:
        liabilities = by_tag.get("total_liabilities", {}).get(period)
        assets = by_tag.get("total_assets", {}).get(period)
        if not liabilities or not assets or liabilities.value is None or assets.value in (None, 0):
            return None
        value = liabilities.value / assets.value
        return MetricResult(
            metric_id=_metric_id(document_id, "debt_ratio", period),
            document_id=document_id,
            metric_name="资产负债率",
            metric_code="debt_ratio",
            period=period,
            value=value,
            display_value=_format_percent(value),
            formula="总负债/总资产",
            source_fact_ids=[liabilities.fact_id, assets.fact_id],
            source_pages=sorted({liabilities.page, assets.page}),
        )

    def _cash_short_debt(
        self,
        document_id: str,
        by_tag: dict[str, dict[str, StatementFact]],
        period: str,
    ) -> MetricResult | None:
        cash = by_tag.get("cash", {}).get(period)
        short_debt = by_tag.get("short_term_borrowing", {}).get(period)
        if not cash or not short_debt or cash.value is None or short_debt.value in (None, 0):
            return None
        value = cash.value / short_debt.value
        return MetricResult(
            metric_id=_metric_id(document_id, "cash_short_debt", period),
            document_id=document_id,
            metric_name="现金短债比",
            metric_code="cash_short_debt",
            period=period,
            value=value,
            display_value=_format_ratio(value),
            formula="货币资金/短期借款",
            source_fact_ids=[cash.fact_id, short_debt.fact_id],
            source_pages=sorted({cash.page, short_debt.page}),
        )
