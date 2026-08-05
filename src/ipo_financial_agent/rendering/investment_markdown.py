"""Render a traceable investment-committee report from structured state."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ipo_financial_agent.models_agent import Evidence, Finding


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _evidence_label(item: Evidence) -> str:
    if item.source_url:
        location = item.source_url
    elif item.page_number:
        location = f"招股书 P{item.page_number}"
    else:
        location = item.source or item.source_type
    return f"[{item.evidence_id} | {location}]"


def _finding_line(item: Finding, evidence: dict[str, Evidence]) -> str:
    citations = " ".join(
        _evidence_label(evidence[evidence_id])
        for evidence_id in item.evidence_ids
        if evidence_id in evidence
    )
    return f"- {item.conclusion} {citations}".rstrip()


def _entity_lines(items: list[Any]) -> list[str]:
    lines: list[str] = []
    for item in items:
        evidence = list(_value(item, "evidence", []) or [])
        citations = " ".join(_evidence_label(entry) for entry in evidence)
        name = _value(item, "name", "未命名事项")
        detail = _value(item, "detail", "")
        suffix = f"：{detail}" if detail else ""
        lines.append(f"- {name}{suffix} {citations}".rstrip())
    return lines


def render_investment_markdown(state: dict[str, Any]) -> str:
    """Render facts, judgments and unresolved questions as separate layers."""
    company = state.get("company", "未命名公司")
    evidence_items: list[Evidence] = state.get("research_evidence", [])
    findings: list[Finding] = state.get("research_findings", [])
    evidence = {item.evidence_id: item for item in evidence_items}
    findings_by_agent: dict[str, list[Finding]] = defaultdict(list)
    for item in findings:
        findings_by_agent[item.agent_name].append(item)

    risk_review = state.get("risk_review")
    risk_level = _value(risk_review, "risk_level", "未评定")
    prospectus = state.get("prospectus_analysis")
    metrics = list(state.get("metrics", []) or [])
    open_questions = list(dict.fromkeys(state.get("open_questions", []) or []))
    challenges = list(state.get("challenges", []) or [])

    lines = [
        f"# {company}港股 IPO 尽调与投资研究报告",
        "",
        "> 本报告由结构化 Research Ledger 确定性渲染。事实与结论必须引用招股书页码、计算结果或外部 URL；缺少证据的内容列入待核实事项。",
        "",
        "## 一、项目摘要",
        "",
        f"- 当前风险等级：**{risk_level}**",
        f"- 已登记证据：{len(evidence_items)} 条",
        f"- 已验证研究发现：{len(findings)} 条",
        f"- 待核实问题：{len(open_questions)} 条",
        f"- Skeptic Challenge：{len(challenges)} 条",
        "",
    ]

    business_model = _value(prospectus, "business_model", "")
    business_evidence = list(
        _value(prospectus, "business_model_evidence", []) or []
    )
    lines.extend(["## 二、公司、股权与业务尽调", ""])
    if business_model and business_evidence:
        citations = " ".join(
            _evidence_label(item) for item in business_evidence
        )
        lines.append(f"- 商业模式：{business_model} {citations}")
    else:
        lines.append("- 商业模式尚未形成具备页码证据的结论。")
    for title, field in (
        ("主要产品", "main_products"),
        ("客户", "customers"),
        ("供应商", "suppliers"),
        ("管理团队", "management_team"),
    ):
        items = list(_value(prospectus, field, []) or [])
        lines.extend(["", f"### {title}", ""])
        lines.extend(_entity_lines(items) or ["- 暂无已验证记录。"])

    lines.extend(["", "## 三、财务质量与取证", ""])
    financial_findings = findings_by_agent.get("financial_dd", [])
    lines.extend(
        [_finding_line(item, evidence) for item in financial_findings]
        or ["- 暂无通过 Evidence Ledger 校验的财务结论。"]
    )
    if metrics:
        lines.extend(
            [
                "",
                "### Python 计算指标",
                "",
                "| 指标 | 期间 | 结果 | 来源页 |",
                "|---|---|---:|---|",
            ]
        )
        for metric in metrics:
            pages = ", ".join(
                f"P{page}" for page in _value(metric, "source_pages", [])
            )
            lines.append(
                f"| {_value(metric, 'metric_name', '')} | "
                f"{_value(metric, 'period', '')} | "
                f"{_value(metric, 'display_value', '')} | {pages or '待补充'} |"
            )

    lines.extend(["", "## 四、行业、竞争与估值", ""])
    market_findings = findings_by_agent.get("market_valuation", [])
    lines.extend(
        [_finding_line(item, evidence) for item in market_findings]
        or ["- 外部检索尚未提供可引用证据，本节不生成替代性行业事实。"]
    )
    lines.extend(
        [
            "",
            "> 估值纪律：申请版本中的发行价格、发行规模等字段可能仍为[编纂]。无法从可靠来源取得时，不推算虚假估值。",
            "",
            "## 五、投资逻辑",
            "",
        ]
    )
    verified = [
        item
        for item in findings
        if item.evidence_strength in {"strong", "medium"}
        and item.agent_name in {"company_business", "market_valuation"}
    ]
    lines.extend(
        [_finding_line(item, evidence) for item in verified[:8]]
        or ["- 暂无达到证据要求的投资逻辑。"]
    )

    lines.extend(["", "## 六、风险与反证", ""])
    contradictions = list(_value(risk_review, "contradictions", []) or [])
    if contradictions:
        for item in contradictions:
            lines.append(
                f"- **{_value(item, 'severity', 'warning')}**："
                f"{_value(item, 'statement_1', '')}；反证："
                f"{_value(item, 'statement_2', '')}。"
                f"待核实：{_value(item, 'question', '')}"
            )
    else:
        lines.append("- 暂无结构化跨 Agent 矛盾记录。")

    if challenges:
        lines.extend(["", "### Skeptic Challenges", ""])
        for item in challenges:
            status = "已解决" if _value(item, "resolved", False) else "未解决"
            lines.append(
                f"- [{_value(item, 'severity', 'important')}/{status}] "
                f"{_value(item, 'question', '')}"
            )

    lines.extend(["", "## 七、待核实事项与投资方案边界", ""])
    lines.extend([f"- {item}" for item in open_questions] or ["- 暂无。"])
    lines.extend(
        [
            "- 申请版本仍被遮蔽的发行价格、发行规模、基石或锚定条款，必须以后续聆讯后资料集、正式招股章程或配发结果为准。",
            "",
            "## 八、证据索引",
            "",
            "| Evidence ID | 类型 | 标题 | 页码/URL | 置信度 |",
            "|---|---|---|---|---:|",
        ]
    )
    for item in evidence_items:
        location = item.source_url or (
            f"P{item.page_number}" if item.page_number else item.source
        )
        title = item.title.replace("|", "\\|")
        lines.append(
            f"| {item.evidence_id} | {item.source_type} | {title} | "
            f"{location} | {item.confidence:.2f} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "本报告用于研究辅助，不构成审计意见、法律意见或投资承诺。",
        ]
    )
    return "\n".join(lines)
