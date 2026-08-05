from ipo_financial_agent.finance.metric_engine import MetricEngine
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
