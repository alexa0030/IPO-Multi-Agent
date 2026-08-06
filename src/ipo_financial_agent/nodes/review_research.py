from __future__ import annotations

from typing import Any

from ipo_financial_agent.agents.research_reviewer import ResearchReviewerAgent


def review_financial_research(state: dict[str, Any]) -> dict[str, Any]:
    tasks = state.get("research_tasks", [])
    if len(tasks) != 1:
        raise ValueError("phase one requires exactly one ResearchTask")
    review = ResearchReviewerAgent().review_financial(
        task=tasks[0],
        evidences=state.get("evidences", []),
        findings=state.get("financial_findings", []),
    )
    return {
        "review_result": review,
        "follow_up_requests": review.follow_up_requests,
        "review_round": 1,
        "agent_messages": [
            {
                "sender": "ResearchReviewer",
                "receiver": "ReportGenerator",
                "type": "review",
                "content": (
                    f"status={review.review_status}; "
                    f"approved={len(review.approved_finding_ids)}; "
                    f"rejected={len(review.rejected_finding_ids)}"
                ),
            }
        ],
    }
