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
        questions.extend(
            self._question_from_risk_review(item)
            for item in (getattr(risk_review, "investment_questions", []) or [])
            if item
        )
        unique_questions: dict[str, DiligenceQuestion] = {}
        priority_rank = {"P0": 0, "P1": 1, "P2": 2}
        for item in questions:
            previous = unique_questions.get(item.question)
            if previous is None or priority_rank[item.priority] < priority_rank[previous.priority]:
                unique_questions[item.question] = item
        questions = list(unique_questions.values())[:15]
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
            and not any(token in item.conclusion for token in ("待核", "尚未", "未取得"))
        ][:5]
        risks = list(getattr(risk_review, "major_risks", []) or [])[:8]
        conclusion = DueDiligenceConclusion(
            verdict=verdict,
            historical_financial_quality=historical,
            future_earning_power=future,
            material_risk_level=risk_level,
            company_profile=self._company_profile(findings),
            key_strengths=strengths,
            key_risks=risks,
            evidence_ids=evidence_ids,
            follow_up_question_ids=[item.question_id for item in questions],
            confidence=min(0.9, len(evidence_ids) / 10) if evidence_ids else 0.0,
        )
        return conclusion, questions

    @classmethod
    def _question_from_risk_review(cls, question: str) -> DiligenceQuestion:
        category = cls._question_category(question)
        critical_terms = (
            "财务造假", "收入确认", "资金占用", "表外负债", "处罚", "诉讼",
            "实控人", "经营现金流", "偿债", "关联交易",
        )
        priority = "P0" if any(term in question for term in critical_terms) else "P1"
        materials = {
            "financial": ["财务科目明细及口径桥接表", "银行流水或期后回款/付款证明"],
            "legal_governance": ["官方登记、监管或司法原文", "律师核查意见及当前状态说明"],
            "industry_competition": ["注明日期和口径的外部行业原文", "可比公司或客户访谈记录"],
            "company_business": ["招股书对应原文", "客户、供应商或业务台账"],
            "other": ["支持管理层解释的原始材料"],
        }[category]
        return DiligenceQuestion(
            priority=priority,
            category=category,
            question=question,
            rationale="风险复核 Agent 将该事项列为尚未闭环的核查问题。",
            requested_materials=materials,
            downside_if_unresolved="若解释与原始证据不能相互印证，可能下调公司质量或风险判断。",
        )

    @staticmethod
    def _question_category(question: str) -> str:
        if any(term in question for term in ("收入", "利润", "现金", "应收", "存货", "负债", "借款", "毛利", "财务", "审计")):
            return "financial"
        if any(term in question for term in ("诉讼", "处罚", "监管", "关联交易", "实控人", "股权", "登记")):
            return "legal_governance"
        if any(term in question for term in ("行业", "市场", "竞争", "政策", "可比公司")):
            return "industry_competition"
        if any(term in question for term in ("客户", "供应商", "产品", "业务", "子公司", "研发")):
            return "company_business"
        return "other"

    @staticmethod
    def _company_profile(findings: list[Finding]) -> str:
        for item in findings:
            if (
                item.agent_name == "company_business"
                and any(term in item.question for term in ("商业模式", "销售什么"))
            ):
                return item.conclusion[:500]
        return ""

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
                "若关键解释无法由原始证据支持，尽调应暂停并重新评估。"
                if challenge.severity == "critical"
                else "若该事项无法闭环，可能实质影响公司质量或风险判断。"
            ),
        )

    @staticmethod
    def _historical_grade(metrics: list[Any], findings: list[Any]) -> str:
        triggered = [item for item in findings if getattr(item, "triggered", False)]
        if any(
            getattr(item, "severity", "") in {"high", "critical"}
            and getattr(item, "assessment_status", "observation")
            in {"unexplained", "contradiction"}
            for item in triggered
        ):
            return "weak"
        if metrics and not triggered and len(metrics) >= 8:
            return "strong"
        if metrics or triggered:
            return "moderate"
        return "insufficient_evidence"

    @staticmethod
    def _future_grade(findings: list[Finding]) -> str:
        company = [
            item
            for item in findings
            if item.agent_name == "company_business"
            and item.evidence_strength in {"strong", "medium"}
            and not item.risks
        ]
        independently_supported_industry = [
            item
            for item in findings
            if item.agent_name == "industry_competition"
            and item.evidence_strength in {"strong", "medium"}
            and not item.risks
        ]
        if len(company) >= 5 and len(independently_supported_industry) >= 4:
            return "strong"
        if len(company) >= 2 and len(independently_supported_industry) >= 2:
            return "moderate"
        if company:
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
