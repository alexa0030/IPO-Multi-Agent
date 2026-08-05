from ipo_financial_agent.agents.prospectus_agent import ProspectusAgent
from ipo_financial_agent.models import PageData


def test_business_selector_excludes_toc_and_grounds_summary() -> None:
    pages = [
        PageData(
            source_file="prospectus.pdf",
            page=10,
            text="目录 业务 风险因素 客户 供应商",
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=13,
            text=(
                "概要 我们是全球数字打印控制系统供应商，"
                "主要提供打印控制系统、打印机及耗材和软件服务。"
            ),
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=120,
            text="业务模式 我们的解决方案覆盖打印控制与耗材。",
            tables=[],
        ),
    ]

    result = ProspectusAgent().analyze(company="汉森软件", pages=pages)

    assert "全球数字打印控制系统供应商" in result.business_model
    assert result.business_model_evidence[0].page_number == 13
    assert all(item.page_number != 10 for item in result.business_model_evidence)


def test_offline_analysis_extracts_product_categories_and_masked_counterparties() -> None:
    pages = [
        PageData(
            source_file="prospectus.pdf",
            page=13,
            text=(
                "概要 我们是一家全链条数字打印解决方案供应商，"
                "主要提供打印控制系统、打印机及耗材、打印软件及服务。"
            ),
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=140,
            text=(
                "业务 我们的前五大客户详情如下：客户A、客户B、客户C。"
                "来自前五大客户的收入占总收入28.6%。"
            ),
            tables=[],
        ),
        PageData(
            source_file="prospectus.pdf",
            page=148,
            text="业务 前五大供应商详情如下：供应商A、供应商B。",
            tables=[],
        ),
    ]

    result = ProspectusAgent().analyze(company="测试公司", pages=pages)

    assert {item.name for item in result.main_products} >= {
        "打印控制系统",
        "打印机及耗材",
        "打印软件及服务",
    }
    assert {item.name for item in result.customers} >= {"客户A", "客户B"}
    assert {item.name for item in result.suppliers} >= {"供应商A", "供应商B"}
    assert all(item.evidence for item in result.main_products)
    assert next(item for item in result.customers if item.name == "客户A").evidence[
        0
    ].page_number == 140
