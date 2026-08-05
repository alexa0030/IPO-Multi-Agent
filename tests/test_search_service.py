from ipo_financial_agent.tools.search import (
    SearchQuery,
    SearchResult,
    SearchService,
    build_due_diligence_queries,
    classify_source_tier,
)


class FakeProvider:
    def search(self, query: SearchQuery) -> list[SearchResult]:
        if query.topic == "hkex_filings":
            return [
                SearchResult(
                    query=query.query,
                    topic=query.topic,
                    title="Application proof",
                    content="short",
                    url="https://www1.hkexnews.hk/example.pdf",
                ),
                SearchResult(
                    query=query.query,
                    topic=query.topic,
                    title="Application proof",
                    content="a longer duplicate excerpt",
                    url="https://www1.hkexnews.hk/example.pdf",
                ),
            ]
        return []


def test_due_diligence_plan_contains_official_and_adverse_queries() -> None:
    queries = build_due_diligence_queries("汉森软件", "数字打印控制系统")

    topics = {item.topic for item in queries}
    assert {
        "hkex_filings",
        "regulatory",
        "litigation",
        "industry",
        "controller_related_parties",
        "customers_suppliers",
        "accounting_auditor",
        "competitors",
    } <= topics
    assert next(item for item in queries if item.topic == "hkex_filings").domains


def test_official_source_tier_handles_hkex_subdomains() -> None:
    assert classify_source_tier("https://www1.hkexnews.hk/example.pdf") == "official"
    assert classify_source_tier("https://www.cninfo.com.cn/example.pdf") == "primary"
    assert classify_source_tier("https://example.com/article") == "secondary"


def test_search_service_deduplicates_and_prefers_longer_excerpt() -> None:
    service = SearchService(FakeProvider())

    results = service.run(build_due_diligence_queries("汉森软件"))

    assert len(results) == 1
    assert results[0].source_tier == "official"
    assert results[0].confidence == 0.95
    assert results[0].content == "a longer duplicate excerpt"


def test_search_report_exposes_missing_topics_and_budget() -> None:
    service = SearchService(FakeProvider())

    report = service.run_report(
        build_due_diligence_queries("汉森软件"),
        provider_name="fake",
        cost_mode="free_best_effort",
        max_queries=2,
    )

    assert len(report.queries) == 2
    assert report.provider == "fake"
    assert report.cost_mode == "free_best_effort"
    assert "hkex_filings" in report.covered_topics
    assert report.missing_topics
