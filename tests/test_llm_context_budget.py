from __future__ import annotations

from pathlib import Path

import pytest

from ipo_financial_agent.config import Settings
from ipo_financial_agent.llm.client import LLMTruncatedError, OpenAICompatibleClient


def _client(window: int) -> OpenAICompatibleClient:
    client = object.__new__(OpenAICompatibleClient)
    client.settings = Settings(
        project_root=Path("."), data_dir=Path("data"), upload_dir=Path("data/uploads"),
        extracted_dir=Path("data/extracted"), output_dir=Path("data/output"),
        db_dir=Path("data/db"), db_path=Path("data/db/test.sqlite3"),
        llm_api_key="test", llm_base_url="http://localhost/v1", llm_model="test",
        llm_temperature=0.1, llm_timeout_seconds=10, llm_max_retries=1,
        llm_context_window_tokens=window, llm_context_safety_tokens=128,
        parse_chunk_max_chars=45000, parse_chunk_overlap_pages=1,
        candidate_context_pages=1,
    )
    return client


def test_output_budget_is_clamped_before_provider_rejects_request() -> None:
    fitted = _client(2048)._fit_output_budget(max_tokens=1800, parts=["a" * 2000])
    assert 256 <= fitted < 1800


def test_oversized_prompt_raises_split_compatible_error() -> None:
    with pytest.raises(LLMTruncatedError, match="context budget exceeded"):
        _client(1024)._fit_output_budget(max_tokens=500, parts=["中" * 1200])
