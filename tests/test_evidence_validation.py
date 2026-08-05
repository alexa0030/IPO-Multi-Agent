from ipo_financial_agent.extraction.financial_parser import FinancialParser
from ipo_financial_agent.models import (
    FinancialExtractionResult,
    FinancialNote,
    StatementFact,
)


class DummyClient:
    pass


def test_sanitize_drops_invalid_pages():
    parser = FinancialParser(DummyClient(), max_chars=10000)
    result = FinancialExtractionResult(
        statement_facts=[
            StatementFact(
                fact_id="x",
                document_id="wrong",
                company="wrong",
                statement_name="表",
                item_name="收入",
                canonical_tag="revenue",
                period="2024",
                value=100,
                raw_value="100",
                page=999,
            )
        ],
        financial_notes=[
            FinancialNote(
                note_id="n",
                document_id="wrong",
                company="wrong",
                topic="存货",
                title="存货",
                information_type="构成",
                summary="测试",
                pages=[8, 999],
            )
        ],
    )
    sanitized = parser._sanitize_result(
        result=result,
        document_id="doc",
        company="测试公司",
        allowed_pages={8, 9},
        chunk_index=1,
    )
    assert sanitized.statement_facts == []
    assert sanitized.financial_notes[0].pages == [8]
