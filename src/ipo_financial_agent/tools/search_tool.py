"""Backward-compatible entry points for source-aware external research."""

from __future__ import annotations

import os
from typing import Any

from ipo_financial_agent.tools.search import (
    SearchQuery,
    SearchService,
    TavilySearchProvider,
    build_due_diligence_queries,
)


def search_industry_info(
    company: str,
    business_description: str = "",
) -> list[dict[str, Any]]:
    """Return real, traceable search results or an empty list."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return []
    service = SearchService(TavilySearchProvider(api_key))
    results = service.run(build_due_diligence_queries(company, business_description))
    return [item.model_dump() for item in results]


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
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return []
    service = SearchService(TavilySearchProvider(api_key))
    query = SearchQuery(
        query=f"{company} {question}",
        topic="targeted_followup",
        max_results=5,
    )
    return [item.model_dump() for item in service.run([query])]
