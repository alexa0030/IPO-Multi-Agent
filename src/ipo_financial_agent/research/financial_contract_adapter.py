"""Adapt the mature financial toolchain into the PRD v2 research contracts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ipo_financial_agent.models import MetricResult, StatementFact
from ipo_financial_agent.models_agent import FinancialFinding as LegacyFinancialFinding
from ipo_financial_agent.schemas import (
    CompletionCheck,
    Evidence,
    FinancialAgentResult,
    Finding,
    QuestionAnswerMapping,
    ResearchTask,
)


def fact_evidence_id(fact_id: str) -> str:
    return f"PDF_{fact_id}"


def metric_evidence_id(metric_id: str) -> str:
    return f"CALC_{metric_id}"


def register_financial_evidence(
    *,
    facts: Iterable[StatementFact],
    metrics: Iterable[MetricResult],
) -> list[Evidence]:
    """Convert deterministic facts first, then calculations with full lineage."""
    fact_items = list(facts)
    metric_items = list(metrics)
    fact_ids = {item.fact_id for item in fact_items}
    evidence: list[Evidence] = []
    for fact in fact_items:
        evidence.append(
            Evidence(
                evidence_id=fact_evidence_id(fact.fact_id),
                source_type="prospectus",
                title=f"{fact.statement_name}｜{fact.item_name}",
                content=(
                    f"{fact.period}：{fact.raw_value}"
                    f"{(' ' + fact.unit) if fact.unit else ''}"
                ),
                page_number=fact.page,
                section=fact.statement_name,
                raw_value=fact.value,
                source_quality="A",
                created_by="financial",
            )
        )
    for metric in metric_items:
        inputs = [
            fact_evidence_id(item)
            for item in metric.source_fact_ids
            if item in fact_ids
        ]
        if not inputs:
            continue
        evidence.append(
            Evidence(
                evidence_id=metric_evidence_id(metric.metric_id),
                source_type="calculation",
                title=f"{metric.metric_name}｜{metric.period}",
                content=f"{metric.metric_name}（{metric.period}）={metric.display_value}",
                formula=metric.formula,
                input_evidence_ids=inputs,
                raw_value=metric.value,
                source_quality="A",
                created_by="financial",
            )
        )
    return evidence


def convert_selling_expense_rule(
    *,
    task: ResearchTask,
    rule_result: LegacyFinancialFinding,
    metrics: Iterable[MetricResult],
) -> Finding:
    """Convert RA-001 into one complete, reviewable Financial Finding."""
    if task.target_agent != "financial":
        raise ValueError("Financial finding requires a financial ResearchTask")
    if rule_result.rule_id != "RA-001" or not rule_result.triggered:
        raise ValueError("expected a triggered RA-001 rule result")
    ratio_metrics = sorted(
        [item for item in metrics if item.metric_code == "selling_expense_ratio"],
        key=lambda item: item.period,
    )
    if len(ratio_metrics) < 2:
        raise ValueError("RA-001 conversion requires at least two period metrics")
    calculation_ids = [metric_evidence_id(item.metric_id) for item in ratio_metrics]
    input_ids = [
        fact_evidence_id(fact_id)
        for metric in ratio_metrics
        for fact_id in metric.source_fact_ids
    ]
    trend = "，".join(
        f"{item.period}年{item.display_value}" for item in ratio_metrics
    )
    severity_map = {
        "critical": "high",
        "high": "high",
        "warning": "medium",
        "info": "low",
    }
    interpretation = rule_result.interpretation.strip() or (
        "销售费用率连续上升表明获客和市场拓展投入增加；是否属于增长投入或效率恶化，"
        "必须结合新增客户、销售人员、新市场收入贡献及同行水平进一步核验。"
    )
    return Finding(
        finding_id="FIN_RA_001",
        task_id=task.task_id,
        agent="financial",
        topic="selling_expense_quality",
        title=rule_result.name,
        statement=f"报告期销售费用率为{trend}，呈连续上升趋势。",
        evidence_ids=list(dict.fromkeys([*input_ids, *calculation_ids])),
        interpretation=interpretation,
        alternative_explanations=list(rule_result.possible_explanations),
        required_checks=list(rule_result.required_evidence),
        cross_check_topics=[
            "customer_growth",
            "market_expansion",
            "peer_selling_expense_ratio",
        ],
        risk_level=severity_map.get(rule_result.severity, "medium"),
        confidence="high" if len(ratio_metrics) >= 3 else "medium",
    )


def select_supported_rule(findings: Iterable[Any]) -> LegacyFinancialFinding:
    """Select the single golden-path rule supported in phase one."""
    for item in findings:
        if getattr(item, "rule_id", "") == "RA-001" and getattr(item, "triggered", False):
            return item
    raise ValueError("golden-path rule RA-001 was not triggered")


_RULE_META = {
    "EQ-002": {
        "finding_id": "FIN_EQ_002",
        "topic": "cash_flow_quality",
        "formula": "经营活动现金流/营业收入",
        "cross_checks": ["receivable_quality", "customer_settlement_terms"],
    },
    "RA-001": {
        "finding_id": "FIN_RA_001",
        "topic": "selling_expense_quality",
        "formula": "销售费用/营业收入",
        "cross_checks": ["customer_growth", "market_expansion"],
    },
    "RA-003": {
        "finding_id": "FIN_RA_003",
        "topic": "revenue_tax_consistency",
        "formula": "营业收入增长率-已付所得税增长率",
        "cross_checks": ["tax_payment_timing", "revenue_recognition"],
    },
}


def _severity(value: str) -> str:
    return {"critical": "high", "high": "high", "warning": "medium"}.get(value, "low")


def convert_triggered_rules(
    *, task: ResearchTask, rules: Iterable[LegacyFinancialFinding], evidence: list[Evidence]
) -> tuple[list[Evidence], list[Finding]]:
    """Convert supported deterministic rules without changing their financial numbers."""
    if task.target_agent != "financial":
        raise ValueError("Financial findings require a financial ResearchTask")
    registered = {item.evidence_id for item in evidence}
    additions: list[Evidence] = []
    findings: list[Finding] = []
    for rule in rules:
        meta = _RULE_META.get(rule.rule_id)
        if not meta or not rule.triggered:
            continue
        source_ids: list[str] = []
        for index, legacy in enumerate(rule.evidence, start=1):
            if legacy.page <= 0:
                continue
            evidence_id = f"PDF_{rule.rule_id.replace('-', '_')}_{legacy.page}_{index}"
            source_ids.append(evidence_id)
            if evidence_id not in registered:
                additions.append(Evidence(
                    evidence_id=evidence_id,
                    source_type="prospectus",
                    title=f"{rule.name}底层披露",
                    content=legacy.detail or rule.description,
                    page_number=legacy.page,
                    section=legacy.source or "财务资料",
                    source_quality="A",
                    created_by="financial",
                ))
                registered.add(evidence_id)
        if rule.rule_id == "RA-001":
            source_ids.extend(
                item.evidence_id for item in evidence
                if item.source_type == "calculation" and "销售费用率" in item.title
            )
        if not source_ids:
            # Every rule must retain prospectus lineage; do not invent a finding if it cannot.
            continue
        calc_id = f"CALC_{rule.rule_id.replace('-', '_')}"
        calc = Evidence(
            evidence_id=calc_id,
            source_type="calculation",
            title=rule.name,
            content=rule.description,
            formula=meta["formula"],
            input_evidence_ids=list(dict.fromkeys(source_ids)),
            raw_value=rule.metrics,
            source_quality="A",
            created_by="financial",
        )
        additions.append(calc)
        findings.append(Finding(
            finding_id=meta["finding_id"],
            task_id=task.task_id,
            agent="financial",
            topic=meta["topic"],
            title=rule.name,
            statement=rule.description,
            evidence_ids=[*dict.fromkeys([*source_ids, calc_id])],
            interpretation=(rule.interpretation.strip() or
                "该异常需要结合业务口径、会计时点及明细资料核验，现阶段不作负面事项定性。"),
            alternative_explanations=list(rule.possible_explanations),
            required_checks=list(rule.required_evidence),
            upgrade_condition="；".join(rule.escalation_conditions) or None,
            cross_check_topics=meta["cross_checks"],
            risk_level=_severity(rule.severity),
            confidence="high" if len(source_ids) >= 2 else "medium",
        ))
    return [*evidence, *additions], findings


def build_financial_agent_result(
    *, task: ResearchTask, rules: Iterable[LegacyFinancialFinding], evidence: list[Evidence],
    metrics: Iterable[MetricResult] = (),
) -> FinancialAgentResult:
    all_evidence, findings = convert_triggered_rules(task=task, rules=rules, evidence=evidence)
    metric_list = list(metrics)
    metric_map = {
        item.metric_code: item for item in metric_list
        if item.status == "ok" and item.value is not None
    }
    cash_metric = metric_map.get("ocf_to_net_profit")
    if cash_metric:
        findings.append(Finding(
            finding_id="FIN_FA_Q001",
            task_id=task.task_id,
            agent="financial",
            topic="profit_cash_conversion",
            title="利润向经营现金流转化情况",
            statement=f"{cash_metric.period}年经营现金流与净利润比率为{cash_metric.display_value}。",
            evidence_ids=[metric_evidence_id(cash_metric.metric_id)],
            interpretation="该比率反映利润的现金实现程度，应结合多期趋势及营运资金变动核验。",
            alternative_explanations=["回款结算时点变化", "存货及其他营运资金投入"],
            required_checks=["经营现金流与净利润调节表", "期后回款及营运资金明细"],
            upgrade_condition="若多期现金转化持续恶化且无法由营运资金变化解释，则升级风险判断。",
            cross_check_topics=["receivable_quality", "inventory_quality"],
            risk_level="medium" if cash_metric.value < 1 else "low",
            confidence="high",
        ))
    revenue = metric_map.get("revenue_growth")
    receivable = metric_map.get("receivable_growth")
    inventory = metric_map.get("inventory_growth")
    if revenue and receivable:
        gap = receivable.value - revenue.value
        findings.append(Finding(
            finding_id="FIN_FA_Q002",
            task_id=task.task_id,
            agent="financial",
            topic="receivable_revenue_match",
            title="应收账款增长与收入增长的匹配情况",
            statement=(f"{revenue.period}年收入增长{revenue.display_value}，"
                f"应收账款增长{receivable.display_value}。"),
            evidence_ids=[metric_evidence_id(item.metric_id) for item in (revenue, receivable)],
            interpretation="应收账款增速高于收入增速，需进一步核验销售回款质量。",
            alternative_explanations=["期末销售集中", "客户结构或信用期变化", "并购并表口径变化"],
            required_checks=["应收账款账龄", "主要客户期后回款"],
            upgrade_condition="若期后回款异常或账龄显著恶化，则升级风险判断。",
            cross_check_topics=["customer_concentration", "cash_flow_quality"],
            risk_level="medium" if gap > .15 else "low",
            confidence="high",
        ))
    if revenue and inventory:
        gap = inventory.value - revenue.value
        findings.append(Finding(
            finding_id="FIN_FA_Q003",
            task_id=task.task_id,
            agent="financial",
            topic="inventory_revenue_match",
            title="存货增长与收入增长的匹配情况",
            statement=(f"{revenue.period}年收入增长{revenue.display_value}，"
                f"存货增长{inventory.display_value}。"),
            evidence_ids=[metric_evidence_id(item.metric_id) for item in (revenue, inventory)],
            interpretation=("存货增速低于收入增速，本指标本身未显示同步积压；"
                "仍需结合库龄和跌价准备核验资产质量。"),
            alternative_explanations=["备货策略变化", "供应链效率变化", "并购并表口径变化"],
            required_checks=["存货库龄", "存货跌价准备", "期后销售情况"],
            upgrade_condition="若长库龄存货增加且跌价准备不足，则升级风险判断。",
            cross_check_topics=["capacity_utilization", "asset_quality"],
            risk_level="medium" if gap > .15 else "low",
            confidence="high",
        ))
    findings_by_topic: dict[str, list[Finding]] = {}
    for item in findings:
        findings_by_topic.setdefault(item.topic.value, []).append(item)
    mappings: list[QuestionAnswerMapping] = []
    evidence_by_id = {item.evidence_id: item for item in all_evidence}
    question_ids_by_finding: dict[str, list[str]] = {}
    for question in task.questions:
        matched = findings_by_topic.get(question.research_topic.value, [])
        mapped_evidence = list(dict.fromkeys(
            evidence_id for finding in matched for evidence_id in finding.evidence_ids
        ))
        checks: list[CompletionCheck] = []
        for criterion in question.completion_criteria:
            if "计算证据" in criterion or "增长率" in criterion:
                passed = any(
                    evidence_by_id[item].source_type == "calculation"
                    for item in mapped_evidence if item in evidence_by_id
                )
            else:
                passed = bool(matched and mapped_evidence)
            checks.append(CompletionCheck(
                criterion=criterion,
                passed=passed,
                evidence_ids=mapped_evidence if passed else [],
                note=None if passed else "现有Finding或Evidence不足以满足该完成标准",
            ))
        all_checks_pass = bool(checks) and all(item.passed for item in checks)
        if matched and mapped_evidence and all_checks_pass:
            status = "answered"
            gap_reason = None
        elif matched:
            status = "partially_answered"
            gap_reason = "存在Finding，但完成标准或证据要求尚未全部满足"
        else:
            status = "unanswered"
            gap_reason = "没有与该研究主题匹配的Finding"
        mappings.append(QuestionAnswerMapping(
            question_id=question.question_id,
            research_topic=question.research_topic,
            finding_ids=[item.finding_id for item in matched],
            evidence_ids=mapped_evidence,
            completion_checks=checks,
            status=status,
            gap_reason=gap_reason,
        ))
        for finding in matched:
            question_ids_by_finding.setdefault(finding.finding_id, []).append(question.question_id)
    findings = [item.model_copy(update={
        "answered_question_ids": question_ids_by_finding.get(item.finding_id, [])
    }) for item in findings]
    all_answered = bool(mappings) and all(item.status == "answered" for item in mappings)
    missing_p0 = {
        question.question_id for question in task.questions if question.priority == "P0"
    } - {item.question_id for item in mappings if item.status == "answered"}
    errors = [] if findings else ["No supported, traceable financial findings were produced."]
    return FinancialAgentResult(
        task_id=task.task_id,
        evidences=all_evidence,
        findings=findings,
        question_answer_map=mappings,
        completion_status=("completed" if all_answered else ("failed" if not findings else "partial")),
        errors=errors + ([f"Unanswered P0 questions: {sorted(missing_p0)}"] if missing_p0 else []),
    )
