from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ipo_financial_agent.report.report_material_builder import build_report_material_pack_v0
from ipo_financial_agent.storage.json_store import write_json


def _read(path: str | None) -> object:
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Report Material Pack v0 and coverage audit")
    parser.add_argument("--company", default="")
    parser.add_argument("--company-result")
    parser.add_argument("--financial-result")
    parser.add_argument("--industry-result")
    parser.add_argument("--legal-result")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    pack, audit = build_report_material_pack_v0(_read(args.company_result), _read(args.financial_result), _read(args.industry_result), _read(args.legal_result), company=args.company)
    write_json(output / "report_material_pack_v0.json", pack)
    write_json(output / "report_coverage_audit.json", audit)
    print(json.dumps(audit.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
