from __future__ import annotations
import re
from typing import Any
from ipo_financial_agent.schemas.topic_review import ReviewedTopicResult, TopicReviewValidation

def validate_topic_review(result: ReviewedTopicResult, packet: Any, *, rejected_finding_ids: set[str] | None = None) -> TopicReviewValidation:
    data = packet.model_dump(mode="json") if hasattr(packet, "model_dump") else packet
    allowed_findings = set(data.get("finding_ids", [])); allowed_evidence = set()
    for item in data.get("findings", []):
        if isinstance(item, dict): allowed_evidence.update(item.get("evidence_ids", []))
    errors=[]; warnings=[]
    unknown_f = set(result.reviewed_finding_ids) - allowed_findings
    unknown_e = set(result.reviewed_evidence_ids) - allowed_evidence
    if unknown_f: errors.append("unknown finding ids: "+str(sorted(unknown_f)))
    if unknown_e: errors.append("unknown evidence ids: "+str(sorted(unknown_e)))
    rejected_finding_ids = rejected_finding_ids or set()
    if rejected_finding_ids.intersection(result.reviewed_finding_ids): errors.append("result references validator-rejected finding")
    text = result.integrated_statement + " " + " ".join(result.positive_factors + result.negative_factors)
    if re.search(r"不存在|一定|必然|绝对", text) and result.conclusion_nature != "insufficient_evidence": warnings.append("结论可能把有限材料写成绝对判断")
    if result.suggested_severity == "high": warnings.append("high 仅为模型建议，必须由确定性规则决定")
    return TopicReviewValidation(topic_id=result.topic_id, valid=not errors, errors=errors, warnings=warnings)
