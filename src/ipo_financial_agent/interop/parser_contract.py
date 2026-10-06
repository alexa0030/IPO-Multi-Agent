from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


SAFE_DOCUMENT_ID = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")


class ParserContractError(ValueError):
    """Raised when extracted data cannot be safely exposed to Java."""


class ParserAnalysisRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company: str = Field(min_length=1)
    document_id: str = Field(alias="documentId", min_length=1)
    reporting_entity: str = Field(alias="reportingEntity", min_length=1)


class ContractFinancialFact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    fact_id: str = Field(alias="factId")
    metric_code: str = Field(alias="metricCode")
    period: str
    value: float
    unit: str | None = None
    page: int | None = None
    reporting_entity: str = Field(alias="reportingEntity")


class AnalysisContract(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company: str
    document_id: str = Field(alias="documentId")
    reporting_entity: str = Field(alias="reportingEntity")
    facts: list[ContractFinancialFact]


class VerifiedFactManifest(BaseModel):
    reporting_entity: str
    fact_ids: list[str] = Field(min_length=1)


class VerifiedFactContractService:
    """Exports only facts explicitly approved in a per-document manifest.

    The manifest is a review gate. The service never guesses between duplicate
    issuer/subsidiary tables or balance/cash-flow occurrences of the same tag.
    """

    def __init__(self, extracted_dir: str | Path):
        self.extracted_dir = Path(extracted_dir).resolve()

    def load(self, request: ParserAnalysisRequest) -> AnalysisContract:
        if not SAFE_DOCUMENT_ID.fullmatch(request.document_id):
            raise ParserContractError("invalid documentId")
        document_dir = self.extracted_dir / request.document_id
        kb_path = document_dir / "financial_kb.json"
        manifest_path = document_dir / "verified_fact_manifest.json"
        if not kb_path.is_file():
            raise ParserContractError("financial_kb.json not found")
        if not manifest_path.is_file():
            raise ParserContractError("verified_fact_manifest.json not found")
        kb = json.loads(kb_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return self.build(request, kb, manifest)

    def build(
        self,
        request: ParserAnalysisRequest,
        financial_kb: dict[str, Any],
        manifest_payload: dict[str, Any],
    ) -> AnalysisContract:
        manifest = VerifiedFactManifest.model_validate(manifest_payload)
        if manifest.reporting_entity != request.reporting_entity:
            raise ParserContractError("reporting entity does not match verified manifest")
        if len(manifest.fact_ids) != len(set(manifest.fact_ids)):
            raise ParserContractError("verified manifest contains duplicate fact IDs")

        facts_by_id: dict[str, dict[str, Any]] = {}
        duplicate_ids: set[str] = set()
        for raw in financial_kb.get("statement_facts", []):
            fact_id = raw.get("fact_id")
            if not fact_id:
                continue
            if fact_id in facts_by_id:
                duplicate_ids.add(fact_id)
            facts_by_id[fact_id] = raw
        if duplicate_ids & set(manifest.fact_ids):
            raise ParserContractError("financial knowledge base contains duplicate verified fact IDs")

        exported: list[ContractFinancialFact] = []
        missing: list[str] = []
        for fact_id in manifest.fact_ids:
            raw = facts_by_id.get(fact_id)
            if raw is None:
                missing.append(fact_id)
                continue
            if raw.get("value") is None or raw.get("canonical_tag") in (None, "other"):
                raise ParserContractError(f"verified fact is not numeric: {fact_id}")
            fact_entity = raw.get("reporting_entity")
            if fact_entity and fact_entity != request.reporting_entity:
                raise ParserContractError(f"verified fact belongs to another entity: {fact_id}")
            exported.append(
                ContractFinancialFact(
                    factId=fact_id,
                    metricCode=raw["canonical_tag"],
                    period=str(raw["period"]),
                    value=float(raw["value"]),
                    unit=raw.get("unit"),
                    page=raw.get("page"),
                    reportingEntity=request.reporting_entity,
                )
            )
        if missing:
            raise ParserContractError("verified facts missing from knowledge base: " + ", ".join(missing))
        return AnalysisContract(
            company=request.company,
            documentId=request.document_id,
            reportingEntity=request.reporting_entity,
            facts=exported,
        )
