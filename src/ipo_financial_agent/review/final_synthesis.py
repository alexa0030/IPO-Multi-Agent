from __future__ import annotations
from typing import Any
from ipo_financial_agent.schemas.final_synthesis import *

def _dump(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value

def build_final_synthesis_context(review_input: Any, topic_results: list[ReviewedTopicResult], *, company_name: str = "", job_id: str = "") -> FinalSynthesisContext:
    data = _dump(review_input); reviewed = {fid for item in topic_results for fid in item.reviewed_finding_ids}
    all_findings = data.get("finding_index", [])
    standalone = [item for item in all_findings if str(_dump(item).get("finding_id", "")) not in reviewed]
    high = [str(_dump(item).get("finding_id")) for item in standalone if _dump(item).get("risk_level") == "high" and _dump(item).get("upgrade_condition_met")]
    return FinalSynthesisContext(company_name=company_name, job_id=job_id, reviewed_topics=topic_results, standalone_findings=standalone, evidence_gaps=data.get("evidence_gaps", []), existing_follow_up_requests=data.get("follow_up_requests", []), agent_statuses=data.get("agent_validation_summaries", []), deterministic_high_risk_finding_ids=high)

def deterministic_draft(context: FinalSynthesisContext) -> FinalSynthesisDraft:
    topics = context.reviewed_topics
    def assessment(title: str, axes: list[str]) -> FinalAssessment:
        selected = [item for item in topics if any(axis in item.assessment_axes for axis in axes)]
        return FinalAssessment(title=title, conclusion="；".join(item.integrated_statement for item in selected) or "当前资料不足，无法形成充分结论。", positive_factors=[x for item in selected for x in item.positive_factors], negative_factors=[x for item in selected for x in item.negative_factors], evidence_gaps=[x for item in selected for x in item.evidence_gaps], related_topic_ids=[item.topic_id for item in selected], finding_ids=[x for item in selected for x in item.reviewed_finding_ids], evidence_ids=[x for item in selected for x in item.reviewed_evidence_ids], confidence="medium" if selected else "low")
    strengths=[]; risks=[]; mixed=[]
    for item in topics:
        point=FinalPoint(point_id="FP_"+item.topic_id, title=item.topic_name, statement=item.integrated_statement, finding_ids=item.reviewed_finding_ids, evidence_ids=item.reviewed_evidence_ids, confidence=item.confidence)
        (strengths if item.conclusion_nature=="strength" else risks if item.conclusion_nature=="risk" else mixed if item.conclusion_nature=="mixed" else []).append(point) if item.conclusion_nature in {"strength","risk","mixed"} else None
    return FinalSynthesisDraft(historical_financial_assessment=assessment("历史财务质量", ["historical_financial"]), future_earning_assessment=assessment("未来盈利能力", ["future_earning"]), negative_matter_assessment=assessment("重大负面事项", ["negative_matter"]), reviewed_strengths=strengths, reviewed_risks=risks, reviewed_mixed_points=mixed, additional_evidence_gaps=context.evidence_gaps, approved_finding_ids=[x for item in topics for x in item.reviewed_finding_ids], due_diligence_question_candidates=[])

def determine_final_review_status(context: FinalSynthesisContext, draft: FinalSynthesisDraft) -> str:
    if context.deterministic_high_risk_finding_ids: return "high_risk"
    if context.unresolved_p0_question_ids or any(item.consistency_status=="conflicted" for item in context.reviewed_topics): return "needs_follow_up"
    if any(item.suggested_severity=="medium" for item in context.reviewed_topics) or context.evidence_gaps: return "conditional_pass"
    return "pass"

def build_final_review_result(context: FinalSynthesisContext, draft: FinalSynthesisDraft) -> FinalReviewResult:
    questions=draft.due_diligence_question_candidates
    status=determine_final_review_status(context,draft)
    return FinalReviewResult(review_status=status, historical_financial_assessment=draft.historical_financial_assessment, future_earning_assessment=draft.future_earning_assessment, negative_matter_assessment=draft.negative_matter_assessment, reviewed_topics=context.reviewed_topics, reviewed_strengths=draft.reviewed_strengths, reviewed_risks=draft.reviewed_risks, reviewed_mixed_points=draft.reviewed_mixed_points, evidence_gaps=[*context.evidence_gaps,*draft.additional_evidence_gaps], p0_due_diligence_questions=[x for x in questions if x.priority=="P0"], p1_due_diligence_questions=[x for x in questions if x.priority=="P1"], p2_due_diligence_questions=[x for x in questions if x.priority=="P2"], approved_finding_ids=draft.approved_finding_ids, excluded_finding_ids=draft.excluded_finding_ids)
