from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ipo_financial_agent.agents.report_reviewer import EvidenceComplianceReviewerAgent
from ipo_financial_agent.agents.report_writer import ReportWriterAgent
from ipo_financial_agent.config import get_settings
from ipo_financial_agent.llm.client import OpenAICompatibleClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply and validate one bounded report revision")
    parser.add_argument("--company", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = args.report.read_text(encoding="utf-8")
    review = json.loads(args.review.read_text(encoding="utf-8"))
    instructions = list(review.get("revision_instructions", []))
    client = OpenAICompatibleClient(get_settings(ROOT))
    revised = ReportWriterAgent(client).revise_diligence_draft(
        report=report,
        revision_instructions=instructions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(revised, encoding="utf-8")
    post = EvidenceComplianceReviewerAgent(client).review(
        company=args.company,
        report=revised,
    )
    summary = {
        "original_chars": len(report),
        "revised_chars": len(revised),
        "changed": revised != report,
        "score": post.score,
        "passed": post.passed,
        "revision_items": len(post.revision_instructions),
        "output": str(args.output),
    }
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
