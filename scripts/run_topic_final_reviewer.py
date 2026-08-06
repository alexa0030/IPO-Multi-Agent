from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from ipo_financial_agent.config import get_settings
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.review.topic_reviewer import TopicReviewer
from ipo_financial_agent.schemas.final_reviewer import TopicReviewPacket
from ipo_financial_agent.storage.json_store import write_json

def main() -> None:
    parser=argparse.ArgumentParser(description="Run Qwen topic-by-topic Final Reviewer")
    parser.add_argument("--packets",required=True); parser.add_argument("--output-dir",required=True); parser.add_argument("--llm-mode",choices=("on","off"),default="on")
    args=parser.parse_args(); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    packets=[TopicReviewPacket.model_validate(item) for item in json.loads(Path(args.packets).read_text(encoding="utf-8"))]
    client=OpenAICompatibleClient(get_settings(ROOT)) if args.llm_mode=="on" else None
    results, validations=TopicReviewer(client).run(packets)
    write_json(out/"topic_review_results.json",results); write_json(out/"topic_review_validation.json",validations)
    print(json.dumps({"result_count":len(results),"valid_count":sum(item.valid for item in validations)},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
