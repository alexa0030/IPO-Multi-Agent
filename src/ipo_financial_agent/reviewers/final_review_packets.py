from __future__ import annotations

from typing import Any

from ipo_financial_agent.schemas.final_reviewer import FinalReviewInput, TopicPacketValidation, TopicReviewPacket

TOPICS = {
    "customer_quality_and_collection": ("客户关系、收入质量和回款表现是否形成一致结论？", ("customer", "receivable", "cash", "collection")),
    "product_structure_and_earnings_quality": ("产品结构、毛利和盈利质量是否相互支持？", ("product", "margin", "inventory", "earnings")),
    "growth_plan_and_funding_capacity": ("增长计划是否有足够资金和产能支撑？", ("growth", "capex", "debt", "funding")),
    "technology_and_competitive_barriers": ("技术能力和竞争壁垒是否有外部证据支持？", ("technology", "patent", "barrier", "competition")),
    "supply_chain_and_cost_pressure": ("供应链依赖和成本压力是否可控？", ("supplier", "inventory", "cost")),
    "related_party_and_business_independence": ("关联交易是否影响业务独立性？", ("related", "customer", "receivable")),
    "litigation_penalty_and_financial_impact": ("诉讼处罚是否可能影响财务结果？", ("litigation", "penalty", "legal")),
    "license_ip_and_continuity": ("许可、知识产权和持续经营是否有足够支撑？", ("license", "ip", "continuity")),
}


def _dump(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def build_final_review_input(pack: Any) -> FinalReviewInput:
    data = _dump(pack)
    return FinalReviewInput(
        strength_findings=data.get("strength_findings", []),
        risk_findings=data.get("risk_findings", []),
        mixed_findings=data.get("mixed_findings", []),
        important_neutral_findings=data.get("neutral_findings", []),
        claim_assessments=data.get("claim_assessments", []),
        evidence_gaps=data.get("evidence_gaps", []),
        follow_up_requests=data.get("follow_up_requests", []),
        finding_index=data.get("finding_index", []),
        evidence_index=data.get("evidence_index", []),
    )


def _id(item: Any, fallback: str) -> str:
    data = _dump(item)
    return str(data.get("finding_id") or data.get("evidence_id") or fallback) if isinstance(data, dict) else fallback


def _text(item: Any) -> str:
    data = _dump(item)
    if not isinstance(data, dict):
        return str(data).lower()
    return " ".join(str(data.get(key, "")) for key in ("question", "conclusion", "statement", "research_topic", "topic")).lower()


def build_topic_review_packets(review_input: Any) -> list[TopicReviewPacket]:
    data = _dump(review_input)
    all_findings = data.get("finding_index", [])
    packets: list[TopicReviewPacket] = []
    for topic, (question, terms) in TOPICS.items():
        selected = [item for item in all_findings if any(term in _text(item) for term in terms)]
        positive = [_id(item, f"finding_{index}") for index, item in enumerate(selected) if (_dump(item).get("finding_nature") if isinstance(_dump(item), dict) else "") == "strength"]
        negative = [_id(item, f"finding_{index}") for index, item in enumerate(selected) if (_dump(item).get("finding_nature") if isinstance(_dump(item), dict) else "") == "risk"]
        mixed = [_id(item, f"finding_{index}") for index, item in enumerate(selected) if (_dump(item).get("finding_nature") if isinstance(_dump(item), dict) else "") == "mixed"]
        packets.append(TopicReviewPacket(review_topic=topic, review_question=question, finding_ids=[_id(item, f"finding_{index}") for index, item in enumerate(selected)], findings=selected, positive_material_ids=positive, negative_material_ids=negative, mixed_material_ids=mixed, evidence_gaps=data.get("evidence_gaps", []), follow_up_requests=data.get("follow_up_requests", [])))
    return packets


def validate_topic_packets(packets: list[TopicReviewPacket], review_input: Any) -> TopicPacketValidation:
    data = _dump(review_input)
    finding_ids = {_id(item, "") for item in data.get("finding_index", [])}
    errors: list[str] = []
    for packet in packets:
        unknown = set(packet.finding_ids) - finding_ids
        if unknown:
            errors.append(f"{packet.review_topic}: unknown findings {sorted(unknown)}")
    return TopicPacketValidation(valid=not errors, errors=errors, checked_topics=[packet.review_topic for packet in packets])
