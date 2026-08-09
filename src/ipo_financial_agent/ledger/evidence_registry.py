from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ipo_financial_agent.schemas import Evidence, adapt_legacy_evidence


class EvidenceRegistry:
    """Append-only evidence registry with calculation-lineage enforcement."""

    def __init__(self, evidence: Iterable[Evidence] = ()) -> None:
        self._items: dict[str, Evidence] = {}
        for item in evidence:
            self.add(item)

    @classmethod
    def from_legacy(
        cls, evidence: Iterable[Any], *, created_by: str
    ) -> "EvidenceRegistry":
        """Build a canonical registry through the strict legacy boundary."""
        return cls(
            adapt_legacy_evidence(item, created_by=created_by) for item in evidence
        )

    def add(self, evidence: Evidence) -> Evidence:
        existing = self._items.get(evidence.evidence_id)
        if existing is not None:
            if existing != evidence:
                raise ValueError(f"conflicting evidence_id: {evidence.evidence_id}")
            return existing
        if evidence.source_type == "calculation":
            missing = [
                item
                for item in evidence.input_evidence_ids
                if item not in self._items
            ]
            if missing:
                raise ValueError(
                    f"calculation evidence {evidence.evidence_id} has missing inputs: {missing}"
                )
        self._items[evidence.evidence_id] = evidence
        return evidence

    def extend(self, evidence: Iterable[Evidence]) -> list[Evidence]:
        return [self.add(item) for item in evidence]

    def get(self, evidence_id: str) -> Evidence | None:
        return self._items.get(evidence_id)

    def require(self, evidence_ids: Iterable[str]) -> list[Evidence]:
        requested = list(evidence_ids)
        missing = [item for item in requested if item not in self._items]
        if missing:
            raise ValueError(f"missing Evidence references: {missing}")
        return [self._items[item] for item in requested]

    def all(self) -> list[Evidence]:
        return list(self._items.values())
