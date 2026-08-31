from __future__ import annotations

import hashlib
import re
import shutil
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ipo_financial_agent.agents.financial_agent import FinancialAnalysisAgent
from ipo_financial_agent.agents.due_diligence_lead import DueDiligenceLeadAgent
from ipo_financial_agent.agents.industry_agent import IndustryAgent
from ipo_financial_agent.agents.legal_governance_agent import LegalGovernanceAgent
from ipo_financial_agent.agents.prospectus_agent import ProspectusAgent
from ipo_financial_agent.agents.research_manager import ResearchManagerAgent
from ipo_financial_agent.agents.report_reviewer import EvidenceComplianceReviewerAgent
from ipo_financial_agent.agents.report_writer import ReportWriterAgent
from ipo_financial_agent.agents.risk_reviewer import RiskReviewerAgent
from ipo_financial_agent.agents.skeptic import SkepticAgent
from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.document.pdf_loader import PDFLoader
from ipo_financial_agent.document.section_detector import detect_sections
from ipo_financial_agent.document.topic_page_selector import TopicPageSelector
from ipo_financial_agent.llm.client import LLMConfigurationError, OpenAICompatibleClient
from ipo_financial_agent.models import (
    FinancialExtractionResult,
    PipelineArtifacts,
)
from ipo_financial_agent.models_agent import AgentMessage, Evidence
from ipo_financial_agent.ledger import EvidenceRegistry, FindingRegistry
from ipo_financial_agent.schemas import (
    adapt_legacy_challenge,
    adapt_legacy_evidence,
    adapt_legacy_research_patch,
)
from ipo_financial_agent.output.excel_writer import export_financial_workbook
from ipo_financial_agent.output.delivery_writer import (
    enrich_due_diligence_workbook,
    ledger_integrity,
)
from ipo_financial_agent.output.report_writer import write_markdown_report
from ipo_financial_agent.rendering import render_investment_markdown
from ipo_financial_agent.research import (
    build_financial_agent_result,
    financial_research_patch,
    industry_research_patch,
    legal_governance_research_patch,
    prospectus_research_patch,
    register_financial_evidence,
)
from ipo_financial_agent.storage.evidence_store import EvidenceStore
from ipo_financial_agent.storage.json_store import write_json
from ipo_financial_agent.storage.repository import FinancialRepository
from ipo_financial_agent.tools.search_tool import search_targeted_followup
from ipo_financial_agent.workflow.graph import build_graph


class IPOFinancialPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(
        self,
        *,
        pdf_path: str | Path,
        company: str,
        llm_mode: str = "auto",
    ) -> PipelineArtifacts:
        path = Path(pdf_path).resolve()
        if llm_mode not in {"auto", "on", "off"}:
            raise ValueError("llm_mode must be one of: auto, on, off")
        document_id = self._document_id(path)
        effective_llm_mode = self._resolve_llm_mode(llm_mode)
        graph = build_graph(self._nodes())
        result = graph.invoke(
            {
                "pdf_path": str(path),
                "company": company,
                "document_id": document_id,
                "llm_mode": effective_llm_mode,
                "agent_messages": [],
                "research_evidence": [],
                "research_findings": [],
                "open_questions": [],
                "challenges": [],
                "followup_round": 0,
                "review_llm_budget": {"max_calls": 1, "used_calls": 0},
                "tool_call_trace": [],
            }
        )
        return result["artifacts"]

    def _nodes(self) -> dict[str, Any]:
        return {
            "document_prepare": self._document_prepare,
            "research_manager": self._run_research_manager,
            "run_financial_agent": self._run_financial_agent,
            "run_prospectus_agent": self._run_prospectus_agent,
            "run_industry_agent": self._run_industry_agent,
            "run_legal_governance_agent": self._run_legal_governance_agent,
            "run_risk_reviewer": self._run_risk_reviewer,
            "run_skeptic": self._run_skeptic,
            "run_targeted_followup": self._run_targeted_followup,
            "run_due_diligence_lead": self._run_due_diligence_lead,
            "run_report_writer": self._run_report_writer,
            "run_report_reviewer": self._run_report_reviewer,
            "run_report_revision": self._run_report_revision,
            "export_outputs": self._export_outputs,
        }

    # ========================
    # Data layer (not an Agent)
    # ========================

    def _document_prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        """Document preparation: load PDF + detect sections.

        This is a DATA node, not an Agent. It prepares the shared
        knowledge base that all downstream Agents will use.
        """
        pages = PDFLoader(state["pdf_path"]).load()
        hits = detect_sections(pages)
        selector = TopicPageSelector(pages_per_topic=2, context_pages=0)
        topic_groups = selector.select_groups(pages, hits)
        candidates = selector.flatten(topic_groups)
        print(
            f"[document-prepare] PDF loaded: {len(pages)} pages, "
            f"{len(hits)} sections, "
            f"{len(candidates)} candidate pages",
            flush=True,
        )
        return {
            "pages": pages,
            "section_hits": hits,
            "candidate_pages": candidates,
            "topic_page_groups": topic_groups,
        }

    # ========================
    # Research Manager Agent
    # ========================

    def _run_research_manager(self, state: dict[str, Any]) -> dict[str, Any]:
        """Research Manager Agent: plan research tasks for specialist agents."""
        client = None
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)

        agent = ResearchManagerAgent(client)

        section_hits = state.get("section_hits", [])
        section_names = []
        for hit in section_hits:
            name = getattr(hit, "section_name", "") or getattr(hit, "name", "")
            if name:
                section_names.append(name)

        document_summary = {
            "page_count": len(state.get("pages", [])),
            "section_count": len(section_hits),
            "section_names": section_names,
            "signal_texts": [
                getattr(page, "text", "")[:2000]
                for page in state.get("candidate_pages", [])[:24]
            ],
        }

        try:
            plan = agent.plan(
                company=state["company"],
                document_summary=document_summary,
            )
        except Exception as exc:
            if state["llm_mode"] == "on":
                raise
            print(
                f"[research-manager] LLM unavailable ({type(exc).__name__}); "
                "falling back to deterministic company-specific plan.",
                flush=True,
            )
            plan = ResearchManagerAgent().plan(
                company=state["company"],
                document_summary=document_summary,
            )
        print(
            f"[research-manager] Plan created: {len(plan.tasks)} tasks, "
            f"focus={plan.focus_areas}",
            flush=True,
        )

        # Message type=plan: task assignment to agents
        msg = AgentMessage(
            sender="ResearchManager",
            receiver="all",
            content="\n".join(
                [plan.manager_notes]
                + [f"{task.agent_name}: {task.question}" for task in plan.tasks]
            ),
            message_type="plan",
            payload={
                "task_count": len(plan.tasks),
                "focus_areas": plan.focus_areas,
                "page_count": document_summary["page_count"],
                "section_count": document_summary["section_count"],
                "company_specific_hypotheses": plan.company_specific_hypotheses,
            },
        )

        return {
            "research_plan": plan,
            "agent_messages": [msg],
        }

    # ========================
    # Financial Analyst Agent (Tool-Augmented, single node)
    # ========================

    def _run_financial_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        """Financial Analyst Agent -- Tool-Augmented Architecture."""
        client = None
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)

        agent = FinancialAnalysisAgent(client)

        result = agent.analyze(
            document_id=state["document_id"],
            company=state["company"],
            pages=state.get("pages", []),
            section_hits=state.get("section_hits", []),
            topic_page_groups=state.get("topic_page_groups"),
            llm_mode=state["llm_mode"],
        )

        analysis = result["analysis"]
        findings = result.get("findings", [])
        triggered = [f for f in findings if getattr(f, "triggered", False)]
        risks = result.get("risks", [])

        # Extract triggered rule IDs for payload
        triggered_ids = [getattr(f, "rule_id", "") for f in triggered]
        triggered_summary = "；".join(
            f"{getattr(f, 'rule_id', '')} {getattr(f, 'name', '')}"
            f"（{getattr(f, 'assessment_status', 'observation')}）"
            for f in triggered[:6]
        )
        patch = financial_research_patch(findings)
        extraction_result = result.get(
            "extraction_result", FinancialExtractionResult()
        )
        metrics = result.get("metrics", [])
        financial_task = ResearchManagerAgent.plan_financial_task(state["company"])
        canonical_financial_evidence = register_financial_evidence(
            facts=extraction_result.statement_facts,
            metrics=metrics,
        )
        canonical_financial_result = build_financial_agent_result(
            task=financial_task,
            rules=findings,
            evidence=canonical_financial_evidence,
            metrics=metrics,
        )

        print(
            f"[financial-agent] Tool-Augmented analysis complete: "
            f"{len(result.get('raw_statements', []))} tables, "
            f"{len(result.get('extraction_result', FinancialExtractionResult()).statement_facts)} facts, "
            f"{len(result.get('metrics', []))} metrics, "
            f"{len(risks)} risk alerts, "
            f"{len(findings)} forensic findings ({len(triggered)} triggered)",
            flush=True,
        )

        # Message type=finding: structured research artifact
        msg = AgentMessage(
            sender="FinancialAgent",
            receiver="RiskReviewer",
            content=(
                f"Financial analysis complete (Tool-Augmented): "
                f"{len(result.get('extraction_result', FinancialExtractionResult()).statement_facts)} facts, "
                f"{len(result.get('metrics', []))} metrics, "
                f"{len(risks)} risk alerts, "
                f"{len(findings)} forensic findings ({len(triggered)} triggered). "
                f"Triggered items: {triggered_summary or 'none'}."
            ),
            message_type="finding",
            payload={
                "fact_count": len(
                    result.get(
                        "extraction_result", FinancialExtractionResult()
                    ).statement_facts
                ),
                "metric_count": len(result.get("metrics", [])),
                "risk_alert_count": len(risks),
                "forensic_finding_count": len(findings),
                "triggered_count": len(triggered),
                "triggered_rule_ids": triggered_ids,
                "categories": {
                    "asset_quality": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "asset_quality"
                        ]
                    ),
                    "earnings_quality": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "earnings_quality"
                        ]
                    ),
                    "capital_structure": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "capital_structure"
                        ]
                    ),
                    "revenue_authenticity": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "revenue_authenticity"
                        ]
                    ),
                },
            },
        )

        return {
            "analysis": analysis,
            "raw_statements": result.get("raw_statements", []),
            "extraction_result": result.get(
                "extraction_result", FinancialExtractionResult()
            ),
            "metrics": result.get("metrics", []),
            "risks": risks,
            "financial_findings": findings,
            "rule_trigger_events": triggered,
            "research_evidence": patch.evidence,
            "research_findings": patch.findings,
            "canonical_evidence": canonical_financial_result.evidences,
            "canonical_findings": canonical_financial_result.findings,
            "canonical_financial_result": canonical_financial_result,
            "open_questions": patch.open_questions,
            "agent_messages": [msg],
        }

    # ========================
    # Parallel Agent branches
    # ========================

    def _run_prospectus_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        client = None
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)

        agent = ProspectusAgent(client)
        result = agent.analyze(
            company=state["company"],
            pages=state.get("pages", []),
            section_hits=state.get("section_hits"),
        )

        # Handle ProspectusEntity lists
        products = result.main_products or []
        customers = result.customers or []
        key_claims = result.key_claims or []
        patch = prospectus_research_patch(result)
        canonical_patch = adapt_legacy_research_patch(
            patch,
            task_id="TASK_COMPANY_BOUNDARY",
            agent="company_business",
        )
        dossier_counts = {
            topic: len(items)
            for topic, items in result.dossier.topic_findings.items()
        }
        dossier_total = sum(dossier_counts.values())
        dossier_preview = "；".join(
            item.conclusion.replace("\n", "；")[:240]
            for item in patch.findings[:3]
        )

        print(
            f"[prospectus-agent] Done (Tool-Augmented): "
            f"products={len(products)}, "
            f"customers={len(customers)}, "
            f"management={len(result.management_team or [])}, "
            f"dossier_findings={dossier_total}, "
            f"risks={len(result.prospectus_risks)}, "
            f"key_claims={len(key_claims)}",
            flush=True,
        )

        # Message type=finding: with key claims for cross-validation
        msg = AgentMessage(
            sender="ProspectusAgent",
            receiver="RiskReviewer",
            content=(
                f"Prospectus analysis complete: "
                f"products={len(products)}, "
                f"customers={len(customers)}, "
                f"dossier_findings={dossier_total}, "
                f"risks={len(result.prospectus_risks)}, "
                f"key_claims={len(key_claims)}. "
                f"Key output: {dossier_preview or result.business_model[:240] or 'insufficient evidence'}."
            ),
            message_type="finding",
            payload={
                "key_claims": key_claims,
                "has_business_model": bool(result.business_model),
                "product_count": len(products),
                "customer_count": len(customers),
                "risk_count": len(result.prospectus_risks),
                "dossier_topic_counts": dossier_counts,
                "ledger_finding_count": len(patch.findings),
            },
        )

        return {
            "prospectus_analysis": result,
            "research_evidence": patch.evidence,
            "research_findings": patch.findings,
            "canonical_evidence": canonical_patch.evidences,
            "canonical_findings": canonical_patch.findings,
            "open_questions": patch.open_questions,
            "agent_messages": [msg],
        }

    def _run_industry_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        client = None
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)

        business_desc = ""
        pa = state.get("prospectus_analysis")
        if pa and getattr(pa, "business_model", ""):
            business_desc = pa.business_model[:200]

        agent = IndustryAgent(client)
        result = agent.analyze(
            company=state["company"],
            business_description=business_desc,
            pages=state.get("pages", []),
        )
        patch = industry_research_patch(result)
        canonical_patch = adapt_legacy_research_patch(
            patch,
            task_id="TASK_INDUSTRY_BOUNDARY",
            agent="industry_competition",
        )
        web_evidence_count = sum(
            1 for item in result.evidence if getattr(item, "source_type", "") == "web"
        )
        industry_preview = "；".join(
            item.conclusion.replace("\n", "；")[:220]
            for item in patch.findings[:3]
            if item.agent_name == "industry_competition"
        )
        print(
            f"[industry-agent] Done: "
            f"competitors={len(result.competitors)}, "
            f"trends={len(result.industry_trends)}",
            flush=True,
        )

        msg = AgentMessage(
            sender="IndustryAgent",
            receiver="RiskReviewer",
            content=(
                f"Industry analysis complete: "
                f"competitors={len(result.competitors)}, "
                f"trends={len(result.industry_trends)}, "
                f"risks={len(result.industry_risks)}, "
                f"web_evidence={web_evidence_count}. "
                f"Key output: {industry_preview or 'external validation unavailable'}."
            ),
            message_type="finding",
            payload={
                "competitor_count": len(result.competitors),
                "trend_count": len(result.industry_trends),
                "risk_count": len(result.industry_risks),
                "has_market_data": bool(result.market_growth),
                "web_evidence_count": web_evidence_count,
                "ledger_finding_count": len(patch.findings),
            },
        )

        return {
            "industry_analysis": result,
            "research_evidence": patch.evidence,
            "research_findings": patch.findings,
            "canonical_evidence": canonical_patch.evidences,
            "canonical_findings": canonical_patch.findings,
            "tool_call_trace": agent.runtime_trace,
            "open_questions": patch.open_questions,
            "agent_messages": [msg],
        }

    def _run_legal_governance_agent(
        self, state: dict[str, Any]
    ) -> dict[str, Any]:
        agent = LegalGovernanceAgent()
        result = agent.analyze(
            company=state["company"],
            pages=state.get("pages", []),
        )
        patch = legal_governance_research_patch(result)
        canonical_patch = adapt_legacy_research_patch(
            patch,
            task_id="TASK_LEGAL_BOUNDARY",
            agent="legal_governance",
        )
        legal_preview = "；".join(
            item.conclusion[:220] for item in patch.findings[:3]
        )
        print(
            f"[legal-governance-agent] leads={len(result.evidence)}, "
            f"findings={len(patch.findings)}",
            flush=True,
        )
        msg = AgentMessage(
            sender="LegalGovernanceAgent",
            receiver="DueDiligenceLead",
            content=(
                f"Legal/governance surface review complete: "
                f"{len(result.evidence)} page-level leads. "
                f"Key output: {legal_preview or 'no grounded lead found'}."
            ),
            message_type="finding",
            payload={
                "evidence_count": len(result.evidence),
                "finding_count": len(patch.findings),
                "legal_opinion": False,
            },
        )
        return {
            "legal_governance_analysis": result,
            "research_evidence": patch.evidence,
            "research_findings": patch.findings,
            "canonical_evidence": canonical_patch.evidences,
            "canonical_findings": canonical_patch.findings,
            "tool_call_trace": agent.runtime_trace,
            "open_questions": patch.open_questions,
            "agent_messages": [msg],
        }

    # ========================
    # Fan-in: Investment Committee Agent
    # ========================

    @staticmethod
    def _review_needs_llm(state: dict[str, Any]) -> bool:
        """Escalate only material, unexplained evidence conflicts to an LLM."""
        canonical_high = any(
            getattr(item, "risk_level", "") == "high"
            for item in state.get("canonical_findings", [])
        )
        unexplained_financial = any(
            getattr(item, "severity", "") in {"high", "critical"}
            and getattr(item, "assessment_status", "observation")
            in {"unexplained", "contradiction"}
            for item in state.get("financial_findings", [])
        )
        high_rule_alert = any(
            getattr(item, "severity", "") in {"high", "critical"}
            for item in state.get("risks", [])
        )
        return canonical_high or unexplained_financial or high_rule_alert

    def _run_risk_reviewer(self, state: dict[str, Any]) -> dict[str, Any]:
        """Investment Committee Agent: cross-agent reasoning + contradiction detection."""
        canonical_evidence = state.get("canonical_evidence", [])
        canonical_findings = state.get("canonical_findings", [])
        canonical_registry = EvidenceRegistry(canonical_evidence)
        FindingRegistry(canonical_registry).extend(canonical_findings)
        canonical_status = {
            "validated": True,
            "evidence_count": len(canonical_evidence),
            "finding_count": len(canonical_findings),
        }

        # Compatibility ledger for renderers not yet migrated. The canonical
        # reference check above is the first quality gate.
        ledger = EvidenceStore(state.get("research_evidence", []))
        ledger.add_findings(state.get("research_findings", []))
        review_budget = dict(
            state.get("review_llm_budget", {"max_calls": 1, "used_calls": 0})
        )
        budget_available = review_budget.get("used_calls", 0) < review_budget.get(
            "max_calls", 1
        )
        use_review_llm = (
            self._review_needs_llm(state)
            and budget_available
            and self._should_use_llm(state["llm_mode"])
        )
        client = None
        if use_review_llm:
            client = OpenAICompatibleClient(self.settings)
            review_budget["used_calls"] = review_budget.get("used_calls", 0) + 1

        agent = RiskReviewerAgent(client)

        financial_md = ""
        analysis = state.get("analysis")
        if analysis and hasattr(analysis, "markdown"):
            financial_md = analysis.markdown

        # Pass agent_messages to RiskReviewer so it can read finding messages
        agent_messages = state.get("agent_messages", [])

        result = agent.review(
            company=state["company"],
            prospectus_analysis=state.get("prospectus_analysis"),
            industry_analysis=state.get("industry_analysis"),
            financial_markdown=financial_md,
            financial_risks=state.get("risks", []),
            financial_metrics=state.get("metrics", []),
            financial_findings=state.get("financial_findings", []),
            agent_messages=agent_messages,
            research_findings=(
                canonical_findings
                if canonical_findings
                else state.get("research_findings", [])
            ),
            open_questions=state.get("open_questions", []),
        )

        # Handle both structured Contradiction objects and strings
        contradiction_count = len(result.contradictions)
        risk_matrix_count = len(result.risk_matrix)

        print(
            f"[risk-reviewer] risk_level={result.risk_level}, "
            f"major_risks={len(result.major_risks)}, "
            f"contradictions={contradiction_count}, "
            f"risk_matrix_items={risk_matrix_count}, "
            f"questions={len(result.investment_questions)}",
            flush=True,
        )

        # Message type=decision: final risk judgment
        msg = AgentMessage(
            sender="RiskReviewer",
            receiver="ReportWriter",
            content=(
                f"Investment Committee decision: risk_level={result.risk_level}, "
                f"major_risks={len(result.major_risks)}, "
                f"contradictions={contradiction_count}, "
                f"risk_matrix_items={risk_matrix_count}, "
                f"questions={len(result.investment_questions)}."
                f" Major items: {'；'.join(result.major_risks[:4]) or 'none'}."
            ),
            message_type="decision",
            payload={
                "risk_level": result.risk_level,
                "contradiction_count": contradiction_count,
                "risk_matrix_count": risk_matrix_count,
                "question_count": len(result.investment_questions),
                "messages_received": len(agent_messages),
                "canonical_ledger": canonical_status,
                "findings_received": len(
                    [
                        m
                        for m in agent_messages
                        if getattr(m, "message_type", "") == "finding"
                    ]
                ),
            },
        )

        return {
            "risk_review": result,
            "canonical_ledger_status": canonical_status,
            "review_llm_budget": review_budget,
            "agent_messages": [msg],
        }

    def _run_skeptic(self, state: dict[str, Any]) -> dict[str, Any]:
        risk_review = state.get("risk_review")
        challenges = SkepticAgent().review(
            findings=state.get("research_findings", []),
            contradictions=list(getattr(risk_review, "contradictions", []) or []),
            open_questions=state.get("open_questions", []),
        )
        print(f"[skeptic] challenges={len(challenges)}", flush=True)
        if state.get("followup_round", 0) >= 1 and state.get("canonical_challenges"):
            canonical_challenges = [
                item.model_copy(
                    update={
                        "status": (
                            "resolved" if item.response_finding_ids else "unresolved"
                        )
                    }
                )
                for item in state["canonical_challenges"]
            ]
        else:
            canonical_challenges = [adapt_legacy_challenge(item) for item in challenges]
        return {
            "challenges": challenges,
            "canonical_challenges": canonical_challenges,
        }

    def _run_targeted_followup(self, state: dict[str, Any]) -> dict[str, Any]:
        """Route one bounded challenge round to prospectus retrieval or web search."""
        if not state.get("challenges"):
            return {"followup_round": state.get("followup_round", 0)}
        evidence: list[Evidence] = []
        canonical_evidence = []
        canonical_response_ids: dict[str, list[str]] = {}
        unresolved: list[str] = []
        messages: list[AgentMessage] = []
        for challenge in state.get("challenges", []):
            challenge_evidence: list[Evidence] = []
            if challenge.target_agent in {
                "industry_competition",
                "legal_governance",
            }:
                results = search_targeted_followup(state["company"], challenge.question)
                for result in results:
                    challenge_evidence.append(
                        Evidence(
                            source_type="web",
                            title=result.get("title", ""),
                            content=result.get("content", ""),
                            source=result.get("url", ""),
                            source_url=result.get("url"),
                            published_at=result.get("published_at"),
                            retrieved_at=result.get("retrieved_at"),
                            confidence=float(result.get("confidence", 0.5)),
                            metadata={
                                "topic": "targeted_followup",
                                "challenge_id": challenge.challenge_id,
                                "source_tier": result.get("source_tier", "unknown"),
                            },
                        )
                    )
            else:
                challenge_evidence.extend(
                    self._retrieve_prospectus_followup(
                        pages=state.get("pages", []),
                        question=challenge.question,
                        challenge_id=challenge.challenge_id,
                    )
                )
            evidence.extend(challenge_evidence)
            converted_evidence = [
                adapt_legacy_evidence(item, created_by=challenge.target_agent)
                for item in challenge_evidence
            ]
            canonical_evidence.extend(converted_evidence)
            canonical_response_ids[challenge.challenge_id] = [
                item.evidence_id for item in converted_evidence
            ]
            if not challenge_evidence:
                unresolved.append(challenge.question)
            messages.append(
                AgentMessage(
                    sender=challenge.target_agent,
                    receiver="DueDiligenceLead",
                    content=(
                        f"Challenge {challenge.challenge_id}: located "
                        f"{len(challenge_evidence)} additional evidence items; "
                        "the lead must still judge whether the explanation is sufficient."
                    ),
                    message_type="finding",
                    payload={
                        "challenge_id": challenge.challenge_id,
                        "evidence_ids": [item.evidence_id for item in challenge_evidence],
                        "resolved": False,
                    },
                )
            )
        print(
            f"[targeted-followup] round=1, new_evidence={len(evidence)}, "
            f"unresolved={len(unresolved)}",
            flush=True,
        )
        return {
            "research_evidence": evidence,
            "canonical_evidence": canonical_evidence,
            "canonical_challenges": [
                item.model_copy(
                    update={
                        "response_evidence_ids": canonical_response_ids.get(
                            item.challenge_id, []
                        ),
                        "status": "open",
                    }
                )
                for item in state.get("canonical_challenges", [])
            ],
            "followup_round": 1,
            "agent_messages": messages,
        }

    @staticmethod
    def _retrieve_prospectus_followup(
        *, pages: list[Any], question: str, challenge_id: str
    ) -> list[Evidence]:
        """Locate page-level leads for company/financial challenges without inventing an answer."""
        lowered_question = question.lower()
        tokens = set(re.findall(r"[a-zA-Z]{4,}", lowered_question))
        domain_terms = {
            "收入", "毛利", "利润", "现金", "应收", "应付", "存货", "负债",
            "借款", "收购", "并购", "研发", "客户", "供应商", "返利", "关联交易",
            "实控人", "股权", "产品", "市场", "竞争", "诉讼", "处罚", "牌照",
        }
        tokens.update(term for term in domain_terms if term in lowered_question)
        stop = {"是否", "公司", "需要", "核实", "什么", "which", "what", "does", "company"}
        tokens -= stop
        ranked: list[tuple[int, Any]] = []
        for page in pages:
            text = getattr(page, "text", "") or ""
            score = sum(1 for token in tokens if token in text.lower())
            if score:
                ranked.append((score, page))
        result: list[Evidence] = []
        for _, page in sorted(ranked, key=lambda item: item[0], reverse=True)[:3]:
            text = (getattr(page, "text", "") or "").replace("\n", " ")
            result.append(
                Evidence(
                    source_type="prospectus",
                    title="质疑回路定向检索线索",
                    content=text[:800],
                    page_number=(
                        getattr(page, "page_number", None)
                        or getattr(page, "page", None)
                    ),
                    confidence=0.65,
                    metadata={"topic": "targeted_followup", "challenge_id": challenge_id},
                )
            )
        return result

    def _run_due_diligence_lead(self, state: dict[str, Any]) -> dict[str, Any]:
        canonical_status = {
            item.challenge_id: item.status
            for item in state.get("canonical_challenges", [])
        }
        active_challenges = [
            item
            for item in state.get("challenges", [])
            if canonical_status.get(item.challenge_id, "open") != "resolved"
        ]
        conclusion, questions = DueDiligenceLeadAgent().synthesize(
            findings=state.get("research_findings", []),
            challenges=active_challenges,
            risk_review=state.get("risk_review"),
            metrics=state.get("metrics", []),
            financial_findings=state.get("financial_findings", []),
        )
        print(
            f"[due-diligence-lead] verdict={conclusion.verdict}, "
            f"follow_up_questions={len(questions)}",
            flush=True,
        )
        return {
            "due_diligence_conclusion": conclusion,
            "diligence_questions": questions,
            "agent_messages": [
                AgentMessage(
                    sender="DueDiligenceLead",
                    receiver="ReportWriter",
                    content=(
                        f"Mainline A conclusion: {conclusion.verdict}; "
                        f"{len(questions)} follow-up questions."
                    ),
                    message_type="decision",
                    payload={
                        "verdict": conclusion.verdict,
                        "historical_financial_quality": (
                            conclusion.historical_financial_quality
                        ),
                        "future_earning_power": conclusion.future_earning_power,
                        "material_risk_level": conclusion.material_risk_level,
                    },
                )
            ],
        }

    # ========================
    # Report Writer
    # ========================

    def _run_report_writer(self, state: dict[str, Any]) -> dict[str, Any]:
        grounded_draft = render_investment_markdown(state)
        client = None
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)
        writer_used_llm = bool(
            client is not None
            and len(grounded_draft) <= 12000
            and "三大财务报表（招股书原表还原）" not in grounded_draft
        )
        try:
            final_report = ReportWriterAgent(client).write_diligence_draft(
                company=state["company"],
                grounded_draft=grounded_draft,
                agent_messages=state.get("agent_messages", []),
            )
        except Exception as error:
            print(
                f"[report-writer] LLM rewrite unavailable "
                f"({type(error).__name__}); using grounded draft.",
                flush=True,
            )
            final_report = grounded_draft
        print(
            f"[report-writer] Report generated: {len(final_report)} chars",
            flush=True,
        )
        return {
            "final_report": final_report,
            "agent_messages": [
                AgentMessage(
                    sender="ReportWriter",
                    receiver="EvidenceComplianceReviewer",
                    content=(
                        f"Drafted a {len(final_report)}-character due-diligence report "
                        f"from the shared research ledger."
                    ),
                    message_type="finding",
                    payload={
                        "used_llm": writer_used_llm,
                        "deterministic_financial_tables": True,
                    },
                )
            ],
        }

    def _run_report_reviewer(self, state: dict[str, Any]) -> dict[str, Any]:
        client = None
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)
        review = EvidenceComplianceReviewerAgent(client).review(
            company=state["company"],
            report=state.get("final_report", ""),
        )
        print(
            f"[report-reviewer] passed={review.passed}, score={review.score}, "
            f"revision_items={len(review.revision_instructions)}",
            flush=True,
        )
        return {
            "report_review": review,
            "agent_messages": [
                AgentMessage(
                    sender="EvidenceComplianceReviewer",
                    receiver="ReportWriter",
                    content=(
                        f"Report review completed: passed={review.passed}, "
                        f"score={review.score}, "
                        f"revision_items={len(review.revision_instructions)}."
                    ),
                    message_type="challenge" if not review.passed else "decision",
                    payload=review.model_dump(),
                )
            ],
        }

    def _run_report_revision(self, state: dict[str, Any]) -> dict[str, Any]:
        review = state.get("report_review")
        instructions = list(
            getattr(review, "revision_instructions", []) or []
        )
        # Passing the hard gate can still leave actionable quality findings.
        # Apply one bounded revision until the investor-facing target is met.
        if not instructions or getattr(review, "score", 0) >= 90:
            return {"report_revision_performed": False}
        client = None
        if self._should_use_llm(state["llm_mode"]):
            client = OpenAICompatibleClient(self.settings)
        if client is None:
            return {"report_revision_performed": False}
        try:
            revised = ReportWriterAgent(client).revise_diligence_draft(
                report=state.get("final_report", ""),
                revision_instructions=instructions,
            )
        except Exception as error:
            print(
                f"[report-revision] revision unavailable ({type(error).__name__}).",
                flush=True,
            )
            return {"report_revision_performed": False}
        post_review = EvidenceComplianceReviewerAgent(client).review(
            company=state["company"], report=revised
        )
        if post_review.score <= getattr(review, "score", 0):
            return {
                "report_revision_performed": False,
                "report_revision_attempted": True,
                "agent_messages": [
                    AgentMessage(
                        sender="EvidenceComplianceReviewer",
                        receiver="ReportWriter",
                        content="Revision candidate was rejected because the review score did not improve.",
                        message_type="decision",
                        payload={
                            "before_score": getattr(review, "score", 0),
                            "candidate_score": post_review.score,
                        },
                    )
                ],
            }
        return {
            "final_report": revised,
            "report_review": post_review,
            "report_revision_performed": True,
            "report_revision_attempted": True,
            "agent_messages": [
                AgentMessage(
                    sender="ReportWriter",
                    receiver="EvidenceComplianceReviewer",
                    content="Applied one bounded revision round and preserved grounded citations.",
                    message_type="finding",
                    payload={"revision_items": len(instructions)},
                )
            ],
        }

    # ========================
    # Export (extended with forensic outputs)
    # ========================

    def _export_outputs(self, state: dict[str, Any]) -> dict[str, Any]:
        document_id = state.get("document_id", "")
        company = state.get("company", "")
        extraction: FinancialExtractionResult = state.get(
            "extraction_result", FinancialExtractionResult()
        )
        artifact_dir = self.settings.extracted_dir / document_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        pages = state.get("pages", [])
        raw_statements = state.get("raw_statements", [])
        metrics = state.get("metrics", [])
        risks = state.get("risks", [])
        analysis = state.get("analysis")
        findings = state.get("financial_findings", [])
        rule_events = state.get("rule_trigger_events", [])

        # Original JSON outputs
        pages_json = write_json(artifact_dir / "pages.json", pages)
        document_json = write_json(
            artifact_dir / "document.json",
            {
                "schema_version": "2.0",
                "document_id": document_id,
                "company": company,
                "source_pdf": state.get("pdf_path", ""),
                "page_count": len(pages),
                "pages": pages,
                "sections": state.get("section_hits", []),
                "topic_page_groups": state.get("topic_page_groups", {}),
            },
        )
        raw_statements_json = write_json(
            artifact_dir / "raw_statements.json", raw_statements
        )
        financial_kb_json = write_json(artifact_dir / "financial_kb.json", extraction)
        metrics_json = write_json(artifact_dir / "metrics.json", metrics)
        risk_json = write_json(artifact_dir / "risk_findings.json", risks)

        # Multi-Agent outputs
        prospectus_json = write_json(
            artifact_dir / "prospectus_analysis.json",
            state.get("prospectus_analysis"),
        )
        industry_json = write_json(
            artifact_dir / "industry_analysis.json",
            state.get("industry_analysis"),
        )
        legal_governance_json = write_json(
            artifact_dir / "legal_governance_analysis.json",
            state.get("legal_governance_analysis"),
        )
        due_diligence_json = write_json(
            artifact_dir / "due_diligence_conclusion.json",
            {
                "conclusion": state.get("due_diligence_conclusion"),
                "follow_up_questions": state.get("diligence_questions", []),
            },
        )
        risk_review_json = write_json(
            artifact_dir / "risk_review.json",
            state.get("risk_review"),
        )
        report_review_json = write_json(
            artifact_dir / "report_review.json",
            state.get("report_review"),
        )

        # Research plan + agent messages (event bus)
        research_plan_json = write_json(
            artifact_dir / "research_plan.json",
            state.get("research_plan"),
        )
        agent_messages_json = write_json(
            artifact_dir / "agent_messages.json",
            state.get("agent_messages", []),
        )
        research_ledger_json = write_json(
            artifact_dir / "research_ledger.json",
            {
                "evidence": state.get("research_evidence", []),
                "findings": state.get("research_findings", []),
                "open_questions": state.get("open_questions", []),
                "challenges": state.get("challenges", []),
                "canonical_evidence": state.get("canonical_evidence", []),
                "canonical_findings": state.get("canonical_findings", []),
                "canonical_challenges": state.get("canonical_challenges", []),
                "canonical_ledger_status": state.get(
                    "canonical_ledger_status", {}
                ),
            },
        )

        # Financial Forensic Engine outputs
        forensic_findings_json = write_json(
            artifact_dir / "forensic_findings.json", findings
        )
        rule_events_json = write_json(artifact_dir / "rule_events.json", rule_events)

        # Excel workbook
        excel_path = self.settings.output_dir / f"{document_id}_financial_workbook.xlsx"
        export_financial_workbook(
            output_path=excel_path,
            raw_statements=raw_statements,
            facts=extraction.statement_facts,
            notes=extraction.financial_notes,
            metrics=metrics,
            risks=risks,
        )

        # Financial analysis report
        report_path = self.settings.output_dir / f"{document_id}_financial_report.md"
        if analysis and hasattr(analysis, "markdown"):
            write_markdown_report(report_path, analysis.markdown)
        else:
            write_markdown_report(report_path, "(financial analysis not generated)")

        # Final IPO research report
        final_report_path: Path | None = None
        final_report = state.get("final_report", "")
        if final_report:
            final_report_path = (
                self.settings.output_dir / f"{document_id}_due_diligence_report.md"
            )
            write_markdown_report(final_report_path, final_report)

        # Stable product delivery bundle. Each run gets an isolated directory,
        # while filenames remain exactly those promised by the PRD.
        delivery_dir = self.settings.output_dir / document_id
        delivery_dir.mkdir(parents=True, exist_ok=True)
        delivery_report_path = delivery_dir / "IPO_Due_Diligence_Report.md"
        write_markdown_report(
            delivery_report_path,
            final_report or "(due diligence report not generated)",
        )
        delivery_workbook_path = delivery_dir / "IPO_Due_Diligence_Report.xlsx"
        shutil.copy2(excel_path, delivery_workbook_path)
        enrich_due_diligence_workbook(
            workbook_path=delivery_workbook_path,
            evidence=state.get("research_evidence", []),
            findings=state.get("research_findings", []),
            diligence_questions=state.get("diligence_questions", []),
            agent_messages=state.get("agent_messages", []),
            conclusion=state.get("due_diligence_conclusion"),
            report_review=state.get("report_review"),
        )
        integrity = ledger_integrity(
            state.get("research_evidence", []),
            state.get("research_findings", []),
        )
        if not integrity["passed"]:
            raise RuntimeError(
                "Evidence -> Finding integrity validation failed: "
                f"{integrity}"
            )
        evidence_json = write_json(
            delivery_dir / "evidence.json",
            {
                "schema_version": "2.0",
                "document_id": document_id,
                "company": company,
                "integrity": integrity,
                "evidence": state.get("research_evidence", []),
                "findings": state.get("research_findings", []),
                "open_questions": state.get("open_questions", []),
                "challenges": state.get("challenges", []),
            },
        )
        agent_trace_json = write_json(
            delivery_dir / "agent_trace.json",
            {
                "schema_version": "2.0",
                "document_id": document_id,
                "company": company,
                "research_plan": state.get("research_plan"),
                "messages": state.get("agent_messages", []),
            },
        )
        delivery_manifest_json = write_json(
            delivery_dir / "delivery_manifest.json",
            {
                "schema_version": "2.0",
                "document_id": document_id,
                "company": company,
                "inputs": {
                    "company": company,
                    "prospectus_pdf": state.get("pdf_path", ""),
                },
                "deliverables": {
                    "report_markdown": str(delivery_report_path),
                    "report_workbook": str(delivery_workbook_path),
                    "evidence": str(evidence_json),
                    "agent_trace": str(agent_trace_json),
                },
                "supporting_artifacts": {
                    "document": str(document_json),
                    "research_plan": str(research_plan_json),
                    "company_business": str(prospectus_json),
                    "financial": str(financial_kb_json),
                    "industry": str(industry_json),
                    "legal_governance": str(legal_governance_json),
                    "risk_review": str(risk_review_json),
                    "report_review": str(report_review_json),
                },
                "integrity": integrity,
            },
        )

        # Database storage
        repository = FinancialRepository(self.settings.db_path)
        try:
            source_file = Path(state.get("pdf_path", "")).name
            repository.replace_document(
                document_id=document_id,
                company=company,
                source_file=source_file,
                pdf_path=state.get("pdf_path", ""),
            )
            repository.save_pages(document_id, pages)
            repository.save_raw_statement_tables(document_id, raw_statements)
            repository.save_statement_facts(extraction.statement_facts)
            repository.save_financial_notes(extraction.financial_notes)
            repository.save_metrics(metrics)
            repository.save_risk_findings(risks)
            if analysis:
                repository.save_analysis(analysis)
        finally:
            repository.close()

        # Count structured artifacts for metadata
        risk_review = state.get("risk_review")
        contradiction_count = (
            len(getattr(risk_review, "contradictions", [])) if risk_review else 0
        )
        risk_matrix_count = (
            len(getattr(risk_review, "risk_matrix", [])) if risk_review else 0
        )

        artifacts = PipelineArtifacts(
            document_id=document_id,
            company=company,
            pdf_path=state.get("pdf_path", ""),
            pages_json=str(pages_json),
            raw_statements_json=str(raw_statements_json),
            financial_kb_json=str(financial_kb_json),
            metrics_json=str(metrics_json),
            risk_findings_json=str(risk_json),
            excel_path=str(excel_path),
            report_path=str(report_path),
            document_json=str(document_json),
            final_report_path=str(delivery_report_path),
            due_diligence_workbook_path=str(delivery_workbook_path),
            evidence_json=str(evidence_json),
            agent_trace_json=str(agent_trace_json),
            delivery_manifest_json=str(delivery_manifest_json),
            metadata={
                "page_count": len(pages),
                "candidate_page_count": len(state.get("candidate_pages", [])),
                "raw_statement_count": len(raw_statements),
                "fact_count": len(extraction.statement_facts),
                "note_count": len(extraction.financial_notes),
                "metric_count": len(metrics),
                "risk_count": len(risks),
                "llm_mode": state.get("llm_mode", "auto"),
                "prospectus_json": str(prospectus_json),
                "industry_json": str(industry_json),
                "legal_governance_json": str(legal_governance_json),
                "due_diligence_json": str(due_diligence_json),
                "risk_review_json": str(risk_review_json),
                "report_review_json": str(report_review_json),
                "report_review_passed": getattr(
                    state.get("report_review"), "passed", None
                ),
                "report_review_score": getattr(
                    state.get("report_review"), "score", None
                ),
                "report_revision_performed": state.get(
                    "report_revision_performed", False
                ),
                "report_revision_attempted": state.get(
                    "report_revision_attempted", False
                ),
                "legacy_final_report_path": str(final_report_path)
                if final_report_path
                else None,
                "final_report_path": str(delivery_report_path),
                "due_diligence_workbook_path": str(delivery_workbook_path),
                "evidence_json": str(evidence_json),
                "agent_trace_json": str(agent_trace_json),
                "delivery_manifest_json": str(delivery_manifest_json),
                "ledger_integrity_passed": integrity["passed"],
                "risk_level": getattr(state.get("risk_review"), "risk_level", None),
                "research_plan_json": str(research_plan_json),
                "agent_messages_json": str(agent_messages_json),
                "agent_message_count": len(state.get("agent_messages", [])),
                "research_ledger_json": str(research_ledger_json),
                "research_evidence_count": len(state.get("research_evidence", [])),
                "research_finding_count": len(state.get("research_findings", [])),
                "open_question_count": len(state.get("open_questions", [])),
                "challenge_count": len(state.get("canonical_challenges", [])),
                "resolved_challenge_count": len(
                    [
                        item
                        for item in state.get("canonical_challenges", [])
                        if item.status == "resolved"
                    ]
                ),
                "unresolved_challenge_count": len(
                    [
                        item
                        for item in state.get("canonical_challenges", [])
                        if item.status in {"open", "unresolved"}
                    ]
                ),
                "followup_round": state.get("followup_round", 0),
                "due_diligence_verdict": getattr(
                    state.get("due_diligence_conclusion"), "verdict", None
                ),
                "diligence_question_count": len(
                    state.get("diligence_questions", [])
                ),
                # Forensic engine metadata
                "forensic_findings_json": str(forensic_findings_json),
                "rule_events_json": str(rule_events_json),
                "forensic_finding_count": len(findings),
                "forensic_triggered_count": len(rule_events),
                "forensic_categories": {
                    "asset_quality": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "asset_quality"
                        ]
                    ),
                    "earnings_quality": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "earnings_quality"
                        ]
                    ),
                    "capital_structure": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "capital_structure"
                        ]
                    ),
                    "revenue_authenticity": len(
                        [
                            f
                            for f in findings
                            if getattr(f, "category", "") == "revenue_authenticity"
                        ]
                    ),
                },
                # Investment Committee metadata
                "contradiction_count": contradiction_count,
                "risk_matrix_count": risk_matrix_count,
                "investment_question_count": len(
                    getattr(risk_review, "investment_questions", [])
                )
                if risk_review
                else 0,
            },
        )
        write_json(artifact_dir / "run_summary.json", artifacts)
        return {"artifacts": artifacts}

    # ========================
    # Helpers
    # ========================

    def _should_use_llm(self, llm_mode: str) -> bool:
        if llm_mode == "off":
            return False
        if llm_mode == "on" and not self.settings.llm_configured:
            raise LLMConfigurationError(
                "llm_mode=on, but OPENAI_COMPATIBLE_API_KEY and OPENAI_COMPATIBLE_MODEL are not configured."
            )
        return self.settings.llm_configured

    def _resolve_llm_mode(self, llm_mode: str) -> str:
        """Make auto truly resilient: one cheap endpoint check before fan-out."""
        if llm_mode != "auto" or not self.settings.llm_configured:
            return llm_mode
        raw_url = self.settings.llm_base_url or "https://api.openai.com/v1"
        parsed = urlparse(raw_url if "://" in raw_url else f"http://{raw_url}")
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            print("[llm-preflight] Invalid base URL; auto mode falls back to off.", flush=True)
            return "off"
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"[llm-preflight] Endpoint reachable: {host}:{port}", flush=True)
                return "auto"
        except OSError as exc:
            print(
                f"[llm-preflight] Endpoint unavailable ({type(exc).__name__}); "
                "auto mode falls back to deterministic agents.",
                flush=True,
            )
            return "off"

    @staticmethod
    def _document_id(path: Path) -> str:
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:8]
        stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", path.stem).strip("_")
        return f"{stem[:48]}_{digest}"
