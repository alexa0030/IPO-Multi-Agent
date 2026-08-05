from ipo_financial_agent.finance.forensic_engine import FinancialForensicEngine
from ipo_financial_agent.models import RawStatementTable, StatementFact


def _revenue(period: str, value: float, page: int) -> StatementFact:
    return StatementFact(
        fact_id=f"revenue_{period}",
        document_id="doc",
        company="Example",
        statement_name="综合损益表",
        item_name="收入",
        canonical_tag="revenue",
        period=period,
        value=value,
        raw_value=str(value),
        page=page,
    )


def _cash_flow(table_id: str, page: int, values: tuple[str, str]) -> RawStatementTable:
    return RawStatementTable(
        table_id=table_id,
        statement_name="综合现金流量表",
        statement_type="cash_flow_statement",
        company="Example",
        pages=[page],
        rows=[
            ["", "2024年", "2025年"],
            ["已付所得税", values[0], values[1]],
        ],
        row_pages=[page, page],
        source_file="prospectus.pdf",
    )


def test_raw_index_keeps_all_header_periods() -> None:
    table = _cash_flow("main", 287, ("(10)", "(13)"))

    index = FinancialForensicEngine._build_raw_index([table])

    assert [item["period"] for item in index["已付所得税"]] == [
        "2024",
        "2025",
    ]


def test_tax_rule_uses_absolute_cash_tax_and_primary_statement() -> None:
    engine = FinancialForensicEngine()
    main = _cash_flow("main", 287, ("(10)", "(13)"))
    acquired_company = _cash_flow("appendix", 357, ("(50)", "(1)"))

    findings = engine.analyze(
        document_id="doc",
        facts=[_revenue("2024", 100, 21), _revenue("2025", 130, 21)],
        metrics=[],
        raw_statements=[main, acquired_company],
    )
    tax_finding = next(item for item in findings if item.rule_id == "RA-003")

    assert tax_finding.triggered is False
    assert tax_finding.metrics["tax_growth"] == 0.3
    assert tax_finding.evidence[0].page_number == 287
