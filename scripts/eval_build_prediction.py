from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipo_financial_agent.evaluation.prediction_builder import build_prediction


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an eval prediction from pipeline artifacts")
    parser.add_argument("--extracted-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_prediction(args.extracted_dir), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output.resolve())


if __name__ == "__main__":
    main()
