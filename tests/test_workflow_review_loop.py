from __future__ import annotations

from ipo_financial_agent.schemas import IPOResearchState
from ipo_financial_agent.workflow.graph import IPOAnalysisState, _SequentialFallback


def _nodes(calls: list[str], *, challenged: bool) -> dict[str, object]:
    names = [
        "document_prepare",
        "research_manager",
        "run_financial_agent",
        "run_prospectus_agent",
        "run_industry_agent",
        "run_legal_governance_agent",
        "run_risk_reviewer",
        "run_skeptic",
        "run_targeted_followup",
        "run_due_diligence_lead",
        "run_report_writer",
        "run_report_reviewer",
        "run_report_revision",
        "export_outputs",
    ]

    def make_node(name: str):
        def node(state):
            calls.append(name)
            if name == "run_skeptic" and challenged and state.get("followup_round", 0) == 0:
                return {"challenges": ["missing evidence"]}
            if name == "run_targeted_followup":
                return {"followup_round": 1}
            return {}

        return node

    return {name: make_node(name) for name in names}


def test_graph_uses_canonical_state_contract():
    assert IPOAnalysisState is IPOResearchState
    assert "document_id" in IPOResearchState.__annotations__


def test_sequential_fallback_skips_followup_without_challenge():
    calls: list[str] = []
    _SequentialFallback(_nodes(calls, challenged=False)).invoke({})
    assert "run_targeted_followup" not in calls
    assert calls.count("run_risk_reviewer") == 1


def test_sequential_fallback_rereviews_followup_evidence():
    calls: list[str] = []
    _SequentialFallback(_nodes(calls, challenged=True)).invoke({})
    followup = calls.index("run_targeted_followup")
    assert calls[followup + 1 : followup + 3] == ["run_risk_reviewer", "run_skeptic"]
    assert calls.count("run_targeted_followup") == 1
