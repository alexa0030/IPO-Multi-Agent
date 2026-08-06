from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ipo_financial_agent.config import get_settings
from ipo_financial_agent.workflow.stage_company_pipeline import (
    ManagerFinancialReviewerCompanyStage,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Manager -> Financial -> Reviewer -> fixed Company stage"
    )
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument(
        "--company-llm-mode", choices=("off", "auto", "on"), default="auto"
    )
    args = parser.parse_args()
    result = ManagerFinancialReviewerCompanyStage(get_settings(ROOT)).run(
        pdf_path=args.pdf,
        company_name=args.company,
        company_llm_mode=args.company_llm_mode,
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
