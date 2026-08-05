from types import SimpleNamespace

from ipo_financial_agent.pipeline import IPOFinancialPipeline


def test_financial_followup_retrieves_relevant_prospectus_pages_only() -> None:
    pages = [
        SimpleNamespace(page_number=10, text="存货增加主要来自收购纳入合并范围。"),
        SimpleNamespace(page_number=11, text="董事会成员履历。"),
    ]

    evidence = IPOFinancialPipeline._retrieve_prospectus_followup(
        pages=pages,
        question="存货增加是否由收购合理解释",
        challenge_id="challenge_1",
    )

    assert [item.page_number for item in evidence] == [10]
    assert evidence[0].metadata["challenge_id"] == "challenge_1"
