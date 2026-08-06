from __future__ import annotations

import re

from ipo_financial_agent.research.fixed_financial_task import build_fixed_financial_task
from ipo_financial_agent.schemas import (
    BASELINE_FINANCIAL_TOPICS,
    ManagerContext,
    ManagerValidationResult,
    ResearchPlan,
    ResearchTask,
)

_NUMBER = re.compile(r"(?<![A-Za-z_])-?\d+(?:\.\d+)?%?")


def validate_manager_plan(plan: ResearchPlan, context: ManagerContext) -> list[str]:
    """Validate in the documented fixed order; never repair model output silently."""
    errors: list[str] = []
    if len(plan.tasks) != 1:
        return ["当前阶段必须恰好生成一个ResearchTask"]
    task = plan.tasks[0]
    if task.target_agent != "financial":
        errors.append("当前阶段唯一任务必须分配给financial")
    question_ids = [item.question_id for item in task.questions]
    if len(question_ids) != len(set(question_ids)):
        errors.append("question_id必须唯一")
    topics = [item.research_topic for item in task.questions]
    missing = BASELINE_FINANCIAL_TOPICS - set(topics)
    errors.extend(
        f"缺少基础主题 {item.value}" for item in sorted(missing, key=lambda x: x.value)
    )
    if any(not item.reason.strip() for item in task.questions):
        errors.append("每个问题必须提供reason")
    if any(not item.expected_evidence for item in task.questions):
        errors.append("每个问题必须提供expected_evidence")
    p0_count = sum(item.priority == "P0" for item in task.questions)
    if not 3 <= p0_count <= 5:
        errors.append("P0问题数量必须在3至5个之间")
    if len(task.questions) > 8:
        errors.append("全部问题不能超过8个")
    company_specific = sum(item.research_topic not in BASELINE_FINANCIAL_TOPICS for item in task.questions)
    if company_specific < 1:
        errors.append("至少需要一个公司特定财务问题")
    if company_specific > 3:
        errors.append("公司特定问题不能超过3个")
    if task.web_topics:
        errors.append("当前阶段禁止web_topics")
    prohibited = ("造假", "违规", "违法", "虚构", "少缴", "粉饰", "欺诈", "操纵")
    task_text = " ".join(
        [task.objective, *(text for item in task.questions for text in (item.question, item.reason))]
    )
    used_prohibited = sorted(word for word in prohibited if word in task_text)
    if used_prohibited:
        errors.append(f"计划包含未经核实的负面定性措辞: {used_prohibited}")
    unsupported_requests = (
        "周转率", "周转天数", "资产负债率", "占营业收入", "占收入",
        "绝对差额", "影响金额", "侵蚀程度",
    )
    used_unsupported = sorted(word for word in unsupported_requests if word in task_text)
    if used_unsupported:
        errors.append(f"问题要求Financial Agent尚不支持的新计算: {used_unsupported}")
    allowed_numbers = set(_NUMBER.findall(context.model_dump_json()))
    output_text = " ".join(
        [task.objective, *(
            text for item in task.questions for text in (item.question, item.reason)
        )]
    )
    invented = sorted(set(_NUMBER.findall(output_text)) - allowed_numbers)
    if invented:
        errors.append(f"问题包含只读摘要中不存在的数字: {invented}")
    return errors


def select_financial_task(
    *, plan: ResearchPlan | None, context: ManagerContext,
    raw_response: str = "", parse_error: str | None = None,
) -> tuple[ResearchTask, ManagerValidationResult, str]:
    errors = [f"ResearchPlan Schema解析失败: {parse_error}"] if parse_error else []
    if plan is not None and not errors:
        errors.extend(validate_manager_plan(plan, context))
    if plan is not None and len(plan.tasks) == 1:
        manager_task_id = plan.tasks[0].task_id
        actual = {item.research_topic for item in plan.tasks[0].questions}
    else:
        manager_task_id = None
        actual = set()
    missing = BASELINE_FINANCIAL_TOPICS - actual
    if plan is not None and not errors:
        selected = plan.tasks[0]
        return selected, ManagerValidationResult(
            plan_valid=True,
            fallback_used=False,
            selected_task_id=selected.task_id,
            manager_task_id=selected.task_id,
            task_source="manager",
            baseline_topics_covered=sorted(item.value for item in BASELINE_FINANCIAL_TOPICS),
            baseline_topics_missing=[],
            raw_response=raw_response,
        ), "completed"
    selected = build_fixed_financial_task()
    return selected, ManagerValidationResult(
        plan_valid=False,
        fallback_used=True,
        validation_errors=errors or ["Research Manager未返回计划"],
        selected_task_id=selected.task_id,
        manager_task_id=manager_task_id,
        task_source="fixed",
        baseline_topics_covered=sorted(item.value for item in actual & BASELINE_FINANCIAL_TOPICS),
        baseline_topics_missing=sorted(item.value for item in missing),
        raw_response=raw_response,
    ), ("failed_parse" if parse_error else "failed_validation")
