from ipo_financial_agent.agents.industry_agent import IndustryAgent
from ipo_financial_agent.tools.search_tool import (
    search_industry_info,
    search_market_data,
)


def test_missing_search_provider_never_returns_mock(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("IPO_SEARCH_PROVIDER", "auto")

    assert search_industry_info("Example Holdings") == []
    assert search_market_data("Example Holdings")["source"] == "unavailable"


def test_industry_agent_marks_external_research_unavailable(monkeypatch) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    result = IndustryAgent().analyze(company="Example Holdings")

    assert "未生成行业事实" in result.industry_overview
    assert "稳定增长" not in result.raw_markdown
    assert "mock://" not in result.raw_markdown
