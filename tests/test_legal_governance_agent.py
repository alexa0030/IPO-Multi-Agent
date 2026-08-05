from ipo_financial_agent.agents.legal_governance_agent import LegalGovernanceAgent
from ipo_financial_agent.models import PageData
from ipo_financial_agent.research import legal_governance_research_patch


def test_legal_agent_creates_page_grounded_review_leads() -> None:
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
