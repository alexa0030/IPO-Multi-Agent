"""Convert legacy v0.3 Agent outputs into the unified Research Ledger."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ipo_financial_agent.models_agent import (
    Evidence,
    Finding,
    IndustryAnalysis,
    LegalGovernanceAnalysis,
    ProspectusAnalysis,
    ResearchPatch,
)


def _deduplicate_evidence(items: Iterable[Evidence]) -> list[Evidence]:
    return list({item.evidence_id: item for item in items}.values())


def financial_research_patch(items: Iterable[Any]) -> ResearchPatch:
    """Ground triggered forensic conclusions in their existing evidence."""
    evidence: list[Evidence] = []
    findings: list[Finding] = []
    for item in items:
        if not getattr(item, "triggered", False):
            continue
        item_evidence = list(getattr(item, "evidence", []) or [])
        evidence.extend(item_evidence)
        if not item_evidence:
            continue
        rule_id = getattr(item, "rule_id", "")
        name = getattr(item, "name", "")
        conclusion = (
            getattr(item, "interpretation", "")
            or getattr(item, "description", "")
            or name
        )
        findings.append(
            Finding(
                finding_id=f"financial_{rule_id.lower()}",
                agent_name="financial_dd",
                question=f"财务取证规则 {rule_id} 是否触发？",
                conclusion=conclusion,
                evidence_ids=[entry.evidence_id for entry in item_evidence],
                evidence_strength="strong",
                risks=[name] if name else [],
                open_questions=[getattr(item, "recommendation", "")]
                if getattr(item, "recommendation", "")
                else [],
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(evidence),
        findings=findings,
    )


def prospectus_research_patch(result: ProspectusAnalysis) -> ResearchPatch:
    """Collect traceable prospectus facts without inventing missing citations."""
    evidence = list(result.business_model_evidence)
    for group in (
        result.main_products,
        result.customers,
        result.suppliers,
        result.management_team,
    ):
        for entity in group:
            evidence.extend(entity.evidence)

    dossier = result.dossier
    for topic_items in dossier.topic_findings.values():
        for item in topic_items:
            evidence.extend(item.evidence)

    findings: list[Finding] = []
    if result.business_model and result.business_model_evidence:
        findings.append(
            Finding(
                agent_name="company_business",
                question="公司的核心商业模式是什么？",
                conclusion=result.business_model,
                evidence_ids=[
                    item.evidence_id for item in result.business_model_evidence
                ],
                evidence_strength="strong",
            )
        )

    topic_questions = {
        "history_ownership": "公司沿革、股权结构和控制权有哪些需要关注的事实？",
        "capital_events": "融资、收购、重组等资本事件如何影响当前业务和报表？",
        "products_business_model": "公司销售什么、如何定价交付并形成收入？",
        "customers_suppliers": "客户供应商结构、集中度、账期和议价关系如何？",
        "operations": "研发、生产、销售、交付与回款链条如何运转？",
        "subsidiaries_management": "重要经营主体和管理层如何分工并承担业务？",
    }
    type_labels = {
        "fact": "披露事实",
        "company_explanation": "发行人解释",
        "analyst_inference": "分析判断",
    }
    for topic, topic_items in dossier.topic_findings.items():
        if not topic_items:
            continue
        topic_evidence = [entry for item in topic_items for entry in item.evidence]
        if not topic_evidence:
            continue
        conclusion = "\n".join(
            f"[{type_labels.get(item.finding_type, '披露事实')}] {item.statement}"
            for item in topic_items
        )
        findings.append(
            Finding(
                agent_name="company_business",
                question=topic_questions.get(topic, f"公司业务主题 {topic} 的核查结论是什么？"),
                conclusion=conclusion,
                evidence_ids=[item.evidence_id for item in topic_evidence],
                evidence_strength=(
                    "weak"
                    if all(item.finding_type == "analyst_inference" for item in topic_items)
                    else "medium"
                ),
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(evidence),
        findings=findings,
        open_questions=list(
            dict.fromkeys(
                [
                    *dossier.open_questions,
                    *(
                        ["发行人所述竞争优势与风险因素尚需逐项绑定证据并交叉验证。"]
                        if (result.prospectus_risks or result.competitive_advantages)
                        else []
                    ),
                    *[
                        f"公司业务底稿仍缺少主题：{item}"
                        for item in dossier.coverage_gaps
                    ],
                ]
            )
        ),
    )


def industry_research_patch(result: IndustryAnalysis) -> ResearchPatch:
    """Publish industry claims while preserving issuer/external source scope."""
    if not result.evidence:
        return ResearchPatch(
            open_questions=["外部行业检索不可用，市场结论待补查。"]
        )
    external_evidence = [
        item
        for item in result.evidence
        if item.metadata.get("source_scope") == "external" and item.source_url
    ]
    has_external = bool(external_evidence)
    findings = list(result.structured_findings)
    issuer_evidence = [
        item
        for item in result.evidence
        if item.metadata.get("source_scope") != "external"
    ]
    industry_sections = (
        ("行业边界、需求和市场位置如何？", result.industry_overview),
        ("产业链上下游和公司的商业位置是什么？", "；".join(result.value_chain)),
        ("下游客户来自哪些行业，需求景气度如何？", "；".join(result.customer_industries)),
        ("市场规模、增速和生命周期如何？", result.market_growth),
        ("主要竞争者和竞争维度是什么？", "；".join(result.competitors)),
        ("竞争主要发生在哪些维度？", "；".join(result.competitive_dimensions)),
        ("竞争者为何难以迅速复制或抢占份额？", "；".join(result.barriers_to_entry)),
        ("未来增长驱动和行业变化是什么？", "；".join(result.industry_trends)),
        ("未来收入增长由哪些因素驱动？", "；".join(result.growth_drivers)),
        ("公司可向哪些新行业、产品或海外市场拓展？", "；".join(result.expansion_paths)),
        ("行业瓶颈、替代和周期风险是什么？", "；".join(result.industry_risks)),
    )
    if issuer_evidence and not result.structured_findings:
        for question, conclusion in industry_sections:
            if not conclusion.strip():
                continue
            findings.append(
                Finding(
                    agent_name="industry_competition",
                    question=question,
                    conclusion=conclusion,
                    evidence_ids=[item.evidence_id for item in issuer_evidence],
                    evidence_strength="weak",
                    risks=[conclusion] if "风险" in question else [],
                    open_questions=["发行人披露尚需与对应外部原文逐项交叉验证。"],
                )
            )

    industry_topics = {"industry", "competitors", "customers_suppliers", "policy"}
    legal_topics = {
        "hkex_filings",
        "regulatory",
        "corporate_registry",
        "litigation",
        "controller_related_parties",
        "financing_debt",
        "accounting_auditor",
        "adverse_media",
        "targeted_followup",
    }
    structured_evidence_ids = {
        evidence_id
        for finding in result.structured_findings
        for evidence_id in finding.evidence_ids
    }
    for item in external_evidence:
        topic = str(item.metadata.get("topic", "external_research"))
        agent_name = (
            "legal_governance"
            if topic in legal_topics
            else "industry_competition"
        )
        source_tier = str(item.metadata.get("source_tier", "unknown"))
        excerpt = " ".join(item.content.split())[:320]
        # A grounded LLM finding is more useful than a duplicate raw search
        # lead.  Keep unreferenced results visible so research coverage is not
        # silently lost.
        if item.evidence_id in structured_evidence_ids:
            continue
        findings.append(
            Finding(
                agent_name=agent_name,
                question=f"公开信息检索是否发现 {topic} 相关核查线索？",
                conclusion=(
                    f"外部公开信息线索（{topic}）：{item.title}。"
                    f"搜索摘要：{excerpt}"
                ),
                evidence_ids=[item.evidence_id],
                evidence_strength=(
                    "medium" if source_tier in {"official", "primary"} else "weak"
                ),
                risks=[topic] if agent_name == "legal_governance" else [],
                open_questions=["打开并阅读原始 URL，核对全文、主体、日期和当前状态。"],
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(result.evidence),
        findings=findings,
        open_questions=(
            ["已取得外部搜索线索，但尚需逐条打开原始 URL 核验。"]
            if has_external
            else ["招股书行业数据尚需独立行业来源交叉验证。"]
        ),
    )


def legal_governance_research_patch(
    result: LegalGovernanceAnalysis,
) -> ResearchPatch:
    """Publish legal review leads by category with their prospectus pages."""
    findings: list[Finding] = []
    by_category: dict[tuple[str, str], list[Evidence]] = {}
    for item in result.evidence:
        category = str(item.metadata.get("category", "legal_governance"))
        scope = str(item.metadata.get("source_scope", "issuer_disclosed"))
        by_category.setdefault((category, scope), []).append(item)
    for (category, scope), evidence in by_category.items():
        page_labels = "、".join(
            f"P{item.page_number}" for item in evidence if item.page_number
        )
        excerpts = "；".join(
            " ".join(item.content.split())[:220] for item in evidence[:2]
        )
        is_external = scope == "external"
        source_labels = "、".join(
            item.source_url or f"P{item.page_number}"
            for item in evidence
        )
        tiers = {str(item.metadata.get("source_tier", "unknown")) for item in evidence}
        findings.append(
            Finding(
                agent_name="legal_governance",
                question=(
                    f"公开信息是否存在 {category} 相关核查线索？"
                    if is_external
                    else f"招股书是否披露 {category} 相关核查线索？"
                ),
                conclusion=(
                    f"在{source_labels or '来源待核验'}取得 {len(evidence)} 条"
                    f" {category} 公开检索线索：{excerpts}"
                    if is_external
                    else f"在{page_labels or '页码待核验'}定位到 {len(evidence)} 条"
                    f" {category} 招股书核查线索：{excerpts}"
                ),
                evidence_ids=[item.evidence_id for item in evidence],
                evidence_strength=(
                    "medium"
                    if is_external and tiers.intersection({"official", "primary"})
                    else "weak" if is_external else "medium"
                ),
                risks=[f"待核实核查线索：{category}"],
                open_questions=[
                    (
                        "打开并阅读原始 URL，核实主体、法律效力、当前状态、涉及金额和全文语境。"
                        if is_external
                        else "核实事项法律效力、当前状态、涉及金额、对手方及披露完整性。"
                    )
                ],
            )
        )
    return ResearchPatch(
        evidence=_deduplicate_evidence(result.evidence),
        findings=findings,
        open_questions=result.open_questions,
    )
