"""External search tools used by the market research Agent.

Search unavailability is represented as an empty result set. The production
pipeline must never replace missing external evidence with fabricated data.
"""
from __future__ import annotations

import os
from typing import Any


def search_industry_info(company: str, business_description: str = "") -> list[dict[str, Any]]:
    """Search industry information when a provider is configured."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if api_key:
        return _tavily_search(api_key, company, business_description)
    return []


def search_market_data(company: str) -> dict[str, Any]:
    """Return an explicit unavailable result until a market provider exists."""
    return {
        "company": company,
        "source": "unavailable",
        "available": False,
        "market_cap": None,
        "pe_ratio": None,
        "note": "未配置市场数据源，未生成替代数据。",
    }


def _tavily_search(api_key: str, company: str, business_description: str) -> list[dict[str, Any]]:
    """调用 Tavily API 进行真实搜索。"""
    try:
        import requests
        query = f"{company} 行业 市场规模 竞争格局"
        if business_description:
            query = f"{company} {business_description[:50]} 行业分析"
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title": r.get("title", ""),
                "content": r.get("content", ""),
                "url": r.get("url", ""),
            }
            for r in data.get("results", [])
        ]
    except (OSError, ValueError, KeyError, requests.RequestException) as error:
        print(f"[search_tool] Tavily 搜索失败: {error}")
        return []
