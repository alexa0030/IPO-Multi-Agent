from __future__ import annotations

from typing import Any

from ipo_financial_agent.agents.research_manager import ResearchManagerAgent


def plan_financial_research(state: dict[str, Any]) -> dict[str, Any]:
    task = ResearchManagerAgent.plan_financial_task(state["company_name"])
    return {
        "research_plan": {
            "phase": "financial_minimal_closure",
            "objective": task.objective,
            "task_ids": [task.task_id],
        },
        "research_tasks": [task],
        "agent_messages": [
            {
                "sender": "ResearchManager",
                "receiver": "financial",
                "type": "task",
                "task_id": task.task_id,
                "content": task.objective,
            }
        ],
    }
