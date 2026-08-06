"""Standalone Legal & Governance Lite stage with fixed task and audit outputs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ipo_financial_agent.agents.legal_governance_agent import LegalGovernanceAgent
from ipo_financial_agent.config import Settings, get_settings
from ipo_financial_agent.research.entity_registry_builder import build_entity_registry
from ipo_financial_agent.research.fixed_legal_task import build_fixed_legal_task
from ipo_financial_agent.research.legal_context_builder import build_legal_context
from ipo_financial_agent.research.legal_search_planner import build_entity_search_queries
from ipo_financial_agent.schemas.legal import LegalClaim, LegalFinding, LegalProfileFact, LegalResearchTopic, LegalStageResult
from ipo_financial_agent.storage.json_store import write_json
from ipo_financial_agent.tools.search_tool import search_legal_entities
from ipo_financial_agent.validators.legal_validator import validate_legal_result

PDFLoader = None
detect_sections = None


class LegalGovernanceStage:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def run(self, *, pdf_path: str | Path, company_name: str) -> LegalStageResult:
        global PDFLoader, detect_sections
        if PDFLoader is None or detect_sections is None:
            from ipo_financial_agent.document.pdf_loader import PDFLoader as _PDFLoader
            from ipo_financial_agent.document.section_detector import detect_sections as _detect_sections
            PDFLoader, detect_sections = _PDFLoader, _detect_sections
        path = Path(pdf_path).resolve()
        job_id = self._job_id(path)
        pages = PDFLoader(path).load()
        _ = detect_sections(pages)
        task = build_fixed_legal_task()
        context = build_legal_context(company_name, pages)
        entities = build_entity_registry(company_name, pages)
        legacy = LegalGovernanceAgent().analyze(company=company_name, pages=pages)
        evidence = list(legacy.evidence)
        for item in evidence:
            if not item.evidence_id:
                item.evidence_id = "LE_" + hashlib.sha1((item.source_url or item.source or item.content).encode()).hexdigest()[:12]
        targeted_results = search_legal_entities(build_entity_search_queries(entities))
        for result in targeted_results:
            item_id = "WEB_LE_" + hashlib.sha1((result.get("url", "") + str(result.get("entity_id", ""))).encode()).hexdigest()[:12]
            from ipo_financial_agent.models_agent import Evidence
            evidence.append(Evidence(evidence_id=item_id, source_type="web", title=str(result.get("title", "")), content=str(result.get("content", ""))[:1200], source=str(result.get("url", "")), source_url=str(result.get("url", "")), published_at=result.get("published_at"), retrieved_at=result.get("retrieved_at"), confidence=float(result.get("confidence", 0.5)), metadata={"topic": str(result.get("research_topic", "")), "entity_id": result.get("entity_id"), "source_tier": result.get("source_tier", "unknown"), "content_hash": result.get("content_hash", ""), "source_scope": "external"}))
        evidence_ids = {item.evidence_id for item in evidence}
        facts: list[LegalProfileFact] = []
        claims: list[LegalClaim] = []
        findings: list[LegalFinding] = []
        for index, question in enumerate(task.questions, start=1):
            blocks = context.topic_blocks.get(question.research_topic, [])
            refs = [item.evidence_id for item in evidence if str(item.metadata.get("category", "")).lower() in question.research_topic.value]
            if not refs:
                refs = [item.evidence_id for item in evidence[:1]] if blocks and evidence else []
            facts.append(LegalProfileFact(profile_fact_id=f"LPF{index:03d}", research_topic=question.research_topic, entity_ids=[entities[0].entity_id] if entities else [], statement=(blocks[0].text[:500] if blocks else "当前审阅范围未提取到足够披露材料"), evidence_ids=refs, fact_status="prospectus_disclosed" if blocks else "unable_to_verify"))
            if blocks:
                claims.append(LegalClaim(claim_id=f"LC{index:03d}", research_topic=question.research_topic, related_entity_ids=[entities[0].entity_id] if entities else [], claim=question.question, verification_question=question.question, prospectus_evidence_ids=refs))
            external_refs = [item.evidence_id for item in evidence if item.source_type == "web" and item.metadata.get("topic") == question.research_topic.value]
            finding_refs = list(dict.fromkeys(refs + external_refs))
            findings.append(LegalFinding(finding_id=f"LGF{index:03d}", research_topic=question.research_topic, entity_ids=[entities[0].entity_id] if entities else [], statement=("已在审阅范围内定位相关披露和外部来源，仍需逐项核对主体、期间与法律状态。" if finding_refs else "当前审阅范围未取得可核验的主体法律公开资料。"), evidence_ids=finding_refs, issue_status="potential_issue" if external_refs else "unable_to_verify", cross_check_topics=( ["customer_quality", "receivable_revenue_match"] if question.research_topic == LegalResearchTopic.RELATED_PARTY else []), legal_scope_note="本 Finding 仅表示尽调核查状态，不构成法律意见。"))
        validation = validate_legal_result(task=task, entities=entities, profile_facts=facts, claims=claims, findings=findings, evidence_ids=evidence_ids)
        root = self.settings.output_dir / job_id / "stage_legal"
        root.mkdir(parents=True, exist_ok=True)
        paths = {
            "legal_task": write_json(root / "legal_task.json", task),
            "legal_context": write_json(root / "legal_context.json", context),
            "entity_registry": write_json(root / "entity_registry.json", entities),
            "legal_evidences": write_json(root / "legal_evidences.json", evidence),
            "legal_profile": write_json(root / "legal_profile.json", facts),
            "legal_claims": write_json(root / "legal_claims.json", claims),
            "legal_findings": write_json(root / "legal_findings.json", findings),
            "legal_analysis": write_json(root / "legal_analysis.json", legacy),
            "legal_validation": write_json(root / "legal_validation.json", validation),
        }
        result = LegalStageResult(job_id=job_id, pipeline_status="completed" if validation.valid else "completed_with_fallback", legal_status="completed" if validation.valid else "partial", validation=validation, paths={key: str(value) for key, value in paths.items()})
        write_json(root / "legal_stage_result.json", result)
        return result

    @staticmethod
    def _job_id(path: Path) -> str:
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:8]
        stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", path.stem).strip("_")
        return f"{stem[:48]}_{digest}"
