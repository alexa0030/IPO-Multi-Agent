from ipo_financial_agent.agents.research_manager import ResearchManagerAgent


def test_mainline_a_default_plan_assigns_four_specialists() -> None:
    plan = ResearchManagerAgent().plan(
        company="Example Holdings",
        document_summary={"page_count": 500, "section_count": 30},
    )

    assert {task.agent_name for task in plan.tasks} == {
        "company_business",
        "financial_dd",
        "industry_competition",
        "legal_governance",
    }
    assert all(task.question for task in plan.tasks)
    assert all(task.expected_evidence for task in plan.tasks)
