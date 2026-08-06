from __future__ import annotations
from typing import Any
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.schemas.final_synthesis import FinalSynthesisContext, FinalSynthesisDraft
from .final_synthesis import deterministic_draft

FINAL_SYNTHESIS_SYSTEM_PROMPT = """你是IPO尽调最终研究综合员。只能使用输入中的Topic Review结果、standalone Finding、Evidence Gap和Follow-up。不得新增数字、主体、案件、竞争对手或外部事实，不得修改原始Finding，不得输出review_status。所有观点必须引用输入中的topic_id、finding_id或evidence_id。请严格返回JSON Schema。"""

def run_final_synthesis(context: FinalSynthesisContext, client: OpenAICompatibleClient | None = None) -> tuple[FinalSynthesisDraft, str]:
    if client is None:
        return deterministic_draft(context), "deterministic_fallback"
    payload = context.model_dump(mode="json")
    prompt = "请综合以下受限研究材料，输出三轴判断、Strength、Risk、Mixed和补充尽调问题候选，不要输出最终状态：\n" + str(payload)
    try:
        draft = client.complete_json(system_prompt=FINAL_SYNTHESIS_SYSTEM_PROMPT, user_prompt=prompt, response_model=FinalSynthesisDraft, max_tokens=6000)
        allowed_findings = {str(item.get("finding_id")) for item in context.standalone_findings if isinstance(item, dict)} | {x for topic in context.reviewed_topics for x in topic.reviewed_finding_ids}
        allowed_evidence = {x for topic in context.reviewed_topics for x in topic.reviewed_evidence_ids}
        refs = set(draft.approved_finding_ids) | set(draft.excluded_finding_ids)
        refs |= {x for point in [*draft.reviewed_strengths, *draft.reviewed_risks, *draft.reviewed_mixed_points] for x in point.finding_ids}
        if not refs.issubset(allowed_findings):
            raise ValueError("Final Synthesis referenced an unknown Finding ID")
        for point in [*draft.reviewed_strengths, *draft.reviewed_risks, *draft.reviewed_mixed_points]:
            if not set(point.evidence_ids).issubset(allowed_evidence):
                raise ValueError("Final Synthesis referenced an unknown Evidence ID")
        return draft, "qwen"
    except Exception:
        return deterministic_draft(context), "deterministic_fallback"
