"""Deterministic Financial-only reviewer for the staged research contract."""

from __future__ import annotations

from ipo_financial_agent.ledger import EvidenceRegistry, FindingRegistry
from ipo_financial_agent.schemas import (
    Assessment,
    Evidence,
    FinancialAgentResult,
    Finding,
    FindingReview,
    FollowUpRequest,
    ResearchTask,
    ReviewResult,
    ReviewerValidationResult,
)


class ResearchReviewerAgent:
    """Review immutable Financial artifacts; never rewrite a Finding or Evidence."""

    def review_financial_contract(
        self, *, task: ResearchTask, result: FinancialAgentResult
    ) -> tuple[ReviewResult, ReviewerValidationResult]:
        return self._review(
            task=task,
            evidences=result.evidences,
            findings=result.findings,
            financial_result=result,
        )

    def review_financial(
        self, *, task: ResearchTask, evidences: list[Evidence], findings: list[Finding]
    ) -> ReviewResult:
        review, _ = self._review(
            task=task, evidences=evidences, findings=findings, financial_result=None
        )
        return review

    def _review(
        self, *, task: ResearchTask, evidences: list[Evidence], findings: list[Finding],
        financial_result: FinancialAgentResult | None,
    ) -> tuple[ReviewResult, ReviewerValidationResult]:
        if task.target_agent != "financial":
            raise ValueError("Financial-only Reviewer accepts only financial tasks")
        evidence_registry = EvidenceRegistry(evidences)
        finding_registry = FindingRegistry(evidence_registry)
        approved: list[Finding] = []
        rejected_ids: list[str] = []
        follow_ups: list[FollowUpRequest] = []
        finding_reviews: list[FindingReview] = []
        validation_errors: list[str] = []

        for finding in findings:
            reasons: list[str] = []
            try:
                finding_registry.add(finding)
            except ValueError as exc:
                reasons.append(str(exc))
            if not finding.interpretation.strip():
                reasons.append("Finding缺少解释")
            if finding.risk_level in {"medium", "high"}:
                if not finding.alternative_explanations:
                    reasons.append("中高风险Finding缺少替代解释")
                if not finding.required_checks:
                    reasons.append("中高风险Finding缺少补证要求")
            if finding.risk_level == "high" and not finding.upgrade_condition:
                reasons.append("高风险Finding缺少升级条件")
            if reasons:
                rejected_ids.append(finding.finding_id)
                validation_errors.extend(
                    f"{finding.finding_id}: {reason}" for reason in reasons
                )
                finding_reviews.append(FindingReview(
                    finding_id=finding.finding_id,
                    decision="rejected",
                    reasons=reasons,
                    evidence_ids_checked=list(finding.evidence_ids),
                ))
                follow_ups.append(FollowUpRequest(
                    follow_up_id=f"FU_{finding.finding_id}_QUALITY",
                    target_agent="financial",
                    related_finding_ids=[finding.finding_id],
                    question=f"补齐“{finding.title}”的证据、解释或升级条件。",
                    reason="；".join(reasons),
                    required_evidence=list(finding.required_checks),
                    priority="P0",
                ))
                continue
            approved.append(finding)
            needs_follow_up = bool(finding.required_checks) and finding.risk_level != "positive"
            finding_reviews.append(FindingReview(
                finding_id=finding.finding_id,
                decision="needs_follow_up" if needs_follow_up else "approved",
                reasons=(
                    ["证据链完整，但替代解释及升级条件仍需补证"]
                    if needs_follow_up else ["证据链与Finding质量检查通过"]
                ),
                evidence_ids_checked=list(finding.evidence_ids),
            ))
            if needs_follow_up:
                priority = {"high": "P0", "medium": "P1", "low": "P2"}.get(
                    finding.risk_level, "P2"
                )
                follow_ups.append(FollowUpRequest(
                    follow_up_id=f"FU_{finding.finding_id}_CHECK",
                    target_agent="financial",
                    related_finding_ids=[finding.finding_id],
                    question=f"验证“{finding.title}”的替代解释及风险升级条件。",
                    reason="当前结论是有证据支持的观察项，原因与升级条件尚未闭环。",
                    required_evidence=list(finding.required_checks),
                    priority=priority,
                ))

        approved_ids = {item.finding_id for item in approved}
        reviewed_question_ids = [item.question_id for item in task.questions]
        accepted_question_ids: list[str] = []
        rejected_question_ids: list[str] = []
        if financial_result is not None:
            mapping_by_id = {
                item.question_id: item for item in financial_result.question_answer_map
            }
            for question in task.questions:
                mapping = mapping_by_id.get(question.question_id)
                if mapping and mapping.status == "answered" and approved_ids.intersection(mapping.finding_ids):
                    accepted_question_ids.append(question.question_id)
                else:
                    rejected_question_ids.append(question.question_id)
                    validation_errors.append(
                        f"问题{question.question_id}没有通过Reviewer的有效Finding"
                    )
        else:
            accepted_question_ids = reviewed_question_ids

        p0_ids = {item.question_id for item in task.questions if item.priority == "P0"}
        p0_gap = p0_ids - set(accepted_question_ids)
        upgraded = [
            item for item in approved
            if item.risk_level == "high" and item.upgrade_condition_met
        ]
        if upgraded:
            review_status = "high_risk"
        elif p0_gap or not approved:
            review_status = "insufficient_evidence"
        elif follow_ups:
            review_status = "conditional_pass"
        else:
            review_status = "pass"

        approved_evidence_ids = list(dict.fromkeys(
            evidence_id for finding in approved for evidence_id in finding.evidence_ids
        ))
        calculation_ids = [
            item.evidence_id for item in evidence_registry.require(approved_evidence_ids)
            if item.source_type == "calculation"
        ] if approved_evidence_ids else []
        conclusion = (
            "；".join(f"{item.statement}{item.interpretation}" for item in approved)
            if approved else "尚无通过Evidence完整性与Finding质量检查的财务结论。"
        )
        review = ReviewResult(
            review_status=review_status,
            historical_financial_assessment=Assessment(
                conclusion=conclusion,
                confidence="high" if len(calculation_ids) >= 3 else ("medium" if approved else "low"),
                evidence_ids=calculation_ids or approved_evidence_ids,
            ),
            future_earning_assessment=Assessment(
                conclusion="本阶段仅审核Financial Finding，不单独判断未来盈利能力。",
                confidence="low", evidence_ids=[],
            ),
            negative_matter_assessment=Assessment(
                conclusion="本阶段不覆盖法务与外部负面事项。",
                confidence="low", evidence_ids=[],
            ),
            approved_finding_ids=[item.finding_id for item in approved],
            rejected_finding_ids=rejected_ids,
            follow_up_requests=follow_ups,
            key_risks=[item.title for item in approved if item.risk_level in {"medium", "high"}],
            p0_questions=[item.question for item in follow_ups if item.priority == "P0"],
            p1_questions=[item.question for item in follow_ups if item.priority == "P1"],
            p2_questions=[item.question for item in follow_ups if item.priority == "P2"],
        )
        validation = ReviewerValidationResult(
            input_valid=not any("unknown" in item.lower() or "missing" in item.lower() for item in validation_errors),
            evidence_integrity=not any("evidence" in item.lower() for item in validation_errors),
            question_coverage_complete=not rejected_question_ids,
            finding_quality_complete=not rejected_ids,
            validation_errors=validation_errors,
            reviewed_question_ids=reviewed_question_ids,
            accepted_question_ids=accepted_question_ids,
            rejected_question_ids=rejected_question_ids,
            finding_reviews=finding_reviews,
        )
        return review, validation
