"""No-key, best-effort metasearch provider for the public GitHub demo."""

from __future__ import annotations

from urllib.parse import urlparse

from ipo_financial_agent.tools.search.models import SearchQuery, SearchResult


class DDGSSearchProvider:
    """Use ``ddgs`` lazily so the core package does not require it."""

    def __init__(self, timeout_seconds: int = 12, backend: str = "auto") -> None:
        self.timeout_seconds = timeout_seconds
        self.backend = backend

    def search(self, query: SearchQuery) -> list[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError:
            return []

        search_text = query.query
        if query.domains:
            domain_clause = " OR ".join(f"site:{domain}" for domain in query.domains)
            search_text = f"{search_text} ({domain_clause})"
        try:
            rows = DDGS(timeout=self.timeout_seconds).text(
                search_text,
                region="cn-zh",
                safesearch="moderate",
                max_results=query.max_results,
                backend=self.backend,
            )
        except Exception as error:  # provider/network failures must not break DD
            print(f"[search] DDGS query failed ({query.topic}): {error}")
            return []

        output: list[SearchResult] = []
        for row in rows or []:
            url = row.get("href") or row.get("url") or ""
            try:
                output.append(
                    SearchResult(
                        query=query.query,
                        topic=query.topic,
                        title=row.get("title", ""),
                        content=row.get("body") or row.get("content") or "",
                        url=url,
                        publisher=urlparse(url).hostname or "",
                        provider="ddgs",
                    )
                )
            except ValueError:
                continue
        return output
