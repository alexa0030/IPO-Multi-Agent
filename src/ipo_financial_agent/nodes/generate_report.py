from __future__ import annotations

from typing import Any


def generate_financial_report(state: dict[str, Any]) -> dict[str, Any]:
    review = state["review_result"]
    approved = set(review.approved_finding_ids)
    findings = [
        item
        for item in state.get("financial_findings", [])
        if item.finding_id in approved
    ]
    lines = [
        "## Financial-only 最小闭环结论",
        "",
        f"- Reviewer 状态：{review.review_status}",
        f"- 历史财务判断：{review.historical_financial_assessment.conclusion}",
    ]
    for finding in findings:
        citations = " ".join(f"[{item}]" for item in finding.evidence_ids)
        lines.extend(
            [
                "",
                f"### {finding.title}",
                "",
                f"{finding.statement}{finding.interpretation}",
                f"风险等级：{finding.risk_level}；置信度：{finding.confidence}。",
                f"证据：{citations}",
                f"待补材料：{'；'.join(finding.required_checks)}",
            ]
        )
    if review.follow_up_requests:
        lines.extend(["", "### Reviewer 补证请求", ""])
        lines.extend(f"- {item.question}" for item in review.follow_up_requests)
    return {"final_report": "\n".join(lines)}
