"""Search-provider protocol."""

from __future__ import annotations

from typing import Protocol

from ipo_financial_agent.tools.search.models import SearchQuery, SearchResult


class SearchProvider(Protocol):
    def search(self, query: SearchQuery) -> list[SearchResult]: ...

