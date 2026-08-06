from __future__ import annotations
import hashlib, re
from typing import Any
from ipo_financial_agent.schemas.final_synthesis import DueDiligenceQuestion

def merge_due_diligence_questions(candidates: list[Any], *, max_p0: int = 10, max_p1: int = 20, max_p2: int = 20) -> list[DueDiligenceQuestion]:
    seen: dict[tuple, DueDiligenceQuestion] = {}
    for item in candidates:
        data = item.model_dump(mode="json") if hasattr(item,"model_dump") else item
        question = str(data.get("question", "")).strip()
        if not question: continue
        materials = tuple(sorted(re.sub(r"\s+", "", str(x).lower()) for x in data.get("required_materials", [])))
        key=(tuple(sorted(data.get("related_topic_ids", []))),tuple(sorted(data.get("related_entity_ids", []))),materials)
        if key in seen: continue
        qid="DDQ_"+hashlib.sha1((str(key)+question).encode()).hexdigest()[:10]
        seen[key]=DueDiligenceQuestion(question_id=qid,priority=data.get("priority","P1"),question=question,reason=str(data.get("reason","")),required_materials=list(data.get("required_materials",[])),decision_impact=str(data.get("decision_impact","")),related_topic_ids=list(data.get("related_topic_ids",[])),related_finding_ids=list(data.get("related_finding_ids",[])),related_entity_ids=list(data.get("related_entity_ids",[])),target_owner=data.get("target_owner","company"))
    grouped={p:[] for p in ("P0","P1","P2")}
    for q in seen.values(): grouped[q.priority].append(q)
    return grouped["P0"][:max_p0]+grouped["P1"][:max_p1]+grouped["P2"][:max_p2]
