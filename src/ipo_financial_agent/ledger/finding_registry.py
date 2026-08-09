from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ipo_financial_agent.schemas import (
    FinancialResearchTopic,
    Finding,
    adapt_legacy_finding,
)

from .evidence_registry import EvidenceRegistry


class FindingRegistry:
    """Append-only findings whose Evidence references are valid at registration."""

    def __init__(self, evidence_registry: EvidenceRegistry) -> None:
        self.evidence_registry = evidence_registry
        self._items: dict[str, Finding] = {}

    def add(self, finding: Finding) -> Finding:
        self.evidence_registry.require(finding.evidence_ids)
        existing = self._items.get(finding.finding_id)
        if existing is not None:
            if existing != finding:
                raise ValueError(f"conflicting finding_id: {finding.finding_id}")
            return existing
        self._items[finding.finding_id] = finding
        return finding

    def add_legacy(
        self,
        finding: Any,
        *,
        task_id: str,
        topic: FinancialResearchTopic = FinancialResearchTopic.OTHER_COMPANY_SPECIFIC,
        answered_question_ids: Iterable[str] = (),
    ) -> Finding:
        """Adapt and register one legacy Finding with evidence enforcement."""
        return self.add(
            adapt_legacy_finding(
                finding,
                task_id=task_id,
                topic=topic,
                answered_question_ids=answered_question_ids,
            )
        )

    def extend(self, findings: Iterable[Finding]) -> list[Finding]:
        return [self.add(item) for item in findings]

    def all(self) -> list[Finding]:
        return list(self._items.values())
