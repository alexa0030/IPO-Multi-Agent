from __future__ import annotations

import pytest

from ipo_financial_agent.interop.parser_contract import (
    ParserAnalysisRequest,
    ParserContractError,
    VerifiedFactContractService,
)


REQUEST = ParserAnalysisRequest(
    company="深圳市汉森软件股份有限公司",
    documentId="hosonsoft",
    reportingEntity="深圳市汉森软件股份有限公司",
)


def _fact(fact_id: str, code: str, value: float, entity: str | None = None) -> dict:
    return {
        "fact_id": fact_id,
        "canonical_tag": code,
        "period": "2025",
        "value": value,
        "unit": "CNY thousand",
        "page": 21,
        "reporting_entity": entity,
    }


def test_manifest_exports_only_explicitly_verified_facts():
    service = VerifiedFactContractService("data/extracted")
    kb = {
        "statement_facts": [
            _fact("issuer-revenue", "revenue", 596_909),
            _fact("subsidiary-revenue", "revenue", 51_299, "某子公司"),
        ]
    }

    result = service.build(
        REQUEST,
        kb,
        {"reporting_entity": REQUEST.reporting_entity, "fact_ids": ["issuer-revenue"]},
    )

    payload = result.model_dump(by_alias=True)
    assert [fact["factId"] for fact in payload["facts"]] == ["issuer-revenue"]
    assert payload["facts"][0]["reportingEntity"] == REQUEST.reporting_entity


def test_manifest_rejects_fact_from_another_entity():
    service = VerifiedFactContractService("data/extracted")
    kb = {"statement_facts": [_fact("wrong-entity", "inventory", 51_299, "某子公司")]}

    with pytest.raises(ParserContractError, match="another entity"):
        service.build(
            REQUEST,
            kb,
            {"reporting_entity": REQUEST.reporting_entity, "fact_ids": ["wrong-entity"]},
        )


def test_manifest_rejects_missing_or_duplicate_ids():
    service = VerifiedFactContractService("data/extracted")
    kb = {"statement_facts": [_fact("issuer-revenue", "revenue", 596_909)]}

    with pytest.raises(ParserContractError, match="duplicate fact IDs"):
        service.build(
            REQUEST,
            kb,
            {
                "reporting_entity": REQUEST.reporting_entity,
                "fact_ids": ["issuer-revenue", "issuer-revenue"],
            },
        )
    with pytest.raises(ParserContractError, match="missing"):
        service.build(
            REQUEST,
            kb,
            {"reporting_entity": REQUEST.reporting_entity, "fact_ids": ["missing-id"]},
        )
