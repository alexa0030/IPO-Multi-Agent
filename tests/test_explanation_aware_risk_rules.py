from ipo_financial_agent.finance.risk_rules import RiskRuleEngine
from ipo_financial_agent.models import MetricResult


def _gross_margin(period: str, value: float) -> MetricResult:
    return MetricResult(
        metric_id=f"gm_{period}",
        document_id="doc_1",
        metric_name="毛利率",
        metric_code="gross_margin",
        period=period,
        value=value,
        display_value=f"{value:.1%}",
        formula="gross_profit / revenue",
        source_pages=[100],
    )


def test_declining_but_above_30_percent_margin_is_an_observation() -> None:
    findings = RiskRuleEngine().scan(
        "doc_1",
        [
            _gross_margin("2023", 0.39),
            _gross_margin("2024", 0.37),
            _gross_margin("2025", 0.35),
        ],
        [],
    )

    finding = next(item for item in findings if item.rule_code == "gross_margin_decline")
    assert finding.severity == "low"
    assert finding.assessment_status == "observation"
    assert "高于30%" in finding.description
    assert "并购低毛利业务并表" in finding.possible_explanations
    assert "并购前后桥接" in finding.required_evidence


def test_inventory_anomaly_carries_competing_hypotheses() -> None:
    metrics = [
        MetricResult(
            metric_id="rev_2025",
            document_id="doc_1",
            metric_name="收入增长率",
            metric_code="revenue_growth",
            period="2025",
            value=0.10,
            display_value="10.0%",
            formula="growth",
        ),
        MetricResult(
            metric_id="inv_2025",
            document_id="doc_1",
            metric_name="存货增长率",
            metric_code="inventory_growth",
            period="2025",
            value=0.40,
            display_value="40.0%",
            formula="growth",
        ),
    ]

    finding = RiskRuleEngine().scan("doc_1", metrics, [])[0]

    assert finding.assessment_status == "observation"
    assert "并购带入存货" in finding.possible_explanations
    assert "滞销或虚构存货" in finding.possible_explanations
    assert finding.escalation_conditions
