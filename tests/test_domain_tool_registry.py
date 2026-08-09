from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ipo_financial_agent.models import MetricResult
from ipo_financial_agent.schemas import Evidence
from ipo_financial_agent.tools.domain_tools import (
    DomainToolContext,
    build_domain_tool_registry,
    get_agent_tools,
)


def test_domain_tool_exposes_structured_contract(monkeypatch):
    monkeypatch.setattr(
        "ipo_financial_agent.tools.domain_tools.search_industry_info",
        lambda company, business_description="": [
            {"company": company, "business_description": business_description}
        ],
    )
    registry = build_domain_tool_registry()

    output = registry.execute(
        "industry",
        "search_industry_info",
        company="Issuer",
        business_description="Robotics",
    )

    assert output.results == [
        {"company": "Issuer", "business_description": "Robotics"}
    ]
    description = next(
        item
        for item in registry.describe("industry")
        if item["name"] == "search_industry_info"
    )
    assert description["input_schema"]["required"] == ["company"]
    assert description["output_schema"]["properties"]["results"]


def test_domain_tool_rejects_invalid_input_and_role():
    registry = build_domain_tool_registry()

    with pytest.raises(ValidationError):
        registry.execute("industry", "search_industry_info", company="")
    with pytest.raises(PermissionError):
        registry.execute("company", "search_legal_governance_info", company="Issuer")


def test_prospectus_tool_returns_ranked_page_excerpts():
    registry = build_domain_tool_registry(
        DomainToolContext(
            pages=(
                SimpleNamespace(page=8, text="Customer concentration is disclosed here."),
                SimpleNamespace(page=12, text="Customer concentration and customer contracts."),
            )
        )
    )

    output = registry.execute(
        "company_business",
        "search_prospectus",
        query="customer concentration",
        max_results=2,
    )

    assert [item.page_number for item in output.results] == [12, 8]
    assert all(item.score >= 1 for item in output.results)


def test_financial_and_evidence_tools_are_read_only_and_role_scoped():
    metric = MetricResult(
        metric_id="M-1",
        document_id="D-1",
        metric_name="Gross margin",
        metric_code="gross_margin",
        period="2025",
        value=0.37,
        display_value="37.0%",
        formula="gross_profit / revenue",
    )
    evidence = Evidence(
        evidence_id="E-1",
        source_type="prospectus",
        title="Income statement",
        content="Gross profit disclosure",
        page_number=30,
        source_quality="A",
        created_by="financial",
    )
    registry = build_domain_tool_registry(
        DomainToolContext(metrics=(metric,), evidence=(evidence,))
    )

    metrics = registry.execute(
        "financial", "get_financial_metric", metric_code="gross_margin"
    )
    verified = registry.execute(
        "reviewer", "verify_evidence", evidence_ids=["E-1", "E-MISSING"]
    )

    assert metrics.metrics[0]["value"] == 0.37
    assert not verified.valid
    assert verified.missing_ids == ["E-MISSING"]
    assert all(not item["mutates_evidence"] for item in registry.describe())
    with pytest.raises(PermissionError):
        registry.execute(
            "industry_competition",
            "get_financial_metric",
            metric_code="gross_margin",
        )


def test_all_research_roles_can_run_bounded_web_followup():
    for role in ("research_manager", "company_business", "financial", "industry_competition", "legal_governance", "reviewer"):
        assert "search_targeted_followup" in get_agent_tools(role)
