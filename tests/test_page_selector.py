from ipo_financial_agent.document.page_selector import FinancialPageSelector
from ipo_financial_agent.models import PageData, SectionHit


def test_selector_adds_context_pages():
    pages = [PageData(source_file="x.pdf", page=i, text="普通页面") for i in range(1, 6)]
    pages[2].text = "存货增加原因"
    selected = FinancialPageSelector(context_pages=1).select(pages, [])
    assert [page.page for page in selected] == [2, 3, 4]
