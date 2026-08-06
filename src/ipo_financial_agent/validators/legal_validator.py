from __future__ import annotations

from ipo_financial_agent.schemas.legal import LegalClaim, LegalEntity, LegalFinding, LegalProfileFact, LegalResearchTask, LegalValidationResult

FORBIDDEN = ("行业第一", "技术领先", "市场第一", "绝对安全", "不存在法律风险", "一定长期稳定")

def validate_legal_result(*, task: LegalResearchTask, entities: list[LegalEntity], profile_facts: list[LegalProfileFact], claims: list[LegalClaim], findings: list[LegalFinding] | None = None, evidence_ids: set[str]) -> LegalValidationResult:
    errors: list[str] = []
    expected = {item.research_topic for item in task.questions}
    seen = {item.research_topic for item in profile_facts} | {item.research_topic for item in claims}
    if task.target_agent != "legal_governance" or len(task.questions) != 6:
        errors.append("fixed legal task must contain six legal questions")
    if expected - seen:
        errors.append("missing legal topics: " + ",".join(sorted(item.value for item in expected - seen)))
    entity_ids = {item.entity_id for item in entities}
    for item in profile_facts:
        if set(item.evidence_ids) - evidence_ids or set(item.entity_ids) - entity_ids:
            errors.append(f"profile fact {item.profile_fact_id} has unknown references")
        if any(word in item.statement for word in FORBIDDEN):
            errors.append(f"profile fact {item.profile_fact_id} crosses legal scope")
    for item in claims:
        if set(item.prospectus_evidence_ids) - evidence_ids or set(item.related_entity_ids) - entity_ids:
            errors.append(f"claim {item.claim_id} has unknown references")
    for item in findings or []:
        if set(item.evidence_ids) - evidence_ids or set(item.entity_ids) - entity_ids:
            errors.append(f"finding {item.finding_id} has unknown references")
    return LegalValidationResult(valid=not errors, task_valid=task.target_agent == "legal_governance", evidence_integrity=not any("unknown references" in error for error in errors), scope_valid=not any("scope" in error for error in errors), validation_errors=errors, checked_topics=sorted(expected, key=lambda item: item.value))
