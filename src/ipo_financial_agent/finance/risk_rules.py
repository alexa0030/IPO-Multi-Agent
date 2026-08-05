from __future__ import annotations

import hashlib
from collections import defaultdict

from ipo_financial_agent.models import MetricResult, RiskFinding, StatementFact


def _risk_id(document_id: str, rule_code: str, period: str) -> str:
    seed = f"{document_id}|{rule_code}|{period}"
    return "risk_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:14]


class RiskRuleEngine:
    """可解释规则初筛。命中规则不是最终结论，由分析Agent审慎解释。"""

    def scan(
        self,
        document_id: str,
        metrics: list[MetricResult],
        facts: list[StatementFact],
    ) -> list[RiskFinding]:
        metric_map: dict[tuple[str, str], MetricResult] = {
            (metric.metric_code, metric.period): metric for metric in metrics if metric.value is not None
        }
        periods = sorted({metric.period for metric in metrics})
        findings: list[RiskFinding] = []

        for period in periods:
            revenue_growth = metric_map.get(("revenue_growth", period))
            receivable_growth = metric_map.get(("receivable_growth", period))
            inventory_growth = metric_map.get(("inventory_growth", period))
            ocf_ratio = metric_map.get(("ocf_to_net_profit", period))
            current_ratio = metric_map.get(("current_ratio", period))
            debt_ratio = metric_map.get(("debt_ratio", period))
            gross_margin = metric_map.get(("gross_margin", period))

            if revenue_growth and receivable_growth and receivable_growth.value is not None and revenue_growth.value is not None:
                if receivable_growth.value - revenue_growth.value >= 0.20:
                    findings.append(
                        self._finding(
                            document_id,
                            "receivable_vs_revenue",
                            period,
                            "收入质量",
                            "应收账款增速明显高于收入增速",
                            "medium",
                            f"应收账款增速为{receivable_growth.display_value}，收入增速为{revenue_growth.display_value}，需核实信用政策、期后回款及收入兑现情况。",
                            [receivable_growth, revenue_growth],
                        )
                    )

            if revenue_growth and inventory_growth and inventory_growth.value is not None and revenue_growth.value is not None:
                if inventory_growth.value - revenue_growth.value >= 0.20:
                    findings.append(
                        self._finding(
                            document_id,
                            "inventory_vs_revenue",
                            period,
                            "资产质量",
                            "存货增速明显高于收入增速",
                            "medium",
                            f"存货增速为{inventory_growth.display_value}，收入增速为{revenue_growth.display_value}，需核实备货合理性、库龄及跌价准备。",
                            [inventory_growth, revenue_growth],
                        )
                    )

            if ocf_ratio and ocf_ratio.value is not None and ocf_ratio.value < 0.8:
                severity = "high" if ocf_ratio.value < 0.5 else "medium"
                findings.append(
                    self._finding(
                        document_id,
                        "weak_cash_conversion",
                        period,
                        "现金流",
                        "经营现金流对净利润覆盖偏弱",
                        severity,
                        f"净现比为{ocf_ratio.display_value}，需结合应收、存货及一次性项目核实利润含金量。",
                        [ocf_ratio],
                    )
                )

            if current_ratio and current_ratio.value is not None and current_ratio.value < 1.2:
                findings.append(
                    self._finding(
                        document_id,
                        "low_current_ratio",
                        period,
                        "流动性",
                        "流动比率偏低",
                        "high" if current_ratio.value < 1.0 else "medium",
                        f"流动比率为{current_ratio.display_value}，需关注短期偿债安排和可动用现金。",
                        [current_ratio],
                    )
                )

            if debt_ratio and debt_ratio.value is not None and debt_ratio.value > 0.65:
                findings.append(
                    self._finding(
                        document_id,
                        "high_debt_ratio",
                        period,
                        "偿债能力",
                        "资产负债率较高",
                        "high" if debt_ratio.value > 0.80 else "medium",
                        f"资产负债率为{debt_ratio.display_value}，需核实有息负债、担保、到期结构及利息负担。",
                        [debt_ratio],
                    )
                )

        # 连续毛利率下降
        gm = sorted(
            [metric for metric in metrics if metric.metric_code == "gross_margin" and metric.value is not None],
            key=lambda item: item.period,
        )
        if len(gm) >= 3 and gm[-3].value > gm[-2].value > gm[-1].value:
            period = gm[-1].period
            findings.append(
                self._finding(
                    document_id,
                    "gross_margin_decline",
                    period,
                    "盈利能力",
                    "毛利率连续下降",
                    "medium",
                    f"最近三个期间毛利率依次为{gm[-3].display_value}、{gm[-2].display_value}、{gm[-1].display_value}，需核实产品结构、售价和成本变化。",
                    gm[-3:],
                )
            )

        return findings

    @staticmethod
    def _finding(
        document_id: str,
        rule_code: str,
        period: str,
        category: str,
        title: str,
        severity: str,
        description: str,
        evidence_metrics: list[MetricResult],
    ) -> RiskFinding:
        return RiskFinding(
            risk_id=_risk_id(document_id, rule_code, period),
            document_id=document_id,
            category=category,
            title=title,
            severity=severity,
            description=description,
            evidence_metric_ids=[metric.metric_id for metric in evidence_metrics],
            evidence_fact_ids=sorted(
                {fact_id for metric in evidence_metrics for fact_id in metric.source_fact_ids}
            ),
            source_pages=sorted(
                {page for metric in evidence_metrics for page in metric.source_pages}
            ),
            rule_code=rule_code,
        )
