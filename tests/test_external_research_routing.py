from ipo_financial_agent.models_agent import Evidence, Finding, IndustryAnalysis
from ipo_financial_agent.research.ledger_builders import industry_research_patch


def _web_evidence(topic: str, tier: str = "secondary") -> Evidence:
    return Evidence(
        source_type="web",
        title="公开来源标题",
        content="这是搜索服务返回的可追溯摘要，仍需打开原文核验。",
        source_url=f"https://example.com/{topic}",
        confidence=0.55,
        metadata={
            "topic": topic,
            "source_tier": tier,
            "source_scope": "external",
            "independently_verified": False,
        },
    )


def test_adverse_media_search_lead_is_routed_to_legal_governance() -> None:
    evidence = _web_evidence("adverse_media")
    patch = industry_research_patch(
        IndustryAnalysis(company="示例公司", evidence=[evidence])
    )
    finding = next(item for item in patch.findings if item.agent_name == "legal_governance")
    assert finding.evidence_ids == [evidence.evidence_id]
    assert "外部公开信息线索" in finding.conclusion
    assert "打开并阅读原始 URL" in finding.open_questions[0]


def test_industry_search_lead_stays_in_industry_section() -> None:
    evidence = _web_evidence("competitors", tier="official")
    patch = industry_research_patch(
        IndustryAnalysis(company="示例公司", evidence=[evidence])
    )
    finding = next(item for item in patch.findings if item.agent_name == "industry_competition")
    assert finding.evidence_strength == "medium"
    assert finding.evidence_ids == [evidence.evidence_id]


def test_grounded_industry_finding_replaces_duplicate_search_lead() -> None:
    evidence = _web_evidence("competitors", tier="official")
    grounded = Finding(
        agent_name="industry_competition",
        question="竞争壁垒是什么？",
        conclusion="公开来源显示认证周期较长，但仍需阅读全文。",
        evidence_ids=[evidence.evidence_id],
        evidence_strength="medium",
    )
    patch = industry_research_patch(
        IndustryAnalysis(
            company="示例公司",
            structured_findings=[grounded],
            evidence=[evidence],
        )
    )

    assert patch.findings == [grounded]
