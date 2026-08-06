from __future__ import annotations
from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.schemas.report_sections import ReportSectionMaterial

SECTION_WRITER_SYSTEM_PROMPT = """你是IPO尽调报告章节编辑。只能使用当前章节材料和确定性基础文本生成分析说明，不得新增数字、主体、案件、竞争对手或外部事实。财务数字必须原样引用；必须保留正面、负面和证据不足。不要生成表格，不要修改Finding或Evidence ID。"""

class QwenSectionWriter:
    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def generate_analysis(self, material: ReportSectionMaterial, base_markdown: str) -> str:
        if self.client is None:
            return ""
        prompt = f"章节：{material.title}\n确定性基础文本：\n{base_markdown}\n当前章节允许材料：\n{material.model_dump(mode='json')}\n请只返回分析说明正文。"
        return self.client.complete_text(system_prompt=SECTION_WRITER_SYSTEM_PROMPT, user_prompt=prompt, max_tokens=1800)
