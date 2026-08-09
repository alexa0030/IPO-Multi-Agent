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
from ipo_financial_agent.tools.search.fetcher import fetch_source
from ipo_financial_agent.tools.search.models import SearchQuery


def _configured_provider() -> tuple[Any | None, str, str]:
    mode = os.getenv("IPO_SEARCH_PROVIDER", "auto").strip().lower()
    if mode in {"off", "none", "disabled"}:
        return None, "unavailable", "unavailable"
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if api_key and mode in {"auto", "tavily"}:
        return TavilySearchProvider(api_key), "tavily", "free_quota"
    if mode != "ddgs":
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
    """Return industry-scoped, traceable search results or an empty list.

    Legal and governance searches use a separate budget.  Previously this
    function submitted the whole due-diligence plan, so the P0 legal queries
    consumed the query cap before any industry or competitor query ran.
    """
    provider, provider_name, cost_mode = _configured_provider()
    if provider is None:
        return []
    max_queries = max(1, int(os.getenv("IPO_SEARCH_MAX_QUERIES", "12")))
    if provider_name == "ddgs":
        # Public engines throttle cloud IPs; keep the free fallback bounded.
        max_queries = min(max_queries, 3)
    industry_topics = {
        "industry",
        "competitors",
        "customers_suppliers",
        "policy",
        "downstream_demand",
        "value_chain",
        "technology_standards",
        "comparable_companies",
        "export_market",
    }
    queries = [
        item
        for item in build_due_diligence_queries(company, business_description)
        if item.topic in industry_topics
    ]
    report = SearchService(provider).run_report(
        queries,
        provider_name=provider_name,
        cost_mode=cost_mode,
        max_queries=max_queries,
    )
    output: list[dict[str, Any]] = []
    max_sources = max(1, int(os.getenv("IPO_SEARCH_MAX_FETCHED_SOURCES", "30")))
    for item in report.results[:max_sources]:
        lead = item.model_dump()
        try:
            fetched = fetch_source(item.url)
        except Exception as error:
            lead["fetch_error"] = f"{type(error).__name__}: {error}"
            continue
        lead.update(fetched)
        lead.update(
            {
                "search_provider": report.provider,
                "search_cost_mode": report.cost_mode,
                "covered_topics": report.covered_topics,
                "missing_topics": report.missing_topics,
                "source_scope": "external",
                "verification_status": "fetched_source_pending_claim_match",
            }
        )
        output.append(lead)
    return output


def search_legal_governance_info(company: str) -> list[dict[str, Any]]:
    """Run the legal/governance public-information plan on its own budget."""
    provider, provider_name, cost_mode = _configured_provider()
    if provider is None:
        return []
    legal_topics = {
        "hkex_filings",
        "regulatory",
        "corporate_registry",
        "litigation",
        "controller_related_parties",
        "accounting_auditor",
        "financing_debt",
        "adverse_media",
        "employment_compliance",
        "intellectual_property",
    }
    queries = [
        item
        for item in build_due_diligence_queries(company)
        if item.topic in legal_topics
    ]
    max_queries = max(1, int(os.getenv("IPO_LEGAL_SEARCH_MAX_QUERIES", "6")))
    if provider_name == "ddgs":
        max_queries = min(max_queries, 3)
    report = SearchService(provider).run_report(
        queries,
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


def search_legal_entities(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Search enabled legal entities with a separate bounded budget."""
    provider, provider_name, cost_mode = _configured_provider()
    if provider is None:
        return []
    max_queries = max(1, int(os.getenv("IPO_LEGAL_ENTITY_MAX_QUERIES", "10")))
    selected = queries[:max_queries]
    search_queries = [SearchQuery(query=item["query"], topic=getattr(item.get("research_topic"), "value", str(item.get("research_topic"))), domains=item.get("domains", []), priority=item.get("priority", "P1")) for item in selected]
    report = SearchService(provider).run_report(search_queries, provider_name=provider_name, cost_mode=cost_mode, max_queries=max_queries)
    query_meta = {item["query"]: item for item in selected}
    results: list[dict[str, Any]] = []
    for item in report.results[:20]:
        lead = item.model_dump()
        meta = query_meta.get(item.query, {})
        try:
            lead.update(fetch_source(item.url))
        except Exception:
            continue
        lead.update({"entity_id": meta.get("entity_id"), "entity_name": meta.get("entity_name"), "search_provider": report.provider, "search_cost_mode": report.cost_mode})
        results.append(lead)
    return results
