from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ipo_financial_agent.config import get_settings
from ipo_financial_agent.workflow.stage_legal import LegalGovernanceStage

def main() -> None:
    parser = argparse.ArgumentParser(description="Run fixed Legal & Governance Lite stage")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--company", required=True)
    args = parser.parse_args()
    result = LegalGovernanceStage(get_settings(ROOT)).run(pdf_path=args.pdf, company_name=args.company)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
