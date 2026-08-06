from __future__ import annotations

from collections import defaultdict
from ipo_financial_agent.schemas.legal import LegalResearchTopic, LegalSeedContext, LegalSourceBlock

ROUTES = {
    LegalResearchTopic.OWNERSHIP_CONTROL: ("股东", "控股", "实际控制", "股权", "一致行动"),
    LegalResearchTopic.SUBSIDIARY_STRUCTURE: ("子公司", "附属公司", "持股比例", "注册成立", "集团"),
    LegalResearchTopic.RELATED_PARTY: ("关联方", "关联交易", "同业竞争", "担保", "资金往来"),
    LegalResearchTopic.LITIGATION_PENALTY: ("诉讼", "仲裁", "处罚", "执行", "失信", "纠纷"),
    LegalResearchTopic.LICENSE_IP: ("许可证", "许可", "专利", "商标", "授权", "知识产权"),
    LegalResearchTopic.GOVERNANCE_INTERNAL_CONTROL: ("内控", "审计", "担保", "资金占用", "整改", "董事"),
}


def build_legal_context(company_name: str, pages: list[object], *, max_blocks: int = 12) -> LegalSeedContext:
    grouped: dict[LegalResearchTopic, list[LegalSourceBlock]] = defaultdict(list)
    for page in pages:
        number = int(getattr(page, "page", 0) or 0)
        text = str(getattr(page, "text", "") or "").strip()
        if number < 1 or len(text) < 80:
            continue
        for topic, keywords in ROUTES.items():
            if len(grouped[topic]) >= max_blocks:
                continue
            if any(keyword in text for keyword in keywords):
                grouped[topic].append(LegalSourceBlock(block_id=f"PDF_LE_{number}_{topic.value}", page_number=number, text=text[:1800]))
    return LegalSeedContext(company_name=company_name, topic_blocks=dict(grouped))
