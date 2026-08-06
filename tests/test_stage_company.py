from __future__ import annotations

from pathlib import Path
import shutil

from ipo_financial_agent.models_agent import (
    CompanyBusinessDossier,
    CompanyDossierFinding,
    Evidence,
    ProspectusAnalysis,
)
from ipo_financial_agent.config import get_settings
from ipo_financial_agent.workflow.stage_company import CompanyBusinessStage


class _FakeProspectusAgent:
    def __init__(self, client=None) -> None:
        self.client = client

    def analyze(self, *, company: str, pages, section_hits=None):  # noqa: D401
        evidence = Evidence(
            source_type="prospectus",
            page_number=12,
            source_file="sample.pdf",
            content="The company sells industrial control systems.",
        )
        return ProspectusAnalysis(
            company=company,
            business_model="The company sells industrial control systems.",
            business_model_evidence=[evidence],
            dossier=CompanyBusinessDossier(
                company=company,
                topic_findings={
                    "products_business_model": [
                        CompanyDossierFinding(
                            topic="products_business_model",
                            statement="The company sells industrial control systems.",
                            evidence=[evidence],
                        )
                    ]
                },
                open_questions=["核实核心产品的客户结构。"],
            ),
        )


class _FakePDFLoader:
    def __init__(self, path) -> None:
        self.path = path

    def load(self):
        return []


class _FakeTopicPageSelector:
    def __init__(self, pages_per_topic: int, context_pages: int) -> None:
        self.pages_per_topic = pages_per_topic
        self.context_pages = context_pages

    def select_groups(self, pages, section_hits):
        return {}


def test_company_stage_writes_auditable_outputs(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / "work" / "stage_company_test"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    pdf = root / "example.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF")
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company.ProspectusAgent",
        _FakeProspectusAgent,
    )
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company.PDFLoader", _FakePDFLoader, raising=False
    )
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company.detect_sections",
        lambda pages: [],
        raising=False,
    )
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company.TopicPageSelector",
        _FakeTopicPageSelector,
        raising=False,
    )
    stage = CompanyBusinessStage(get_settings(root))

    result = stage.run(pdf_path=pdf, company_name="Example Holdings", llm_mode="off")

    assert result["output_status"] == "completed"
    assert result["finding_count"] >= 1
    assert result["evidence_count"] == 1

    company_dir = stage.settings.output_dir / result["job_id"] / "stage_company"
    assert (company_dir / "company_task.json").exists()
    assert (company_dir / "company_analysis.json").exists()
    assert (company_dir / "company_evidences.json").exists()
    assert (company_dir / "company_findings.json").exists()
    assert (company_dir / "company_open_questions.json").exists()


def test_company_auto_mode_falls_back_when_llm_is_unavailable(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1] / "work" / "stage_company_auto_test"
    root.mkdir(parents=True, exist_ok=True)
    pdf = root / "example.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF")
    calls: list[object | None] = []

    class _FlakyAgent(_FakeProspectusAgent):
        def analyze(self, *, company: str, pages, section_hits=None):
            calls.append(self.client)
            if self.client is not None:
                raise ConnectionError("model endpoint unavailable")
            return super().analyze(company=company, pages=pages, section_hits=section_hits)

    monkeypatch.setattr("ipo_financial_agent.workflow.stage_company.ProspectusAgent", _FlakyAgent)
    monkeypatch.setattr("ipo_financial_agent.workflow.stage_company.PDFLoader", _FakePDFLoader)
    monkeypatch.setattr("ipo_financial_agent.workflow.stage_company.detect_sections", lambda pages: [])
    monkeypatch.setattr(
        "ipo_financial_agent.workflow.stage_company.TopicPageSelector", _FakeTopicPageSelector
    )
    stage = CompanyBusinessStage(get_settings(root))
    configured_client = object()
    monkeypatch.setattr(stage, "_client", lambda mode: configured_client)

    result = stage.run(pdf_path=pdf, company_name="Example Holdings", llm_mode="auto")

    assert result["output_status"] == "completed"
    assert calls == [configured_client, None]
