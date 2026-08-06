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
from ipo_financial_agent.workflow.stage_reviewer import ReviewerStage


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Manager -> Financial -> Reviewer")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--company", required=True)
    args = parser.parse_args()
    result = ReviewerStage(get_settings(ROOT)).run(
        pdf_path=args.pdf, company_name=args.company
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
