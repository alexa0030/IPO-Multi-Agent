from ipo_financial_agent.schemas import ResearchQuestion, ResearchTask


def build_fixed_financial_task() -> ResearchTask:
    """Return the deterministic Financial-only task used before Manager integration."""
    return ResearchTask(
        task_id="TASK_FA_001",
        target_agent="financial",
        objective="验证公司的盈利质量、资产质量和现金流质量",
        questions=[
            ResearchQuestion(
                question_id="FA_Q001",
                question="利润增长是否能够转化为经营现金流？",
                reason="净利润增长不一定代表实际现金创造能力。",
                priority="P0",
                expected_evidence=["净利润", "经营活动现金流", "经营现金流与净利润比率"],
                research_topic="profit_cash_conversion",
                completion_criteria=["存在净现比计算证据", "形成利润现金转化判断"],
            ),
            ResearchQuestion(
                question_id="FA_Q002",
                question="应收账款增长是否与收入增长匹配？",
                reason="识别收入质量和回款风险。",
                priority="P0",
                expected_evidence=["营业收入", "应收账款", "应收账款增长率", "收入增长率"],
                research_topic="receivable_revenue_match",
                completion_criteria=["存在收入和应收账款增长率计算证据", "形成增速匹配判断"],
            ),
            ResearchQuestion(
                question_id="FA_Q003",
                question="存货增长是否与收入增长匹配？",
                reason="识别资产积压和跌价风险。",
                priority="P0",
                expected_evidence=["营业收入", "存货", "存货增长率", "收入增长率"],
                research_topic="inventory_revenue_match",
                completion_criteria=["存在收入和存货增长率计算证据", "形成增速匹配判断"],
            ),
        ],
        pdf_topics=["财务资料", "贸易应收款项", "存货", "现金流量表"],
        web_topics=[],
        completion_criteria=[
            "生成核心财务指标",
            "每条异常都引用Evidence",
            "中高风险异常包含可能解释和补证要求",
        ],
    )
