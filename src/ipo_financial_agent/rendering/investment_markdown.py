"""Render the Mainline A company due diligence report from structured state."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ipo_financial_agent.models_agent import Evidence, Finding


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _evidence_label(item: Evidence) -> str:
    location = (
        item.source_url
        or (f"招股书 P{item.page_number}" if item.page_number else "")
        or item.source
        or item.source_type
    )
    return f"[{item.evidence_id} | {location}]"


def _finding_lines(
    items: list[Finding], evidence: dict[str, Evidence], empty: str
) -> list[str]:
    if not items:
        return [f"- {empty}"]
    lines: list[str] = []
    for item in items:
        citations = " ".join(
            _evidence_label(evidence[evidence_id])
            for evidence_id in item.evidence_ids
            if evidence_id in evidence
        )
        lines.append(f"- {item.conclusion} {citations}".rstrip())
    return lines


def _entity_lines(items: list[Any]) -> list[str]:
    lines: list[str] = []
    for item in items:
        citations = " ".join(
            _evidence_label(entry)
            for entry in list(_value(item, "evidence", []) or [])
        )
        detail = _value(item, "detail", "")
        suffix = f"：{detail}" if detail else ""
        lines.append(
            f"- {_value(item, 'name', '未命名事项')}{suffix} {citations}".rstrip()
        )
    return lines or ["- 暂无已验证记录。"]


_STATEMENT_TITLES = {
    "balance_sheet": "资产负债表",
    "income_statement": "利润表",
    "cash_flow_statement": "现金流量表",
}


def _markdown_cell(value: Any) -> str:
    text = str(value or "").strip().replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|") or "—"


def _select_primary_statement(tables: list[Any], statement_type: str) -> Any | None:
    """Select the most complete consolidated table without sample-specific hints."""
    candidates = [
        table
        for table in tables
        if _value(table, "statement_type") == statement_type
        and _value(table, "rows", [])
    ]
    if not candidates:
        return None

    def score(table: Any) -> tuple[int, int, int]:
        scope = str(_value(table, "entity_scope", "") or "")
        consolidated = int(any(word in scope for word in ("合并", "综合", "集团")))
        return (
            consolidated,
            len(_value(table, "rows", []) or []),
            len(_value(table, "pages", []) or []),
        )

    return max(candidates, key=score)


def _statement_table_lines(table: Any) -> list[str]:
    rows = [list(row) for row in (_value(table, "rows", []) or []) if row]
    if not rows:
        return ["- 未抽取到可展示的原始表格行。"]

    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header_index = 0
    for index, row in enumerate(normalized[:8]):
        joined = "".join(str(cell) for cell in row)
        nonempty = sum(bool(str(cell).strip()) for cell in row)
        if nonempty >= 2 and any(token in joined for token in ("年", "月", "截至", "202", "201")):
            header_index = index
            break
    else:
        for index, row in enumerate(normalized[:8]):
            if sum(bool(str(cell).strip()) for cell in row) >= 2:
                header_index = index
                break

    lines: list[str] = []
    preface = [
        " ".join(_markdown_cell(cell) for cell in row if str(cell).strip())
        for row in normalized[:header_index]
    ]
    if preface:
        lines.extend([f"> {'；'.join(preface)}", ""])

    header = [_markdown_cell(cell) for cell in normalized[header_index]]
    seen: dict[str, int] = {}
    for index, name in enumerate(header):
        base = name if name != "—" else ("项目" if index == 0 else f"列{index + 1}")
        seen[base] = seen.get(base, 0) + 1
        header[index] = base if seen[base] == 1 else f"{base}_{seen[base]}"
    lines.extend(
        [
            "| " + " | ".join(header) + " |",
            "|" + "|".join("---" for _ in header) + "|",
        ]
    )
    header_key = tuple(header)
    for row in normalized[header_index + 1 :]:
        cells = [_markdown_cell(cell) for cell in row]
        if tuple(cells) == header_key or all(cell == "—" for cell in cells):
            continue
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _financial_statement_lines(state: dict[str, Any]) -> list[str]:
    tables = list(state.get("raw_statements", []) or [])
    lines = [
        "",
        "### 三大财务报表（招股书原表还原）",
        "",
        "> 下表由文档抽取层还原，不由 LLM 生成或补数。单位、口径和页码以招股书原表为准；完整结构化数据同时保存在 Excel、JSON 与 SQLite 中。",
    ]
    for statement_type, title in _STATEMENT_TITLES.items():
        lines.extend(["", f"#### {title}", ""])
        table = _select_primary_statement(tables, statement_type)
        if table is None:
            lines.append(f"- 未识别到{title}原表；该缺口已保留，禁止模型推测或补造数字。")
            continue
        pages = "、".join(f"P{page}" for page in (_value(table, "pages", []) or []))
        metadata = [
            f"来源：{pages or '页码待核验'}",
            f"口径：{_value(table, 'entity_scope', None) or '原表未标明'}",
            f"单位：{_value(table, 'unit', None) or '见原表'}",
            f"币种：{_value(table, 'currency', None) or '见原表'}",
        ]
        lines.extend(["- " + "；".join(metadata), ""])
        lines.extend(_statement_table_lines(table))
    return lines


def render_due_diligence_markdown(state: dict[str, Any]) -> str:
    """Keep facts, assessments, risks, and unanswered questions separate."""
    company = state.get("company", "未命名公司")
    evidence_items: list[Evidence] = state.get("research_evidence", [])
    findings: list[Finding] = state.get("research_findings", [])
    evidence = {item.evidence_id: item for item in evidence_items}
    findings_by_agent: dict[str, list[Finding]] = defaultdict(list)
    for item in findings:
        findings_by_agent[item.agent_name].append(item)

    conclusion = state.get("due_diligence_conclusion")
    risk_review = state.get("risk_review")
    prospectus = state.get("prospectus_analysis")
    dossier = _value(prospectus, "dossier")
    metrics = list(state.get("metrics", []) or [])
    challenges = list(state.get("challenges", []) or [])
    questions = list(state.get("diligence_questions", []) or [])
    financial_findings = list(state.get("financial_findings", []) or [])

    lines = [
        f"# {company}港股 IPO 公司尽调报告",
        "",
        "> 本报告由 Research Ledger 确定性渲染。结论必须引用招股书页码、计算结果或真实外部 URL；本报告不包含投资金额、估值上限或退出建议。",
        "",
        "## 一、尽调摘要",
        "",
        f"- 综合结论：**{_value(conclusion, 'verdict', '尚未形成')}**",
        f"- 历史财务质量：**{_value(conclusion, 'historical_financial_quality', 'insufficient_evidence')}**",
        f"- 未来盈利能力：**{_value(conclusion, 'future_earning_power', 'insufficient_evidence')}**",
        f"- 重大风险水平：**{_value(conclusion, 'material_risk_level', _value(risk_review, 'risk_level', '未评定'))}**",
        f"- 已登记证据：{len(evidence_items)} 条；已验证发现：{len(findings)} 条；待补充尽调：{len(questions)} 条",
        "",
        "## 二、公司概况、股权与商业模式",
        "",
    ]

    business_model = _value(prospectus, "business_model", "")
    business_evidence = list(
        _value(prospectus, "business_model_evidence", []) or []
    )
    if business_model and business_evidence:
        lines.append(
            f"- 商业模式：{business_model} "
            + " ".join(_evidence_label(item) for item in business_evidence)
        )
    else:
        lines.append("- 商业模式尚未形成具备页码证据的结论。")
    topic_titles = {
        "history_ownership": "公司沿革、股权与控制权",
        "capital_events": "融资、并购及重大资本事件",
        "products_business_model": "产品、服务与商业模式",
        "customers_suppliers": "客户与供应商",
        "operations": "研发、生产、销售、交付与回款",
        "subsidiaries_management": "子公司、经营主体与管理层",
    }
    topic_findings = _value(dossier, "topic_findings", {}) or {}
    for topic, title in topic_titles.items():
        lines.extend(["", f"### {title}", ""])
        items = topic_findings.get(topic, [])
        if not items:
            lines.append("- 尚未形成经页码校验的详细底稿。")
            continue
        for item in items:
            labels = {
                "fact": "披露事实",
                "company_explanation": "公司解释",
                "analyst_inference": "分析判断",
            }
            citations = " ".join(
                _evidence_label(entry) for entry in (_value(item, "evidence", []) or [])
            )
            kind = labels.get(_value(item, "finding_type", "fact"), "披露事实")
            lines.append(f"- **{kind}**：{_value(item, 'statement', '')} {citations}".rstrip())
    dossier_questions = list(_value(dossier, "open_questions", []) or [])
    if dossier_questions:
        lines.extend(["", "### 公司与业务补充核查问题", ""])
        lines.extend(f"- {item}" for item in dossier_questions)
    for title, field in (
        ("主要产品与服务", "main_products"),
        ("客户", "customers"),
        ("供应商", "suppliers"),
        ("管理层", "management_team"),
    ):
        lines.extend(["", f"### {title}", ""])
        lines.extend(_entity_lines(list(_value(prospectus, field, []) or [])))

    lines.extend(["", "## 三、行业与竞争", ""])
    lines.extend(
        _finding_lines(
            findings_by_agent.get("industry_competition", []),
            evidence,
            "尚无招股书之外的行业证据，行业判断保留为待核验事项。",
        )
    )

    lines.extend(["", "## 四、历史财务表现与盈利质量", ""])
    lines.extend(
        _finding_lines(
            findings_by_agent.get("financial_dd", []),
            evidence,
            "暂无通过 Evidence Ledger 校验的财务异常结论。",
        )
    )
    lines.extend(_financial_statement_lines(state))
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

    lines.extend(["", "### 财务异常的解释状态", ""])
    status_labels = {
        "observation": "待解释观察",
        "partially_explained": "部分解释",
        "unexplained": "尚未解释",
        "contradiction": "解释矛盾",
    }
    triggered = [item for item in financial_findings if _value(item, "triggered", False)]
    if not triggered:
        lines.append("- 暂无触发财务核查规则的事项。")
    for item in triggered:
        status = _value(item, "assessment_status", "observation")
        lines.append(
            f"- **{_value(item, 'rule_id', '')} / {status_labels.get(status, status)}**："
            f"{_value(item, 'name', '')}。{_value(item, 'description', '')}"
        )
        explanations = list(_value(item, "possible_explanations", []) or [])
        required = list(_value(item, "required_evidence", []) or [])
        escalation = list(_value(item, "escalation_conditions", []) or [])
        if explanations:
            lines.append(f"  - 可能解释（待验证）：{'；'.join(explanations)}")
        if required:
            lines.append(f"  - 需要证据：{'；'.join(required)}")
        if escalation:
            lines.append(f"  - 升级为风险的条件：{'；'.join(escalation)}")

    lines.extend(["", "## 五、未来持续盈利能力", ""])
    company_findings = findings_by_agent.get("company_business", [])
    lines.extend(
        _finding_lines(
            company_findings,
            evidence,
            "公司业务事实仍不足以判断持续盈利能力。",
        )
    )
    if not findings_by_agent.get("industry_competition"):
        lines.append("- 缺少外部行业与竞争证据，暂不能验证公司增长叙述。")

    lines.extend(["", "## 六、法务、合规、治理与负面事项", ""])
    lines.extend(
        _finding_lines(
            findings_by_agent.get("legal_governance", []),
            evidence,
            "未形成法务治理结论；仍需进行定向章节及外部数据库核查。",
        )
    )
    lines.append("- 上述内容仅为审查线索，不构成法律意见。")

    lines.extend(["", "## 七、跨 Agent 冲突与重大风险", ""])
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
    for item in challenges:
        status = "已解决" if _value(item, "resolved", False) else "未解决"
        lines.append(
            f"- [{_value(item, 'severity', 'important')}/{status}] "
            f"{_value(item, 'question', '')}"
        )

    lines.extend(["", "## 八、综合尽调判断", ""])
    lines.extend(
        [f"- 核心优势：{item}" for item in _value(conclusion, "key_strengths", [])]
        or ["- 核心优势尚缺少充分证据。"]
    )
    lines.extend(
        [f"- 核心风险：{item}" for item in _value(conclusion, "key_risks", [])]
        or ["- 暂无结构化核心风险摘要。"]
    )

    lines.extend(["", "## 九、P0/P1/P2 补充尽调清单", ""])
    if questions:
        for priority in ("P0", "P1", "P2"):
            selected = [item for item in questions if _value(item, "priority") == priority]
            if not selected:
                continue
            lines.extend([f"### {priority}", ""])
            for item in selected:
                materials = "、".join(_value(item, "requested_materials", []) or [])
                lines.extend(
                    [
                        f"- **问题**：{_value(item, 'question', '')}",
                        f"  - 原因：{_value(item, 'rationale', '')}",
                        f"  - 所需材料：{materials or '待明确'}",
                        f"  - 未解决影响：{_value(item, 'downside_if_unresolved', '')}",
                    ]
                )
    else:
        lines.append("- 暂无结构化补充尽调问题。")

    lines.extend(
        [
            "",
            "## 十、证据索引",
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
            f"| {item.evidence_id} | {item.source_type} | "
            f"{title} | {location} | {item.confidence:.2f} |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "本报告用于尽调研究辅助，不构成审计意见、法律意见或投资承诺。",
        ]
    )
    return "\n".join(lines)


def render_investment_markdown(state: dict[str, Any]) -> str:
    """Backward-compatible function name for callers before Mainline A."""
    return render_due_diligence_markdown(state)
