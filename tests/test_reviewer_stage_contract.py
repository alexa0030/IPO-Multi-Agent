from ipo_financial_agent.agents.research_reviewer import ResearchReviewerAgent
from ipo_financial_agent.research.fixed_financial_task import build_fixed_financial_task
from ipo_financial_agent.schemas import (
    CompletionCheck,
    Evidence,
    FinancialAgentResult,
    Finding,
    QuestionAnswerMapping,
    ReviewResult,
    ReviewerValidationResult,
)


def _financial_result(*, upgrade_met: bool = False, bad_quality: bool = False, gap: bool = False):
    task = build_fixed_financial_task()
    evidence = []
    findings = []
    mappings = []
    risks = ("medium", "high", "low")
    for index, question in enumerate(task.questions, start=1):
        pdf_id = f"PDF_R_{index}"
        calc_id = f"CALC_R_{index}"
        finding_id = f"FIN_R_{index}"
        evidence.extend([
            Evidence(evidence_id=pdf_id, source_type="prospectus", title="财务披露", content=f"底层数据{index}", page_number=20 + index, source_quality="A", created_by="financial"),
            Evidence(evidence_id=calc_id, source_type="calculation", title="确定性指标", content=f"指标{index}", formula="A/B", input_evidence_ids=[pdf_id], raw_value=index, source_quality="A", created_by="financial"),
        ])
        finding = Finding(
            finding_id=finding_id,
            task_id=task.task_id,
            agent="financial",
            topic=question.research_topic,
            answered_question_ids=[] if gap and index == 3 else [question.question_id],
            title=f"财务观察{index}",
            statement=f"确定性财务观察{index}",
            evidence_ids=[pdf_id, calc_id],
            interpretation="该观察需要结合明细资料进一步核验。",
            alternative_explanations=[] if bad_quality and index == 1 else ["结算时点变化"],
            required_checks=["补充明细", "期后数据"],
            upgrade_condition="若补证与披露冲突则升级风险判断。",
            upgrade_condition_met=upgrade_met and index == 2,
            risk_level=risks[index - 1],
            confidence="high",
        )
        findings.append(finding)
        has_answer = not (gap and index == 3)
        mappings.append(QuestionAnswerMapping(
            question_id=question.question_id,
            research_topic=question.research_topic,
            finding_ids=[finding_id] if has_answer else [],
            evidence_ids=[pdf_id, calc_id] if has_answer else [],
            completion_checks=[CompletionCheck(
                criterion="存在计算证据", passed=has_answer,
                evidence_ids=[calc_id] if has_answer else [],
            )],
            status="answered" if has_answer else "unanswered",
            gap_reason=None if has_answer else "缺少可用Finding",
        ))
    return task, FinancialAgentResult(
        task_id=task.task_id,
        evidences=evidence,
        findings=findings,
        question_answer_map=mappings,
        completion_status="partial" if gap else "completed",
    )


def test_reviewer_accepts_complete_contract_without_false_high_risk():
    task, financial = _financial_result()
    before = financial.model_dump(mode="json")
    review, validation = ResearchReviewerAgent().review_financial_contract(
        task=task, result=financial
    )
    assert review.review_status == "conditional_pass"
    assert validation.question_coverage_complete
    assert validation.finding_quality_complete
    assert validation.accepted_question_ids == ["FA_Q001", "FA_Q002", "FA_Q003"]
    assert {item.priority for item in review.follow_up_requests} == {"P0", "P1", "P2"}
    assert financial.model_dump(mode="json") == before
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
    assert ReviewerValidationResult.model_validate_json(validation.model_dump_json()) == validation


def test_reviewer_upgrades_only_when_upgrade_condition_is_met():
    task, financial = _financial_result(upgrade_met=True)
    review, _ = ResearchReviewerAgent().review_financial_contract(task=task, result=financial)
    assert review.review_status == "high_risk"


def test_reviewer_rejects_medium_finding_without_alternative_explanation():
    task, financial = _financial_result(bad_quality=True)
    review, validation = ResearchReviewerAgent().review_financial_contract(
        task=task, result=financial
    )
    assert review.review_status == "insufficient_evidence"
    assert "FIN_R_1" in review.rejected_finding_ids
    assert not validation.finding_quality_complete
    assert "FA_Q001" in validation.rejected_question_ids


def test_reviewer_marks_unanswered_p0_as_insufficient():
    task, financial = _financial_result(gap=True)
    review, validation = ResearchReviewerAgent().review_financial_contract(
        task=task, result=financial
    )
    assert review.review_status == "insufficient_evidence"
    assert not validation.question_coverage_complete
    assert validation.rejected_question_ids == ["FA_Q003"]
