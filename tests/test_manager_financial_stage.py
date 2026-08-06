import json

import pytest
from pydantic import ValidationError

from ipo_financial_agent.agents.financial_research_manager import FinancialResearchManager
from ipo_financial_agent.research.manager_validator import (
    select_financial_task,
    validate_manager_plan,
)
from ipo_financial_agent.schemas import (
    CompanyResearchProfile,
    ManagerContext,
    ManagerFinancialSummary,
    ManagerObservation,
    ManagerTrendPoint,
    ResearchPlan,
    ResearchQuestion,
    ResearchTask,
)


def _context(business: str = "制造业") -> ManagerContext:
    return ManagerContext(
        company_name="示例公司",
        company_overview=f"公司从事{business}",
        business_summary=f"{business}业务模式",
        document_outline=("业务", "财务资料", "风险因素"),
        risk_factor_summary=("客户集中风险",),
        financial_summary=ManagerFinancialSummary(
            reporting_periods=("2023", "2024", "2025"),
            revenue_trend=(ManagerTrendPoint(name="营业收入", period="2025", value=136.0, display_value="136百万元"),),
            gross_margin_trend=(ManagerTrendPoint(name="毛利率", period="2025", value=.545, display_value="54.5%"),),
            triggered_observations=(ManagerObservation(rule_id="RA-001", name="销售费用率持续上升", severity="warning", description="销售费用率为4.1%"),),
        ),
    )


def _question(qid: str, topic: str, priority: str = "P0", number: str = "") -> ResearchQuestion:
    return ResearchQuestion(
        question_id=qid,
        research_topic=topic,
        question=f"{number}{topic}是否需要进一步核验？",
        reason="该问题影响财务质量判断。",
        priority=priority,
        expected_evidence=["招股书财务披露", "确定性计算证据"],
        completion_criteria=["存在计算证据", "形成审慎判断"],
    )


def _plan(*, extra_topic: str = "selling_expense_quality", tasks: int = 1, agent: str = "financial") -> ResearchPlan:
    questions = [
        _question("M_Q1", "profit_cash_conversion"),
        _question("M_Q2", "receivable_revenue_match"),
        _question("M_Q3", "inventory_revenue_match"),
        _question("M_Q4", extra_topic, "P1"),
    ]
    task = ResearchTask(
        task_id="MANAGER_TASK_123",
        target_agent=agent,
        objective="核验公司特定财务质量",
        questions=questions,
        pdf_topics=["财务资料"],
        completion_criteria=["问题均形成Evidence和Finding"],
    )
    return ResearchPlan(
        company_name="示例公司",
        company_profile=CompanyResearchProfile(
            industry="工业", business_type="制造业", capital_intensity="high"
        ),
        key_research_focus=[item.research_topic.value for item in questions],
        tasks=[task.model_copy(deep=True) for _ in range(tasks)],
    )


def test_valid_plan_selects_manager_task_and_preserves_dynamic_ids():
    context = _context()
    plan = _plan()
    assert validate_manager_plan(plan, context) == []
    task, result, status = select_financial_task(plan=plan, context=context)
    assert task.task_id == "MANAGER_TASK_123"
    assert result.plan_valid and not result.fallback_used
    assert result.task_source == "manager"
    assert status == "completed"
    assert {item.question_id for item in task.questions} == {"M_Q1", "M_Q2", "M_Q3", "M_Q4"}


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        (_plan(tasks=2), "恰好"),
        (_plan(agent="industry_competition"), "financial"),
    ],
)
def test_invalid_stage_boundary_falls_back(plan, message):
    task, result, status = select_financial_task(plan=plan, context=_context())
    assert task.task_id == "TASK_FA_001"
    assert result.fallback_used and not result.plan_valid
    assert any(message in item for item in result.validation_errors)
    assert status == "failed_validation"


def test_missing_baseline_topic_falls_back():
    plan = _plan()
    plan.tasks[0].questions = plan.tasks[0].questions[:-2] + [
        _question("M_Q4", "selling_expense_quality", "P1")
    ]
    _, result, _ = select_financial_task(plan=plan, context=_context())
    assert result.fallback_used
    assert "inventory_revenue_match" in " ".join(result.validation_errors)


class _TextClient:
    def __init__(self, text: str):
        self.text = text

    def complete_text(self, **_kwargs):
        return self.text


def test_unparseable_manager_output_keeps_raw_response_and_falls_back():
    attempt = FinancialResearchManager(_TextClient("not-json")).plan(_context())
    assert attempt.plan is None and attempt.raw_response == "not-json"
    _, result, status = select_financial_task(
        plan=None, context=_context(), raw_response=attempt.raw_response,
        parse_error=attempt.parse_error,
    )
    assert result.fallback_used and result.raw_response == "not-json"
    assert status == "failed_parse"


def test_numbers_must_come_from_read_only_context():
    allowed = _plan()
    allowed.tasks[0].questions[0].question = "毛利率54.5%是否影响现金转化？"
    assert not any("不存在的数字" in item for item in validate_manager_plan(allowed, _context()))
    invented = _plan()
    invented.tasks[0].questions[0].question = "毛利率88.8%是否影响现金转化？"
    assert any("88.8%" in item for item in validate_manager_plan(invented, _context()))


def test_manager_context_is_frozen_and_contains_no_ledger():
    context = _context()
    with pytest.raises(ValidationError):
        context.company_name = "被修改"
    payload = json.loads(context.model_dump_json())
    assert "evidences" not in payload and "financial_facts" not in payload


def test_two_company_profiles_can_use_different_company_specific_topics():
    manufacturing = _plan(extra_topic="debt_liquidity")
    software = _plan(extra_topic="earnings_sustainability")
    assert validate_manager_plan(manufacturing, _context("制造业")) == []
    assert validate_manager_plan(software, _context("软件服务")) == []
    m_topics = {item.research_topic for item in manufacturing.tasks[0].questions}
    s_topics = {item.research_topic for item in software.tasks[0].questions}
    assert m_topics != s_topics
