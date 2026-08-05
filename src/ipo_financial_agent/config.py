from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=False)


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    upload_dir: Path
    extracted_dir: Path
    output_dir: Path
    db_dir: Path
    db_path: Path

    llm_api_key: str | None
    llm_base_url: str | None
    llm_model: str | None
    llm_temperature: float
    llm_timeout_seconds: float
    llm_max_retries: int

    parse_chunk_max_chars: int
    parse_chunk_overlap_pages: int
    candidate_context_pages: int

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)


def get_settings(project_root: str | Path | None = None) -> Settings:
    root = Path(project_root or os.getenv("IPO_PROJECT_ROOT") or Path.cwd()).resolve()
    data_dir = root / "data"
    upload_dir = data_dir / "uploads"
    extracted_dir = data_dir / "extracted"
    output_dir = data_dir / "output"
    db_dir = data_dir / "db"

    for directory in (data_dir, upload_dir, extracted_dir, output_dir, db_dir):
        directory.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_COMPATIBLE_MODEL") or os.getenv("OPENAI_MODEL")

    return Settings(
        project_root=root,
        data_dir=data_dir,
        upload_dir=upload_dir,
        extracted_dir=extracted_dir,
        output_dir=output_dir,
        db_dir=db_dir,
        db_path=db_dir / "ipo_financial_agent.sqlite3",
        llm_api_key=api_key,
        llm_base_url=base_url,
        llm_model=model,
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        llm_max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        parse_chunk_max_chars=int(os.getenv("PARSE_CHUNK_MAX_CHARS", "45000")),
        parse_chunk_overlap_pages=int(os.getenv("PARSE_CHUNK_OVERLAP_PAGES", "1")),
        candidate_context_pages=int(os.getenv("CANDIDATE_CONTEXT_PAGES", "1")),
    )
