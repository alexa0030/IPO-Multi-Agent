from __future__ import annotations

import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ipo_financial_agent.report.report_material_builder import build_report_material_pack_v0
from ipo_financial_agent.reviewers.coverage_gate import evaluate_coverage_gate
from ipo_financial_agent.reviewers.final_review_packets import build_final_review_input, build_topic_review_packets, validate_topic_packets
from ipo_financial_agent.storage.json_store import write_json

def read(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def main() -> None:
    parser = argparse.ArgumentParser(description="Coverage gate and deterministic Final Reviewer packet preparation")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    gate = evaluate_coverage_gate(read(args.audit))
    write_json(output / "coverage_gate.json", gate)
    if not gate.allowed:
        print(json.dumps(gate.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    review_input = build_final_review_input(read(args.pack))
    packets = build_topic_review_packets(review_input)
    validation = validate_topic_packets(packets, review_input)
    write_json(output / "final_review_input.json", review_input)
    write_json(output / "review_topic_candidates.json", [{"review_topic": item.review_topic, "review_question": item.review_question, "finding_ids": item.finding_ids} for item in packets])
    write_json(output / "topic_review_packets.json", packets)
    write_json(output / "topic_packet_validation.json", validation)
    print(json.dumps({"gate": gate.model_dump(mode="json"), "packet_validation": validation.model_dump(mode="json")}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
