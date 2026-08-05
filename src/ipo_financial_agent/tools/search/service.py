"""Query planning, source grading and deduplication for IPO research."""

from __future__ import annotations

from urllib.parse import urlparse

from ipo_financial_agent.tools.search.models import SearchQuery, SearchResult
from ipo_financial_agent.tools.search.provider import SearchProvider

OFFICIAL_DOMAINS = {
    "hkexnews.hk",
    "hkex.com.hk",
    "sfc.hk",
    "cr.gov.hk",
    "judiciary.hk",
}


def classify_source_tier(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if any(host == domain or host.endswith(f".{domain}") for domain in OFFICIAL_DOMAINS):
        return "official"
    return "secondary"


def build_due_diligence_queries(
    company: str,
    business_description: str = "",
) -> list[SearchQuery]:
    context = business_description[:80].strip()
    industry_query = f"{company} {context} 行业 市场规模 竞争格局".strip()
    return [
        SearchQuery(
            query=f"{company} 申请版本 招股书 上市文件",
            topic="hkex_filings",
            domains=["hkexnews.hk", "hkex.com.hk"],
        ),
        SearchQuery(
            query=f"{company} 监管 纪律 执法",
            topic="regulatory",
            domains=["sfc.hk"],
        ),
        SearchQuery(
            query=f"{company} 公司登记 董事",
            topic="corporate_registry",
            domains=["cr.gov.hk"],
        ),
        SearchQuery(
            query=f"{company} 诉讼 判决",
            topic="litigation",
            domains=["judiciary.hk"],
        ),
        SearchQuery(query=industry_query, topic="industry"),
        SearchQuery(
            query=f"{company} 负面新闻 处罚 诉讼",
            topic="adverse_media",
        ),
    ]


class SearchService:
    def __init__(self, provider: SearchProvider) -> None:
        self.provider = provider

    def run(self, queries: list[SearchQuery]) -> list[SearchResult]:
        results: dict[str, SearchResult] = {}
        for query in queries:
            for item in self.provider.search(query):
                item.source_tier = classify_source_tier(item.url)
                item.confidence = 0.9 if item.source_tier == "official" else 0.55
                previous = results.get(item.url)
                if previous is None or len(item.content) > len(previous.content):
                    results[item.url] = item
        return list(results.values())

