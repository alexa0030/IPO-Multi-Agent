from __future__ import annotations
from typing import Any
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.schemas.topic_review import ReviewedTopicResult, TopicReviewValidation
from .topic_review_prompt import TOPIC_REVIEW_SYSTEM_PROMPT, build_topic_prompt
from .topic_review_validator import validate_topic_review

class TopicReviewer:
    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def run(self, packets: list[Any], *, rejected_finding_ids: set[str] | None = None) -> tuple[list[ReviewedTopicResult], list[TopicReviewValidation]]:
        results=[]; validations=[]
        for packet in packets:
            data = packet.model_dump(mode="json") if hasattr(packet, "model_dump") else packet
            topic_id = str(data.get("review_topic", "unknown"))
            try:
                if self.client is None or not data.get("findings"):
                    result = self._insufficient(data)
                else:
                    result = self.client.complete_json(system_prompt=TOPIC_REVIEW_SYSTEM_PROMPT, user_prompt=build_topic_prompt(data), response_model=ReviewedTopicResult, max_tokens=1800)
                    if not result.topic_id: result.topic_id = topic_id
                validation = validate_topic_review(result, data, rejected_finding_ids=rejected_finding_ids)
                if not validation.valid:
                    result = self._insufficient(data, gaps=validation.errors)
                    validation = validate_topic_review(result, data, rejected_finding_ids=rejected_finding_ids)
            except Exception as exc:
                result = self._insufficient(data, gaps=[f"topic reviewer failed: {type(exc).__name__}"])
                validation = validate_topic_review(result, data, rejected_finding_ids=rejected_finding_ids)
            results.append(result); validations.append(validation)
        return results, validations

    @staticmethod
    def _insufficient(packet: dict, gaps: list[str] | None = None) -> ReviewedTopicResult:
        return ReviewedTopicResult(topic_id=str(packet.get("review_topic", "unknown")), topic_name=str(packet.get("review_topic", "unknown")), reviewed_finding_ids=[], reviewed_evidence_ids=[], conclusion_nature="insufficient_evidence", consistency_status="insufficient_evidence", integrated_statement="当前主题材料不足，无法形成经过复核的结论。", evidence_gaps=list(gaps or ["主题缺少可用 Finding 或 Evidence"]), confidence="low")
