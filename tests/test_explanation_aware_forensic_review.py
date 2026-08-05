from ipo_financial_agent.agents.risk_reviewer import RiskReviewerAgent
from ipo_financial_agent.models_agent import FinancialFinding, ProspectusAnalysis


def test_forensic_observation_does_not_become_a_contradiction_or_high_risk() -> None:
    finding = FinancialFinding(
        rule_id="RA-003",
        name="纳税额收入比背离",
        category="revenue_authenticity",
        layer=2,
        severity="high",
        triggered=True,
        description="revenue_growth=36.0%, tax_growth=-8.8%",
        assessment_status="observation",
        possible_explanations=["所得税支付时点差异", "并购并表口径"],
        required_evidence=["所得税费用与已付所得税桥接"],
    )
    prospectus = ProspectusAnalysis(
        company="测试公司",
        business_model="公司报告期内收入持续增长。",
    )

    review = RiskReviewerAgent().review(
        company="测试公司",
        prospectus_analysis=prospectus,
        financial_findings=[finding],
    )

    assert review.contradictions == []
    assert review.risk_level == "Low"
    assert review.risk_matrix[0].category == "financial_observation"
    assert review.risk_matrix[0].probability == "Low"
    assert review.major_risks == []


def test_forensic_finding_defaults_to_observation() -> None:
    finding = FinancialFinding(rule_id="EQ-002", triggered=True)

    assert finding.assessment_status == "observation"
