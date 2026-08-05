from __future__ import annotations

import hashlib

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
            metric_map.get(("gross_margin", period))

            if (
                revenue_growth
                and receivable_growth
                and receivable_growth.value is not None
                and revenue_growth.value is not None
            ):
                receivable_gap = receivable_growth.value - revenue_growth.value
                if receivable_gap >= 0.20:
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

            if (
                revenue_growth
                and inventory_growth
                and inventory_growth.value is not None
                and revenue_growth.value is not None
            ):
                inventory_gap = inventory_growth.value - revenue_growth.value
                if inventory_gap >= 0.20:
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
            ending_margin = gm[-1].value
            findings.append(
                self._finding(
                    document_id,
                    "gross_margin_decline",
                    period,
                    "盈利能力",
                    "毛利率连续下降",
                    "low" if ending_margin >= 0.30 else "medium",
                    (
                        f"最近三个期间毛利率依次为{gm[-3].display_value}、"
                        f"{gm[-2].display_value}、{gm[-1].display_value}。"
                        + (
                            "期末毛利率仍高于30%，目前作为趋势观察项，"
                            "不能仅凭下降判断盈利能力恶化。"
                            if ending_margin >= 0.30
                            else "期末毛利率低于30%，需进一步核实变化原因。"
                        )
                    ),
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
        hypotheses = {
            "receivable_vs_revenue": (
                ["销售增长及信用期扩张", "客户结构变化", "并购带入应收", "提前确认或虚构收入"],
                ["客户明细及账龄", "期后回款", "信用政策变化", "并购口径桥接"],
                ["期后长期未回款", "异常第三方回款", "合同物流发票无法闭环"],
            ),
            "inventory_vs_revenue": (
                ["扩产或主动备货", "原材料价格预期", "并购带入存货", "滞销或虚构存货"],
                ["存货构成及库龄", "期后销售", "跌价测试", "产量销量及并购口径桥接"],
                ["长库龄上升且跌价不足", "盘点差异", "采购产量销量无法勾稽"],
            ),
            "weak_cash_conversion": (
                ["扩张期营运资金投入", "研发或资本开支增加", "并购整合", "回款恶化或利润失真"],
                ["现金流变动桥接", "应收存货变化", "并购现金流", "研发及资本开支明细"],
                ["持续多年偏弱且无扩张证据", "利润增长但回款持续恶化"],
            ),
            "low_current_ratio": (
                ["短期融资支持扩张", "并购融资", "季节性采购", "短债长投"],
                ["债务到期表", "授信证明", "受限现金", "未来12个月资金计划"],
                ["大额债务集中到期", "授信不可续期", "经营现金无法覆盖偿债"],
            ),
            "high_debt_ratio": (
                ["扩产融资", "并购融资", "租赁负债增加", "经营亏损侵蚀权益"],
                ["有息负债明细", "资金用途", "利息覆盖", "担保及契约条款"],
                ["资金流向关联方", "利息覆盖不足", "隐性担保或交叉违约"],
            ),
            "gross_margin_decline": (
                ["产品结构变化", "并购低毛利业务并表", "原材料涨价", "价格竞争或良率下降"],
                ["分产品收入与毛利率", "并购前后桥接", "售价单位成本及良率"],
                ["公司解释无定量桥接", "核心产品毛利率同步明显下降", "同行稳定而公司恶化"],
            ),
        }
        possible, required, escalation = hypotheses.get(rule_code, ([], [], []))
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
            assessment_status="observation",
            possible_explanations=possible,
            required_evidence=required,
            escalation_conditions=escalation,
        )
