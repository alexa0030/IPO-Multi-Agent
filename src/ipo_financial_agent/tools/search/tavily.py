"""Tavily implementation of the search-provider protocol."""

from __future__ import annotations

import requests

from ipo_financial_agent.tools.search.models import SearchQuery, SearchResult


class TavilySearchProvider:
    def __init__(self, api_key: str, timeout_seconds: int = 20) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: SearchQuery) -> list[SearchResult]:
        payload = {
            "api_key": self.api_key,
            "query": query.query,
            "search_depth": "advanced",
            "max_results": query.max_results,
            "include_raw_content": False,
        }
        if query.domains:
            payload["include_domains"] = query.domains
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as error:
            print(f"[search] Tavily query failed ({query.topic}): {error}")
            return []

        output: list[SearchResult] = []
        for item in data.get("results", []):
            try:
                output.append(
                    SearchResult(
                        query=query.query,
                        topic=query.topic,
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        url=item.get("url", ""),
                        published_at=item.get("published_date"),
                    )
                )
            except ValueError:
                continue
        return output
