from unittest.mock import patch

from ipo_financial_agent.agents.industry_agent import IndustryAgent
from ipo_financial_agent.models import PageData


class JsonIndustryClient:
    def complete_text(self, **_: object) -> str:
        return """{
          "industry_overview": "发行人披露其服务于工业数字打印市场。",
          "market_growth": "市场增速仍需外部原文复核。",
          "competitors": ["竞争者A"],
          "industry_trends": ["下游数字化"],
          "industry_risks": ["价格竞争"],
          "value_chain": ["上游核心部件—公司控制系统—下游设备商"],
          "customer_industries": ["纺织印花"],
          "competitive_dimensions": ["稳定性、交付和服务"],
          "barriers_to_entry": ["客户验证和切换成本"],
          "growth_drivers": ["海外客户拓展"],
          "expansion_paths": ["工业喷墨新场景"],
          "findings": [
            {"question":"公司的竞争壁垒是什么？","conclusion":"发行人披露客户验证形成切换成本。","evidence_refs":[1],"risks":[],"open_questions":["访谈客户核实切换周期。"]},
            {"question":"无证据判断","conclusion":"模型猜测内容","evidence_refs":[99],"risks":[],"open_questions":[]}
          ]
        }"""


@patch(
    "ipo_financial_agent.agents.industry_agent.search_industry_info",
    return_value=[],
)
def test_offline_industry_analysis_uses_page_grounded_prospectus_claims(
    _search: object,
) -> None:
    pages = [
        PageData(
            source_file="prospectus.pdf",
            page=10,
            text="目录 市场规模 市场份额 竞争格局",
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=82,
            text=(
                "行业概览。全球数字打印市场规模由2023年的100亿元增长至"
                "2028年的160亿元，复合年增长率为9.9%。"
                "市场参与者众多，竞争格局较为分散并存在价格竞争。"
            ),
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=88,
            text="按2025年收入计，公司排名第五，市场份额为5.9%。",
            tables=[],
        ),
    ]

    result = IndustryAgent().analyze(company="测试公司", pages=pages)

    assert "9.9%" in result.market_growth
    assert "5.9%" in result.industry_overview
    assert result.industry_trends
    assert any("尚未取得外部独立来源验证" in item for item in result.industry_risks)
    assert {item.page_number for item in result.evidence} == {82, 88}
    assert all(
        item.metadata["independently_verified"] is False
        for item in result.evidence
    )


@patch(
    "ipo_financial_agent.agents.industry_agent.search_industry_info",
    return_value=[
        {
            "title": "Official statistics",
            "content": "Independent market data",
            "url": "https://example.com/statistics",
            "source_tier": "official",
        }
    ],
)
def test_external_evidence_is_labelled_separately(_search: object) -> None:
    result = IndustryAgent().analyze(company="测试公司", pages=[])

    assert result.evidence[0].source_type == "web"
    assert result.evidence[0].metadata["source_scope"] == "external"
    assert result.evidence[0].metadata["independently_verified"] is False
    assert (
        result.evidence[0].metadata["verification_status"]
        == "search_lead_requires_source_review"
    )


@patch(
    "ipo_financial_agent.agents.industry_agent.search_industry_info",
    return_value=[],
)
def test_llm_industry_findings_must_reference_real_evidence(_search: object) -> None:
    pages = [
        PageData(
            source_file="prospectus.pdf",
            page=88,
            text="行业概览。公司在工业数字打印市场依靠客户验证和服务形成切换成本，市场份额为5.9%。",
            tables=[],
        )
    ]

    result = IndustryAgent(JsonIndustryClient()).analyze(
        company="测试公司", pages=pages
    )

    assert result.value_chain
    assert result.customer_industries == ["纺织印花"]
    assert len(result.structured_findings) == 1
    assert result.structured_findings[0].evidence_ids == [result.evidence[0].evidence_id]
    assert "模型猜测内容" not in result.structured_findings[0].conclusion
