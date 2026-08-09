from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipo_financial_agent.evaluation.io import load_case, load_json
from ipo_financial_agent.evaluation.scorer import score_prediction


def main() -> None:
    parser = argparse.ArgumentParser(description="Score one IPO evaluation prediction")
    parser.add_argument("--case", required=True)
    parser.add_argument("--prediction", required=True)
    args = parser.parse_args()
    score = score_prediction(load_case(args.case), load_json(args.prediction))
    print(json.dumps(score.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
