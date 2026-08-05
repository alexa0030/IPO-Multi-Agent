from ipo_financial_agent.models_agent import Evidence, Finding, IndustryAnalysis
from ipo_financial_agent.rendering import render_investment_markdown


def test_markdown_separates_grounded_facts_and_open_questions() -> None:
    evidence = Evidence(
        source_type="prospectus",
        source_file="prospectus.pdf",
        page_number=78,
        title="行业排名",
        content="公司按收入计排名第一。",
    )
    finding = Finding(
        agent_name="market_valuation",
        question="公司的行业地位如何？",
        conclusion="公司在独立打印控制系统供应商中排名第一。",
        evidence_ids=[evidence.evidence_id],
        evidence_strength="strong",
    )

    report = render_investment_markdown(
        {
            "company": "汉森软件",
            "research_evidence": [evidence],
            "research_findings": [finding],
            "open_questions": ["发行价格仍为[编纂]。"],
            "challenges": [],
            "metrics": [],
            "industry_analysis": IndustryAnalysis(),
        }
    )

    assert "# 汉森软件港股 IPO 尽调与投资研究报告" in report
    assert f"{evidence.evidence_id} | 招股书 P78" in report
    assert "发行价格仍为[编纂]。" in report
    assert "不推算虚假估值" in report


def test_markdown_does_not_invent_industry_facts_without_evidence() -> None:
    report = render_investment_markdown(
        {
            "company": "汉森软件",
            "research_evidence": [],
            "research_findings": [],
            "open_questions": [],
            "challenges": [],
            "metrics": [],
        }
    )

    assert "外部检索尚未提供可引用证据" in report
    assert "行业保持稳定增长" not in report


def test_financial_anomaly_is_not_repeated_as_investment_thesis() -> None:
    evidence = Evidence(source_type="calculation", source="metric", content="0.59")
    finding = Finding(
        agent_name="financial_dd",
        question="净现比是否偏低？",
        conclusion="净现比下降至0.59。",
        evidence_ids=[evidence.evidence_id],
    )
    report = render_investment_markdown(
        {
            "company": "汉森软件",
            "research_evidence": [evidence],
            "research_findings": [finding],
            "open_questions": [],
            "challenges": [],
            "metrics": [],
        }
    )

    investment_section = report.split("## 五、投资逻辑", 1)[1].split(
        "## 六、风险与反证", 1
    )[0]
    assert "净现比下降至0.59" not in investment_section
