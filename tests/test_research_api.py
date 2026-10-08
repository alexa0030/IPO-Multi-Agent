from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ipo_financial_agent.api.app import create_app
from ipo_financial_agent.api.job_service import InMemoryJobService


class SuccessfulRunner:
    def __init__(self, report_path: Path) -> None:
        self.report_path = report_path
        self.calls: list[dict[str, object]] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        self.report_path.write_text("# 可追溯尽调报告\n\n测试结论。", encoding="utf-8")
        return SimpleNamespace(final_report_path=str(self.report_path), report_path=None)


class FailingRunner:
    def run(self, **kwargs):
        raise TimeoutError("model timed out")


def _client(tmp_path: Path, runner) -> tuple[TestClient, InMemoryJobService]:
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    service = InMemoryJobService(upload_dir, runner=runner)
    return TestClient(create_app(service)), service


def _upload(client: TestClient) -> str:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("issuer.pdf", b"%PDF-1.7\nmock", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()["document_id"]


def test_upload_create_status_and_report_flow(tmp_path: Path):
    runner = SuccessfulRunner(tmp_path / "report.md")
    client, _ = _client(tmp_path, runner)
    document_id = _upload(client)

    created = client.post(
        "/api/v1/jobs",
        json={"document_id": document_id, "company": "示例公司", "llm_mode": "off"},
    )

    assert created.status_code == 202
    job_id = created.json()["job_id"]
    status_response = client.get(f"/api/v1/jobs/{job_id}")
    assert status_response.json()["status"] == "completed"
    assert runner.calls[0]["company"] == "示例公司"
    report = client.get(f"/api/v1/jobs/{job_id}/report")
    assert report.status_code == 200
    assert "可追溯尽调报告" in report.json()["markdown"]


def test_invalid_upload_and_missing_resources_return_explicit_errors(tmp_path: Path):
    client, _ = _client(tmp_path, SuccessfulRunner(tmp_path / "report.md"))

    invalid = client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", b"not-a-pdf", "application/pdf")},
    )
    missing_document = client.post(
        "/api/v1/jobs",
        json={"document_id": "a" * 64, "company": "示例公司", "llm_mode": "off"},
    )
    missing_job = client.get("/api/v1/jobs/does-not-exist")

    assert invalid.status_code == 422
    assert missing_document.status_code == 404
    assert missing_job.status_code == 404


def test_pipeline_timeout_is_captured_as_failed_job(tmp_path: Path):
    client, _ = _client(tmp_path, FailingRunner())
    document_id = _upload(client)

    created = client.post(
        "/api/v1/jobs",
        json={"document_id": document_id, "company": "示例公司", "llm_mode": "on"},
    )
    job_id = created.json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()

    assert job["status"] == "failed"
    assert job["error_code"] == "TimeoutError"
    assert "timed out" in job["error_message"]
    assert client.get(f"/api/v1/jobs/{job_id}/report").status_code == 409
