"""Skeptic Agent: convert material evidence gaps into routable challenges."""

from __future__ import annotations

from typing import Any

from ipo_financial_agent.models_agent import Challenge, Finding


class SkepticAgent:
    """Review the ledger without redoing specialist research."""

    MAX_CHALLENGES = 3

    def review(
        self,
        *,
        findings: list[Finding],
        contradictions: list[Any],
        open_questions: list[str],
    ) -> list[Challenge]:
        candidates: list[Challenge] = []

        for contradiction in contradictions:
            question = getattr(contradiction, "question", "")
            if not question:
                continue
            source = getattr(contradiction, "source_2", "")
            target = self._target_for_text(f"{source} {question}")
            candidates.append(
                Challenge(
                    target_agent=target,
                    question=question,
                    reason=(
                        "Cross-agent conclusions conflict: "
                        f"{getattr(contradiction, 'statement_1', '')} / "
                        f"{getattr(contradiction, 'statement_2', '')}"
                    ),
                    severity=(
                        "critical"
                        if getattr(contradiction, "severity", "") == "high"
                        else "important"
                    ),
                    required_evidence=self._required_evidence(target),
                )
            )

        for finding in findings:
            if len(candidates) >= self.MAX_CHALLENGES:
                break
            for question in finding.open_questions:
                if not question:
                    continue
                candidates.append(
                    Challenge(
                        target_agent=finding.agent_name,
                        challenged_finding_id=finding.finding_id,
                        question=question,
                        reason=(
                            "A specialist agent marked this evidence gap as unresolved."
                        ),
                        severity="important",
                        required_evidence=self._required_evidence(finding.agent_name),
                    )
                )
                break

        for question in open_questions:
            if len(candidates) >= self.MAX_CHALLENGES:
                break
            target = self._target_for_text(question)
            candidates.append(
                Challenge(
                    target_agent=target,
                    question=question,
                    reason="The research ledger still contains an open question.",
                    severity="important",
                    required_evidence=self._required_evidence(target),
                )
            )

        unique: dict[str, Challenge] = {}
        for item in candidates:
            unique[item.challenge_id] = item
        return list(unique.values())[: self.MAX_CHALLENGES]

    @staticmethod
    def _target_for_text(text: str) -> str:
        lowered = text.lower()
        if any(
            keyword in lowered
            for keyword in (
                "regulatory",
                "litigation",
                "penalty",
                "related party",
                "controller",
                "\u76d1\u7ba1",
                "\u8bc9\u8bbc",
                "\u5904\u7f5a",
                "\u5173\u8054\u4ea4\u6613",
                "\u5b9e\u63a7\u4eba",
            )
        ):
            return "legal_governance"
        if any(
            keyword in lowered
            for keyword in (
                "industry",
                "market",
                "valuation",
                "search",
                "\u884c\u4e1a",
                "\u5e02\u573a",
                "\u4f30\u503c",
                "\u641c\u7d22",
            )
        ):
            return "industry_competition"
        if any(
            keyword in lowered
            for keyword in (
                "financial",
                "revenue",
                "profit",
                "cash",
                "gross margin",
                "\u8d22\u52a1",
                "\u6536\u5165",
                "\u5229\u6da6",
                "\u73b0\u91d1",
                "\u6bdb\u5229",
            )
        ):
            return "financial_dd"
        return "company_business"

    @staticmethod
    def _required_evidence(target: str) -> list[str]:
        if target == "industry_competition":
            return ["official regulator or exchange source", "dated external URL"]
        if target == "legal_governance":
            return ["prospectus legal section", "official registry or court source"]
        if target == "financial_dd":
            return [
                "source financial statement page",
                "calculation trace",
                "related note",
            ]
        return ["prospectus source page", "company structure or business section"]
