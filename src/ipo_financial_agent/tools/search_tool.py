"""Backward-compatible entry points for source-aware external research."""

from __future__ import annotations

import os
from typing import Any

from ipo_financial_agent.tools.search import (
    SearchQuery,
    SearchService,
    TavilySearchProvider,
    DDGSSearchProvider,
    build_due_diligence_queries,
)


def _configured_provider() -> tuple[Any | None, str, str]:
    """Prefer predictable API search; fall back to a no-key demo provider."""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if api_key:
        return TavilySearchProvider(api_key), "tavily", "free_quota"
    # DDGS is deliberately opt-in.  Some GPU-cloud egress networks block or
    # throttle public search engines, which can turn a free query into a long
    # pipeline stall.  It remains useful for local demos where connectivity is
    # known to work.
    if os.getenv("IPO_SEARCH_PROVIDER", "").strip().lower() != "ddgs":
        return None, "unavailable", "unavailable"
    try:
        import ddgs  # noqa: F401
    except ImportError:
        return None, "unavailable", "unavailable"
    return DDGSSearchProvider(), "ddgs", "free_best_effort"


def search_industry_info(
    company: str,
    business_description: str = "",
) -> list[dict[str, Any]]:
    """Return real, traceable search results or an empty list."""
    provider, provider_name, cost_mode = _configured_provider()
    if provider is None:
        return []
    max_queries = max(1, int(os.getenv("IPO_SEARCH_MAX_QUERIES", "12")))
    service = SearchService(provider)
    report = service.run_report(
        build_due_diligence_queries(company, business_description),
        provider_name=provider_name,
        cost_mode=cost_mode,
        max_queries=max_queries,
    )
    return [
        {
            **item.model_dump(),
            "search_provider": report.provider,
            "search_cost_mode": report.cost_mode,
            "covered_topics": report.covered_topics,
            "missing_topics": report.missing_topics,
        }
        for item in report.results
    ]


def search_market_data(company: str) -> dict[str, Any]:
    """Market-data integration is explicit; no placeholder values are invented."""
    return {
        "company": company,
        "source": "unavailable",
        "available": False,
        "market_cap": None,
        "pe_ratio": None,
        "note": "未配置结构化市场数据源，未生成替代数据。",
    }


def search_targeted_followup(company: str, question: str) -> list[dict[str, Any]]:
    """Run one challenge-specific query when a provider is configured."""
    provider, provider_name, cost_mode = _configured_provider()
    if provider is None:
        return []
    service = SearchService(provider)
    query = SearchQuery(
        query=f"{company} {question}",
        topic="targeted_followup",
        max_results=5,
    )
    report = service.run_report(
        [query], provider_name=provider_name, cost_mode=cost_mode, max_queries=1
    )
    return [item.model_dump() for item in report.results]
