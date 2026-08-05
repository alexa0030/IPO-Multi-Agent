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

