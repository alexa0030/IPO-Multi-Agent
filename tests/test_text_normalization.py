from ipo_financial_agent.text_normalization import normalize_search_text, to_simplified


def test_traditional_text_is_normalized_to_simplified():
    source = "關聯交易、訴訟風險及綜合現金流量表"
    assert to_simplified(source) == "关联交易、诉讼风险及综合现金流量表"
    assert normalize_search_text(" 財務\n資料 ") == "财务 资料"


def test_original_text_is_not_mutated():
    source = "會計師報告"
    assert normalize_search_text(source) == "会计师报告"
    assert source == "會計師報告"
