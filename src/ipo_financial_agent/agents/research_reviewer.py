"""Minimal phase-one Reviewer for the Financial contract vertical slice."""

from __future__ import annotations

from ipo_financial_agent.ledger import EvidenceRegistry, FindingRegistry
from ipo_financial_agent.schemas import (
    Assessment,
    Evidence,
    Finding,
    FollowUpRequest,
    ResearchTask,
    ReviewResult,
)


class ResearchReviewerAgent:
    """Validate evidence and Finding quality without mutating Agent outputs."""

    def review_financial(
        self,
        *,
        task: ResearchTask,
        evidences: list[Evidence],
        findings: list[Finding],
    ) -> ReviewResult:
        if task.target_agent != "financial":
            raise ValueError("phase-one Reviewer only accepts financial tasks")
        evidence_registry = EvidenceRegistry(evidences)
        finding_registry = FindingRegistry(evidence_registry)
        approved: list[Finding] = []
        rejected_ids: list[str] = []
        follow_ups: list[FollowUpRequest] = []

        for finding in findings:
            try:
                finding_registry.add(finding)
            except ValueError as error:
                rejected_ids.append(finding.finding_id)
                follow_ups.append(
                    FollowUpRequest(
                        follow_up_id=f"FU_{finding.finding_id}_EVIDENCE",
                        target_agent="financial",
                        related_finding_ids=[finding.finding_id],
                        question=f"补齐“{finding.title}”缺失或无效的 Evidence。",
                        reason=str(error),
                        required_evidence=list(finding.evidence_ids),
                        priority="P0",
                    )
                )
                continue
            if not finding.required_checks or not finding.interpretation.strip():
                rejected_ids.append(finding.finding_id)
                follow_ups.append(
                    FollowUpRequest(
                        follow_up_id=f"FU_{finding.finding_id}_QUALITY",
                        target_agent="financial",
                        related_finding_ids=[finding.finding_id],
                        question=f"补全“{finding.title}”的解释和补证要求。",
                        reason="Finding 必须同时包含事实、解释、风险、证据和补证材料。",
                        required_evidence=list(finding.required_checks),
                        priority="P0",
                    )
                )
                continue
            approved.append(finding)
            follow_ups.append(
                FollowUpRequest(
                    follow_up_id=f"FU_{finding.finding_id}_CHECK",
                    target_agent="financial",
                    related_finding_ids=[finding.finding_id],
                    question=f"验证“{finding.title}”的替代解释并补齐管理层材料。",
                    reason="该异常已获证据支持，但原因与风险升级条件仍需外部材料闭环。",
                    required_evidence=list(finding.required_checks),
                    priority="P1" if finding.risk_level == "medium" else "P0",
                )
            )

        approved_evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for finding in approved
                for evidence_id in finding.evidence_ids
            )
        )
        calculation_ids = [
            item.evidence_id
            for item in evidence_registry.require(approved_evidence_ids)
            if item.source_type == "calculation"
        ] if approved_evidence_ids else []
        if approved:
            conclusion = "；".join(
                f"{item.statement}{item.interpretation}" for item in approved
            )
            confidence = "high" if len(calculation_ids) >= 3 else "medium"
        else:
            conclusion = "尚无通过 Evidence 完整性与 Finding 质量检查的财务结论。"
            confidence = "low"
        if any(item.risk_level == "high" for item in approved):
            status = "high_risk"
        elif approved and follow_ups:
            status = "conditional_pass"
        elif approved:
            status = "pass"
        else:
            status = "insufficient_evidence"

        return ReviewResult(
            review_status=status,
            historical_financial_assessment=Assessment(
                conclusion=conclusion,
                confidence=confidence,
                evidence_ids=calculation_ids or approved_evidence_ids,
            ),
            future_earning_assessment=Assessment(
                conclusion="Financial-only 最小闭环不单独判断未来盈利能力。",
                confidence="low",
                evidence_ids=[],
            ),
            negative_matter_assessment=Assessment(
                conclusion="Financial-only 最小闭环不覆盖法务与负面事项。",
                confidence="low",
                evidence_ids=[],
            ),
            approved_finding_ids=[item.finding_id for item in approved],
            rejected_finding_ids=rejected_ids,
            follow_up_requests=follow_ups,
            key_risks=[item.title for item in approved if item.risk_level in {"medium", "high"}],
            p0_questions=[item.question for item in follow_ups if item.priority == "P0"],
            p1_questions=[item.question for item in follow_ups if item.priority == "P1"],
        )
