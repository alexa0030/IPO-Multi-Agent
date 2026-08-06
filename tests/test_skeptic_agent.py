from ipo_financial_agent.agents.skeptic import SkepticAgent
from ipo_financial_agent.models_agent import Contradiction, Finding


def test_skeptic_prioritizes_contradictions_and_caps_challenges() -> None:
    contradiction = Contradiction(
        source_1="ProspectusAgent",
        statement_1="Revenue is resilient",
        source_2="FinancialAgent",
        statement_2="Cash conversion is weakening",
        severity="high",
        question="Why is cash conversion diverging from revenue?",
    )
    finding = Finding(
        agent_name="company_business",
        question="How concentrated are customers?",
        conclusion="Disclosure is incomplete.",
        evidence_ids=["ev_1"],
        open_questions=["Obtain the top-five customer schedule."],
    )

    challenges = SkepticAgent().review(
        findings=[finding],
        contradictions=[contradiction],
        open_questions=[
            "Verify market share with an independent source.",
            "Check litigation records.",
            "Find another open question.",
        ],
    )

    assert len(challenges) == 3
    assert challenges[0].severity == "critical"
    assert challenges[0].target_agent == "financial_dd"
    assert challenges[1].challenged_finding_id == finding.finding_id
    assert challenges[2].target_agent == "industry_competition"


def test_skeptic_routes_chinese_financial_and_market_questions() -> None:
    agent = SkepticAgent()

    assert agent._target_for_text("\u6838\u5bf9\u6536\u5165\u4e0e\u73b0\u91d1\u6d41") == "financial_dd"
    assert (
        agent._target_for_text("\u641c\u7d22\u884c\u4e1a\u5e02\u573a\u4efd\u989d")
        == "industry_competition"
    )
    assert agent._target_for_text("\u6838\u67e5\u8bc9\u8bbc\u548c\u76d1\u7ba1\u5904\u7f5a") == "legal_governance"
