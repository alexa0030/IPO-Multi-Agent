from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipo_financial_agent.evaluation.candidate_builder import build_candidates
from ipo_financial_agent.evaluation.io import load_case


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic IPO eval candidates")
    parser.add_argument("--case", required=True)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = build_candidates(load_case(args.case), args.pdf)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
