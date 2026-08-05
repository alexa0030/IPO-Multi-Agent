"""Pluggable, source-aware external search."""

from ipo_financial_agent.tools.search.models import SearchQuery, SearchResult
from ipo_financial_agent.tools.search.service import (
    SearchService,
    build_due_diligence_queries,
    classify_source_tier,
)
from ipo_financial_agent.tools.search.tavily import TavilySearchProvider

__all__ = [
    "SearchQuery",
    "SearchResult",
    "SearchService",
    "TavilySearchProvider",
    "build_due_diligence_queries",
    "classify_source_tier",
]

