from __future__ import annotations

from typing import Any, Callable

from ipo_financial_agent.agents.financial_agent import FinancialAnalysisAgent
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.research.financial_contract_adapter import (
    convert_selling_expense_rule,
    register_financial_evidence,
    select_supported_rule,
)


def build_run_financial_node(
    client: OpenAICompatibleClient | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def run_financial(state: dict[str, Any]) -> dict[str, Any]:
        tasks = [
            item
            for item in state.get("research_tasks", [])
            if item.target_agent == "financial"
        ]
        if len(tasks) != 1:
            raise ValueError("phase one requires exactly one financial ResearchTask")
        task = tasks[0]
        result = FinancialAnalysisAgent(client).analyze(
            document_id=state["job_id"],
            company=state["company_name"],
            pages=state.get("pages", []),
            section_hits=state.get("section_hits", []),
            topic_page_groups=state.get("topic_page_groups", {}),
            llm_mode=state.get("llm_mode", "off"),
            task=task,
        )
        extraction = result["extraction_result"]
        evidences = register_financial_evidence(
            facts=extraction.statement_facts,
            metrics=result["metrics"],
        )
        rule = select_supported_rule(result["findings"])
        finding = convert_selling_expense_rule(
            task=task,
            rule_result=rule,
            metrics=result["metrics"],
        )
        return {
            "financial_agent_result": result,
            "evidences": evidences,
            "financial_findings": [finding],
            "agent_messages": [
                {
                    "sender": "FinancialAgent",
                    "receiver": "ResearchReviewer",
                    "type": "finding",
                    "task_id": task.task_id,
                    "content": (
                        f"registered {len(evidences)} Evidence items and "
                        f"Finding {finding.finding_id}"
                    ),
                }
            ],
        }

    return run_financial
