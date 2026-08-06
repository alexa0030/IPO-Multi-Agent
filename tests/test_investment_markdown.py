from ipo_financial_agent.models_agent import (
    CompanyBusinessDossier,
    CompanyDossierFinding,
    DiligenceQuestion,
    DueDiligenceConclusion,
    Evidence,
    Finding,
    FinancialFinding,
    ProspectusAnalysis,
)
from ipo_financial_agent.models import RawStatementTable
from ipo_financial_agent.rendering import render_due_diligence_markdown


def test_markdown_renders_mainline_a_conclusion_and_follow_up() -> None:
    evidence = Evidence(
        source_type="prospectus",
        source_file="prospectus.pdf",
        page_number=78,
        title="Business model",
        content="The company sells industrial printing control systems.",
    )
    finding = Finding(
        agent_name="company_business",
        question="What does the company sell?",
        conclusion="The company sells industrial printing control systems.",
        evidence_ids=[evidence.evidence_id],
        evidence_strength="strong",
    )
    question = DiligenceQuestion(
        priority="P1",
        category="company_business",
        question="Provide top-five customer retention data.",
        rationale="Customer durability is not yet verified.",
        requested_materials=["customer retention schedule"],
        downside_if_unresolved="Future earning power may be overstated.",
    )

    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [evidence],
            "research_findings": [finding],
            "diligence_questions": [question],
            "due_diligence_conclusion": DueDiligenceConclusion(
                verdict="conditional_proceed",
                historical_financial_quality="moderate",
                future_earning_power="weak",
                material_risk_level="Medium",
            ),
            "metrics": [],
            "challenges": [],
        }
    )

    assert "# Example Holdings港股 IPO 公司尽调报告" in report
    assert f"{evidence.evidence_id} | 招股书 P78" in report
    assert "## 十、补充尽调清单" in report
    assert "Provide top-five customer retention data." in report
    assert "投资金额、估值上限或退出建议" in report


def test_markdown_does_not_invent_industry_facts_without_external_evidence() -> None:
    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [],
            "research_findings": [],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    assert "尚无招股书之外的行业证据" in report
    assert "行业保持稳定增长" not in report


def test_company_dossier_survives_from_agent_output_to_report() -> None:
    topic_statements = {
        "history_ownership": "控股股东持有本公司多数表决权。",
        "capital_events": "报告期内完成一项业务收购。",
        "products_business_model": "公司销售工业软件并收取软件及服务费。",
        "customers_suppliers": "前五大客户收入占比已披露。",
        "operations": "研发、销售、交付及回款由不同团队负责。",
        "subsidiaries_management": "主要经营活动由境内子公司承担。",
    }
    topic_findings = {}
    for index, (topic, statement) in enumerate(topic_statements.items(), start=50):
        topic_findings[topic] = [
            CompanyDossierFinding(
                topic=topic,
                statement=statement,
                evidence=[
                    Evidence(
                        source_type="prospectus",
                        page_number=index,
                        content=statement,
                    )
                ],
            )
        ]
    prospectus = ProspectusAnalysis(
        company="示例公司",
        dossier=CompanyBusinessDossier(
            company="示例公司",
            topic_findings=topic_findings,
            open_questions=["请核验主要客户报告期后留存情况。"],
        ),
    )

    report = render_due_diligence_markdown(
        {
            "company": "示例公司",
            "prospectus_analysis": prospectus,
            "research_evidence": [],
            "research_findings": [],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    for statement in topic_statements.values():
        assert statement in report
    assert "公司与业务补充核查问题" in report
    assert "请核验主要客户报告期后留存情况。" in report


def test_financial_anomaly_is_not_rendered_as_company_strength() -> None:
    evidence = Evidence(source_type="calculation", source="metric", content="0.59")
    finding = Finding(
        agent_name="financial_dd",
        question="Is cash conversion weak?",
        conclusion="Cash conversion declined to 0.59.",
        evidence_ids=[evidence.evidence_id],
        risks=["weak cash conversion"],
    )
    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [evidence],
            "research_findings": [finding],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    conclusion_section = report.split("## 九、综合判断", 1)[1].split(
        "## 十、补充尽调清单", 1
    )[0]
    assert "Cash conversion declined to 0.59." not in conclusion_section


def test_financial_trigger_renders_as_hypothesis_with_escalation_conditions() -> None:
    report = render_due_diligence_markdown(
        {
            "company": "Example Holdings",
            "research_evidence": [],
            "research_findings": [],
            "financial_findings": [
                FinancialFinding(
                    rule_id="AQ-002",
                    name="存货增长较快",
                    triggered=True,
                    assessment_status="observation",
                    possible_explanations=["并购纳入报表范围"],
                    required_evidence=["合并口径桥接表"],
                    escalation_conditions=["剔除并购后存货仍显著快于收入"],
                )
            ],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    assert "财务异常的解释状态" in report
    assert "待解释观察" in report
    assert "可能解释（待验证）：并购纳入报表范围" in report
    assert "升级为风险的条件：剔除并购后存货仍显著快于收入" in report


def test_markdown_renders_three_original_financial_statements() -> None:
    def table(statement_type: str, name: str, page: int, item: str) -> RawStatementTable:
        return RawStatementTable(
            table_id=f"{statement_type}_1",
            statement_name=name,
            statement_type=statement_type,
            company="示例公司",
            entity_scope="集团/合并",
            unit="人民币百万元",
            currency="人民币",
            pages=[page],
            rows=[["项目", "2024年", "2023年"], [item, "100", "80"]],
            row_pages=[page, page],
            source_file="prospectus.pdf",
        )

    report = render_due_diligence_markdown(
        {
            "company": "示例公司",
            "research_evidence": [],
            "research_findings": [],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
            "raw_statements": [
                table("balance_sheet", "资产负债表", 100, "现金"),
                table("income_statement", "利润表", 110, "收入"),
                table("cash_flow_statement", "现金流量表", 120, "经营活动现金流"),
            ],
        }
    )

    assert "### 三大财务报表（招股书原表还原）" in report
    assert "#### 资产负债表" in report
    assert "#### 利润表" in report
    assert "#### 现金流量表" in report
    assert "来源：P100" in report
    assert "| 经营活动现金流 | 100 | 80 |" in report


def test_markdown_uses_prd_v2_eleven_section_contract() -> None:
    report = render_due_diligence_markdown(
        {
            "company": "示例公司",
            "research_evidence": [],
            "research_findings": [],
            "diligence_questions": [],
            "metrics": [],
            "challenges": [],
        }
    )

    required = (
        "## 一、投资摘要",
        "## 二、公司基本情况",
        "## 三、股权和治理",
        "## 四、商业模式分析",
        "## 五、行业和竞争",
        "## 六、财务分析",
        "## 七、盈利质量分析",
        "## 八、风险分析",
        "## 九、综合判断",
        "## 十、补充尽调清单",
        "## 十一、财务报表附录",
    )
    positions = [report.index(section) for section in required]
    assert positions == sorted(positions)
