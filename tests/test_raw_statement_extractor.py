from ipo_financial_agent.extraction.raw_statement_extractor import RawStatementExtractor


def test_reporting_entity_detects_acquired_company_accountant_appendix():
    text = """
    附录一A 上海色如丹会计师报告
    致深圳市汉森软件股份有限公司列位董事，就上海色如丹数码科技股份有限公司
    及其附属公司的历史财务资料出具的会计师报告。
    """

    entity = RawStatementExtractor._infer_reporting_entity(
        text, "深圳市漢森軟件股份有限公司"
    )

    assert entity == "上海色如丹"


def test_reporting_entity_defaults_to_issuer_without_distinct_appendix_entity():
    issuer = "深圳市漢森軟件股份有限公司"
    assert RawStatementExtractor._infer_reporting_entity("综合财务状况表", issuer) == issuer


def test_reporting_entity_ignores_inline_appendix_reference():
    issuer = "深圳市漢森軟件股份有限公司"
    text = "有关资料请参阅附录一会计师报告所载历史财务资料。"
    assert RawStatementExtractor._infer_reporting_entity(text, issuer) == issuer
