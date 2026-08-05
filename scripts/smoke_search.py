"""Small connectivity check for the configured public-information provider."""

from __future__ import annotations

import argparse

from ipo_financial_agent.tools.search_tool import search_industry_info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("company")
    parser.add_argument("--business", default="")
    args = parser.parse_args()
    results = search_industry_info(args.company, args.business)
    print(f"results={len(results)}")
    for item in results:
        print(f"[{item.get('topic')}] {item.get('url')}")


if __name__ == "__main__":
    main()
