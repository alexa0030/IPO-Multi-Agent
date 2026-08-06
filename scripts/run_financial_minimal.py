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
from ipo_financial_agent.workflow.financial_minimal import FinancialMinimalClosure


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PRD v2 Financial-only closure")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--company", required=True)
    parser.add_argument("--llm-mode", choices=["off", "auto", "on"], default="off")
    args = parser.parse_args()
    result = FinancialMinimalClosure(get_settings(ROOT)).run(
        pdf_path=args.pdf,
        company_name=args.company,
        llm_mode=args.llm_mode,
    )
    serializable = dict(result)
    serializable["review_result"] = result["review_result"].model_dump()
    print(json.dumps(serializable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
