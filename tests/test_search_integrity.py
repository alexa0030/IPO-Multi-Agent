from ipo_financial_agent.agents.industry_agent import IndustryAgent
from ipo_financial_agent.tools.search_tool import (
    search_industry_info,
    search_legal_governance_info,
    search_market_data,
)
from ipo_financial_agent.tools.search import SearchQuery, SearchResult


class CapturingProvider:
    def __init__(self) -> None:
        self.topics: list[str] = []

    def search(self, query: SearchQuery) -> list[SearchResult]:
        self.topics.append(query.topic)
        return []


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


def test_industry_search_budget_is_not_consumed_by_legal_queries(monkeypatch) -> None:
    provider = CapturingProvider()
    monkeypatch.setattr(
        "ipo_financial_agent.tools.search_tool._configured_provider",
        lambda: (provider, "capture", "test"),
    )
    monkeypatch.setenv("IPO_SEARCH_MAX_QUERIES", "8")

    search_industry_info("示例公司", "工业软件")

    assert set(provider.topics) == {
        "industry",
        "competitors",
        "customers_suppliers",
        "policy",
    }
    assert "regulatory" not in provider.topics


def test_legal_search_has_an_independent_query_budget(monkeypatch) -> None:
    provider = CapturingProvider()
    monkeypatch.setattr(
        "ipo_financial_agent.tools.search_tool._configured_provider",
        lambda: (provider, "capture", "test"),
    )
    monkeypatch.setenv("IPO_LEGAL_SEARCH_MAX_QUERIES", "8")

    search_legal_governance_info("示例公司")

    assert set(provider.topics) == {
        "hkex_filings",
        "regulatory",
        "corporate_registry",
        "litigation",
        "controller_related_parties",
        "accounting_auditor",
        "financing_debt",
        "adverse_media",
    }
    assert "industry" not in provider.topics
