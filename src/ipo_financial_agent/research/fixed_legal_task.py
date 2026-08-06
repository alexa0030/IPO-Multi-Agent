from ipo_financial_agent.schemas.legal import (
    LegalResearchQuestion, LegalResearchTask, LegalResearchTopic,
)


def build_fixed_legal_task() -> LegalResearchTask:
    specs = [
        ("LG_Q001", LegalResearchTopic.OWNERSHIP_CONTROL, "主要股东、控股股东和实际控制人结构是否清晰，是否存在特殊安排？", "P0", ["股权结构", "实际控制人", "一致行动或特殊权利"]),
        ("LG_Q002", LegalResearchTopic.SUBSIDIARY_STRUCTURE, "主要子公司的持股关系、法律状态和集团控制是否清晰？", "P0", ["子公司清单", "持股比例", "注册地和经营职能"]),
        ("LG_Q003", LegalResearchTopic.RELATED_PARTY, "是否存在影响业务独立性的关联方、关联交易或同业竞争？", "P0", ["关联方清单", "关联交易", "同业竞争安排"]),
        ("LG_Q004", LegalResearchTopic.LITIGATION_PENALTY, "公司、实际控制人及核心子公司是否存在重大诉讼、处罚、执行或失信事项？", "P0", ["诉讼处罚披露", "法院或监管原文", "案件进展和整改"]),
        ("LG_Q005", LegalResearchTopic.LICENSE_IP, "核心业务所需许可、专利、商标及第三方授权是否存在重大缺口？", "P1", ["核心许可证", "专利商标", "授权有效期"]),
        ("LG_Q006", LegalResearchTopic.GOVERNANCE_INTERNAL_CONTROL, "审计、内控、担保、资金占用或治理方面是否存在明显红旗？", "P1", ["审计意见", "内控缺陷", "对外担保和资金占用"]),
    ]
    return LegalResearchTask(
        task_id="TASK_LEGAL_FIXED_001",
        objective="核查公司控制结构、子公司、关联关系、重大诉讼处罚及核心资质，不作法律意见。",
        questions=[LegalResearchQuestion(question_id=qid, research_topic=topic, question=q, priority=priority, expected_evidence=evidence) for qid, topic, q, priority, evidence in specs],
    )
