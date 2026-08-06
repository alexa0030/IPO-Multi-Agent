from unittest.mock import patch

from ipo_financial_agent.agents.legal_governance_agent import LegalGovernanceAgent
from ipo_financial_agent.models import PageData
from ipo_financial_agent.research import legal_governance_research_patch


@patch(
    "ipo_financial_agent.agents.legal_governance_agent.search_legal_governance_info",
    return_value=[],
)
def test_legal_agent_creates_page_grounded_review_leads(_search: object) -> None:
    pages = [
        PageData(
            source_file="prospectus.pdf",
            page=88,
            text=(
                "关联交易披露。公司在报告期内向关联方采购服务，相关交易"
                "按照框架协议执行。" * 8
            ),
        ),
        PageData(
            source_file="prospectus.pdf",
            page=120,
            text=(
                "诉讼及处罚。公司目前涉及一项尚未完结的诉讼，管理层认为"
                "不会产生重大不利影响。" * 8
            ),
        ),
    ]

    result = LegalGovernanceAgent().analyze(company="Example", pages=pages)
    patch = legal_governance_research_patch(result)

    assert {item.page_number for item in result.evidence} == {88, 120}
    assert {item.metadata["category"] for item in result.evidence} == {
        "related_party_matters",
        "litigation_and_penalties",
    }
    assert len(patch.findings) == 2
    assert all(item.agent_name == "legal_governance" for item in patch.findings)
    assert all(item.evidence_ids for item in patch.findings)
    assert any("P88" in item.conclusion for item in patch.findings)
    assert all("法律效力" in item.open_questions[0] for item in patch.findings)


@patch(
    "ipo_financial_agent.agents.legal_governance_agent.search_legal_governance_info",
    return_value=[
        {
            "query": "示例公司 审计师 会计差错",
            "topic": "accounting_auditor",
            "title": "监管机构公开通报",
            "content": "公开摘要提及一项需要核实的会计处理事项。",
            "url": "https://example.com/regulatory-notice",
            "source_tier": "official",
            "confidence": 0.95,
        }
    ],
)
def test_legal_agent_routes_external_accounting_lead_with_url(_search: object) -> None:
    result = LegalGovernanceAgent().analyze(company="示例公司", pages=[])
    patch_result = legal_governance_research_patch(result)

    assert result.financial_reporting_integrity
    assert result.evidence[0].source_url == "https://example.com/regulatory-notice"
    finding = patch_result.findings[0]
    assert finding.evidence_strength == "medium"
    assert "accounting_auditor" not in finding.conclusion
    assert "financial_reporting_integrity" in finding.conclusion
    assert "打开并阅读原始 URL" in finding.open_questions[0]
    assert finding.risks == ["待核实核查线索：financial_reporting_integrity"]
