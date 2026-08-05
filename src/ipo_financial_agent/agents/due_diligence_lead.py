"""Deterministic Mainline A due diligence synthesis."""

from __future__ import annotations

from typing import Any

from ipo_financial_agent.models_agent import (
    Challenge,
    DiligenceQuestion,
    DueDiligenceConclusion,
    Finding,
)


class DueDiligenceLeadAgent:
    """Turn validated research and challenges into a bounded DD conclusion."""

    def synthesize(
        self,
        *,
        findings: list[Finding],
        challenges: list[Challenge],
        risk_review: Any,
        metrics: list[Any],
        financial_findings: list[Any],
    ) -> tuple[DueDiligenceConclusion, list[DiligenceQuestion]]:
        finding_map = {item.finding_id: item for item in findings}
        questions = [
            self._question_from_challenge(item, finding_map) for item in challenges
        ]
        risk_level = getattr(risk_review, "risk_level", "Medium")
        historical = self._historical_grade(metrics, financial_findings)
        future = self._future_grade(findings)
        verdict = self._verdict(risk_level, challenges)
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for finding in findings
                for evidence_id in finding.evidence_ids
            )
        )
        strengths = [
            item.conclusion
            for item in findings
            if item.evidence_strength in {"strong", "medium"}
            and item.agent_name in {"company_business", "industry_competition"}
            and not item.risks
        ][:5]
        risks = list(getattr(risk_review, "major_risks", []) or [])[:8]
        conclusion = DueDiligenceConclusion(
            verdict=verdict,
            historical_financial_quality=historical,
            future_earning_power=future,
            material_risk_level=risk_level,
            key_strengths=strengths,
            key_risks=risks,
            evidence_ids=evidence_ids,
            follow_up_question_ids=[item.question_id for item in questions],
            confidence=min(0.9, len(evidence_ids) / 10) if evidence_ids else 0.0,
        )
        return conclusion, questions

    @staticmethod
    def _question_from_challenge(
        challenge: Challenge, finding_map: dict[str, Finding]
    ) -> DiligenceQuestion:
        finding = finding_map.get(challenge.challenged_finding_id or "")
        category_map = {
            "financial_dd": "financial",
            "industry_competition": "industry_competition",
            "legal_governance": "legal_governance",
            "company_business": "company_business",
        }
        priority_map = {"critical": "P0", "important": "P1", "minor": "P2"}
        return DiligenceQuestion(
            priority=priority_map[challenge.severity],
            category=category_map.get(challenge.target_agent, "other"),
            question=challenge.question,
            rationale=challenge.reason,
            current_evidence_ids=list(finding.evidence_ids) if finding else [],
            requested_materials=challenge.required_evidence,
            downside_if_unresolved=(
                "The unresolved issue may change whether diligence should proceed."
                if challenge.severity == "critical"
                else "The unresolved issue may materially change the company-quality assessment."
            ),
        )

    @staticmethod
    def _historical_grade(metrics: list[Any], findings: list[Any]) -> str:
        triggered = [item for item in findings if getattr(item, "triggered", False)]
        if any(
            getattr(item, "severity", "") in {"high", "critical"} for item in triggered
        ):
            return "weak"
        if metrics:
            return "moderate"
        return "insufficient_evidence"

    @staticmethod
    def _future_grade(findings: list[Finding]) -> str:
        agents = {item.agent_name for item in findings}
        if {"company_business", "industry_competition"} <= agents:
            return "moderate"
        if "company_business" in agents:
            return "weak"
        return "insufficient_evidence"

    @staticmethod
    def _verdict(risk_level: str, challenges: list[Challenge]) -> str:
        if any(item.severity == "critical" for item in challenges):
            return "pause"
        if risk_level == "High":
            return "pause"
        if risk_level == "Medium" or challenges:
            return "conditional_proceed"
        return "proceed"
