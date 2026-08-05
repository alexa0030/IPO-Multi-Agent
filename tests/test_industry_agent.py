from unittest.mock import patch

from ipo_financial_agent.agents.industry_agent import IndustryAgent
from ipo_financial_agent.models import PageData


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
    assert result.evidence[0].metadata["independently_verified"] is True
