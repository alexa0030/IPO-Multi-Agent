"""In-memory Research Ledger with deterministic evidence deduplication."""

from __future__ import annotations

from collections.abc import Iterable

from ipo_financial_agent.models_agent import Evidence, Finding


class EvidenceIntegrityError(ValueError):
    """Raised when a conclusion references evidence absent from the ledger."""


class EvidenceStore:
    """Collect evidence and reject ungrounded or conflicting conclusions."""

    def __init__(self, evidence: Iterable[Evidence] = ()) -> None:
        self._evidence: dict[str, Evidence] = {}
        self._findings: dict[str, Finding] = {}
        self.add_evidence(evidence)

    @property
    def evidence(self) -> list[Evidence]:
        return list(self._evidence.values())

    @property
    def findings(self) -> list[Finding]:
        return list(self._findings.values())

    def add_evidence(self, items: Iterable[Evidence]) -> None:
        for item in items:
            previous = self._evidence.get(item.evidence_id)
            if previous is not None and previous != item:
                raise EvidenceIntegrityError(
                    f"evidence_id collision: {item.evidence_id}"
                )
            self._evidence[item.evidence_id] = item

    def add_findings(self, items: Iterable[Finding]) -> None:
        for item in items:
            missing = [
                evidence_id
                for evidence_id in item.evidence_ids
                if evidence_id not in self._evidence
            ]
            if missing:
                raise EvidenceIntegrityError(
                    f"finding {item.finding_id} references missing evidence: {missing}"
                )
            previous = self._findings.get(item.finding_id)
            if previous is not None and previous != item:
                raise EvidenceIntegrityError(
                    f"finding_id collision: {item.finding_id}"
                )
            self._findings[item.finding_id] = item

    def validate_evidence_ids(self, evidence_ids: Iterable[str]) -> None:
        missing = [item for item in evidence_ids if item not in self._evidence]
        if missing:
            raise EvidenceIntegrityError(f"missing evidence: {missing}")

