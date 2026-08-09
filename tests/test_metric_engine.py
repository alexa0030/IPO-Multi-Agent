from ipo_financial_agent.finance.metric_engine import MetricEngine
from ipo_financial_agent.finance.topic_catalog import canonical_tag_for_item
from ipo_financial_agent.models import StatementFact


def fact(fid: str, tag: str, period: str, value: float, page: int) -> StatementFact:
    return StatementFact(
        fact_id=fid,
        document_id="doc",
        company="测试公司",
        statement_name="综合损益及其他全面收益表",
        item_name=tag,
        canonical_tag=tag,
        period=period,
        value=value,
        raw_value=str(value),
        page=page,
    )


def test_metric_engine_growth_and_margin():
    facts = [
        fact("r1", "revenue", "2023", 100, 10),
        fact("r2", "revenue", "2024", 120, 10),
        fact("g1", "gross_profit", "2023", 50, 11),
        fact("g2", "gross_profit", "2024", 54, 11),
        fact("n1", "net_profit", "2023", 20, 12),
        fact("n2", "net_profit", "2024", 18, 12),
    ]
    metrics = MetricEngine().calculate("doc", facts)
    values = {(item.metric_code, item.period): item.value for item in metrics}
    assert round(values[("revenue_growth", "2024")], 6) == 0.2
    assert round(values[("gross_margin", "2024")], 6) == 0.45
    assert round(values[("net_margin", "2024")], 6) == 0.15


def test_non_current_rows_do_not_match_current_tags():
    assert canonical_tag_for_item("非流动资产") != "current_assets"
    assert canonical_tag_for_item("非流動負債總額") != "current_liabilities"
    assert canonical_tag_for_item("流动资产") == "current_assets"
    assert canonical_tag_for_item("流動負債總額") == "current_liabilities"


def test_metric_engine_prefers_issuer_consolidated_facts_over_later_subsidiary():
    issuer_assets = fact("ca-main", "current_assets", "2025", 976478, 22)
    issuer_assets.entity_scope = "集团/合并"
    issuer_assets.reporting_entity = issuer_assets.company
    issuer_assets.source_table_id = "issuer-balance-sheet"
    issuer_liabilities = fact("cl-main", "current_liabilities", "2025", 263595, 22)
    issuer_liabilities.entity_scope = "集团/合并"
    issuer_liabilities.reporting_entity = issuer_liabilities.company
    issuer_liabilities.source_table_id = "issuer-balance-sheet"
    subsidiary_assets = fact("ca-sub", "current_assets", "2025", 300000, 353)
    subsidiary_assets.entity_scope = "集团/合并"
    subsidiary_assets.reporting_entity = "上海色如丹数码科技股份有限公司"
    subsidiary_assets.source_table_id = "subsidiary-balance-sheet"
    subsidiary_liabilities = fact("cl-sub", "current_liabilities", "2025", 150000, 353)
    subsidiary_liabilities.entity_scope = "集团/合并"
    subsidiary_liabilities.reporting_entity = "上海色如丹数码科技股份有限公司"
    subsidiary_liabilities.source_table_id = "subsidiary-balance-sheet"

    metrics = MetricEngine().calculate(
        "doc",
        [subsidiary_assets, subsidiary_liabilities, issuer_assets, issuer_liabilities],
    )
    current_ratio = next(item for item in metrics if item.metric_code == "current_ratio")

    assert round(current_ratio.value or 0, 2) == 3.70
    assert current_ratio.source_fact_ids == ["ca-main", "cl-main"]


def test_metric_engine_excludes_other_reporting_entity_even_if_earlier():
    issuer_revenue = fact("r-main", "revenue", "2025", 600, 200)
    issuer_revenue.reporting_entity = issuer_revenue.company
    target_revenue = fact("r-target", "revenue", "2025", 150, 20)
    target_revenue.reporting_entity = "被收购公司"
    issuer_profit = fact("n-main", "net_profit", "2025", 120, 201)
    issuer_profit.reporting_entity = issuer_profit.company

    metrics = MetricEngine().calculate(
        "doc",
        [target_revenue, issuer_revenue, issuer_profit],
        reporting_entity=issuer_revenue.company,
    )
    net_margin = next(item for item in metrics if item.metric_code == "net_margin")

    assert net_margin.source_fact_ids == ["n-main", "r-main"]
