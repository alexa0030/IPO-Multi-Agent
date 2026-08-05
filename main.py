from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ipo_financial_agent.config import get_settings
from ipo_financial_agent.pipeline import IPOFinancialPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="港股IPO招股书财务解析与分析")
    parser.add_argument("--pdf", required=True, help="招股书PDF路径")
    parser.add_argument("--company", required=True, help="公司名称")
    parser.add_argument(
        "--llm-mode",
        choices=["auto", "on", "off"],
        default="auto",
        help="auto=有配置则调用；on=强制调用；off=不调用",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings(Path(__file__).resolve().parent)
    artifacts = IPOFinancialPipeline(settings).run(
        pdf_path=args.pdf,
        company=args.company,
        llm_mode=args.llm_mode,
    )
    print(artifacts.model_dump_json(ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
