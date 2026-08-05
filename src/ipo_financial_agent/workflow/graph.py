"""
IPO Investment Research Multi-Agent Collaboration Graph

Architecture:
    START -> document_prepare (data layer: PDF load + section detect)
          -> research_manager  (agent layer: plan research tasks)
          -> [fan-out: 4 parallel Agent branches]
              |- Financial Analyst Agent (Tool-Augmented:
              |    internally calls extraction, metrics, forensic engine)
              |- Prospectus Agent
              |- Industry Agent
              |- Legal & Governance Agent
          -> [fan-in] Investment Committee Agent (cross-check + contradiction)
          -> Report Writer Agent -> Evidence/Compliance Reviewer -> bounded revision
          -> export_outputs -> END

Key architectural principle:
  - The Financial Analyst Agent is a TOOL-AUGMENTED AGENT, not a pipeline step.
    It autonomously orchestrates: extraction -> metrics -> 6-rule risk engine
    -> 20-rule forensic engine -> LLM reasoning (Layer 3).
  - document_prepare is a DATA node (not an Agent).
  - research_manager is a real AGENT that plans and delegates.
  - agent_messages enables inter-agent communication.
  - financial_findings + rule_trigger_events expose forensic results to
    downstream Agents (Investment Committee, Report Writer).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class IPOAnalysisState(TypedDict, total=False):
    # --- input ---
    pdf_path: str
    company: str
    document_id: str
    llm_mode: str

    # --- document layer (set by document_prepare) ---
    pages: list[Any]
    section_hits: list[Any]
    candidate_pages: list[Any]
    topic_page_groups: dict[str, list[Any]]

    # --- research plan (set by research_manager) ---
    research_plan: Any  # ResearchPlan
    agent_messages: Annotated[list, operator.add]  # auto-merge from parallel branches
    research_evidence: Annotated[list, operator.add]
    research_findings: Annotated[list, operator.add]
    open_questions: Annotated[list, operator.add]
    challenges: list
    followup_round: int
    diligence_questions: list[Any]
    due_diligence_conclusion: Any

    # --- Financial Analyst Agent outputs (Tool-Augmented, single node) ---
    raw_statements: list[Any]  # from extraction tool
    extraction_result: Any  # FinancialExtractionResult (facts + notes)
    metrics: list[Any]  # from metric engine tool
    risks: list[Any]  # from 6-rule risk engine tool
    financial_findings: list[Any]  # from 20-rule forensic engine tool
    rule_trigger_events: list[Any]  # subset of findings where triggered=True
    analysis: Any  # AnalysisResult (LLM reasoning / offline summary)

    # --- parallel agent outputs ---
    prospectus_analysis: Any  # ProspectusAnalysis
    industry_analysis: Any  # IndustryAnalysis
    legal_governance_analysis: Any  # LegalGovernanceAnalysis

    # --- fan-in + final ---
    risk_review: Any  # RiskReview
    final_report: str  # final markdown report
    report_review: Any  # ReportReview
    report_revision_performed: bool
    artifacts: Any


# Node execution order (also used by _SequentialFallback)
ORDERED_NODES = [
    "document_prepare",
    "research_manager",
    "run_financial_agent",  # single Tool-Augmented Agent node
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


class _SequentialFallback:
    """LangGraph not installed -> sequential execution."""

    def __init__(self, nodes: dict[str, Any]) -> None:
        self.nodes = nodes

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        current = dict(state)
        if "agent_messages" not in current:
            current["agent_messages"] = []
        for key in ("research_evidence", "research_findings", "open_questions"):
            current.setdefault(key, [])
        current.setdefault("challenges", [])
        current.setdefault("followup_round", 0)
        for name in ORDERED_NODES:
            node_fn = self.nodes.get(name)
            if node_fn is None:
                continue
            update = node_fn(current) or {}
            # Manual merge for append-only reducer fields.
            for key in (
                "agent_messages",
                "research_evidence",
                "research_findings",
                "open_questions",
            ):
                if key in update:
                    existing = current.get(key, [])
                    existing.extend(update.pop(key))
                    current[key] = existing
            current.update(update)
        return current


def build_graph(nodes: dict[str, Any]):
    """
    Build the Agent Collaboration Graph.

      START -> document_prepare -> research_manager
        |- run_financial_agent (Tool-Augmented: extraction+metrics+forensic+reasoning)
        |- run_prospectus_agent
        |- run_industry_agent
        |- run_legal_governance_agent
      -> run_risk_reviewer -> skeptic -> DD lead -> writer -> final reviewer
      -> bounded revision -> export_outputs -> END

    The financial branch is a SINGLE Agent node (not a 5-step pipeline).
    The Financial Analyst Agent internally orchestrates its tools.
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _SequentialFallback(nodes)

    graph = StateGraph(IPOAnalysisState)

    for name in ORDERED_NODES:
        graph.add_node(name, nodes[name])

    # Linear prefix: data -> manager
    graph.add_edge(START, "document_prepare")
    graph.add_edge("document_prepare", "research_manager")

    # Fan-out: manager -> 4 parallel Agent branches
    graph.add_edge("research_manager", "run_financial_agent")
    graph.add_edge("research_manager", "run_prospectus_agent")
    graph.add_edge("research_manager", "run_industry_agent")
    graph.add_edge("research_manager", "run_legal_governance_agent")

    # Fan-in: 4 branches -> risk_reviewer (Investment Committee)
    graph.add_edge("run_financial_agent", "run_risk_reviewer")
    graph.add_edge("run_prospectus_agent", "run_risk_reviewer")
    graph.add_edge("run_industry_agent", "run_risk_reviewer")
    graph.add_edge("run_legal_governance_agent", "run_risk_reviewer")

    graph.add_edge("run_risk_reviewer", "run_skeptic")

    def route_after_skeptic(state: IPOAnalysisState) -> str:
        if state.get("challenges") and state.get("followup_round", 0) < 1:
            return "run_targeted_followup"
        return "run_due_diligence_lead"

    graph.add_conditional_edges(
        "run_skeptic",
        route_after_skeptic,
        {
            "run_targeted_followup": "run_targeted_followup",
            "run_due_diligence_lead": "run_due_diligence_lead",
        },
    )
    graph.add_edge("run_targeted_followup", "run_due_diligence_lead")
    graph.add_edge("run_due_diligence_lead", "run_report_writer")
    graph.add_edge("run_report_writer", "run_report_reviewer")
    graph.add_edge("run_report_reviewer", "run_report_revision")
    graph.add_edge("run_report_revision", "export_outputs")
    graph.add_edge("export_outputs", END)

    return graph.compile()
