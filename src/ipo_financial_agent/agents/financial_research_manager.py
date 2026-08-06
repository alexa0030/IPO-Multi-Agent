from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.schemas import ManagerContext, ResearchPlan


SYSTEM_PROMPT = """你是港股IPO尽调项目的Research Manager。你当前只负责为Financial Agent
制定一个公司特定的财务研究任务，不执行财务分析，不撰写投资结论，不生成其他Agent任务。
你可以原样引用只读financial_summary中的数字，但不得创造、修改、重新计算或回写任何数字。
法证规则命中仅是观察项，不得直接定性为造假、违规或重大风险。"""


@dataclass(frozen=True)
class ManagerPlanAttempt:
    plan: ResearchPlan | None
    raw_response: str
    parse_error: str | None = None


def _extract_json(text: str) -> dict:
    value = text.strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型响应不包含JSON对象")
        payload = json.loads(value[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("模型响应必须是JSON对象")
    return payload


class FinancialResearchManager:
    def __init__(self, client: OpenAICompatibleClient) -> None:
        self.client = client

    def plan(self, context: ManagerContext) -> ManagerPlanAttempt:
        response_schema = ResearchPlan.model_json_schema()
        response_schema["properties"]["tasks"]["maxItems"] = 1
        task_schema = response_schema["$defs"]["ResearchTask"]["properties"]
        task_schema["questions"]["minItems"] = 4
        task_schema["questions"]["maxItems"] = 8
        task_schema["web_topics"]["maxItems"] = 0
        schema = json.dumps(response_schema, ensure_ascii=False)
        prompt = f"""请生成ResearchPlan JSON。严格要求：
1. tasks恰好一个且target_agent=financial；任务内部包含多个问题；web_topics必须是空数组[]。
2. 必须创建三个彼此独立且priority=P0的问题，research_topic分别且明确等于：
profit_cash_conversion、receivable_revenue_match、inventory_revenue_match。
不得把应收问题合并到现金流问题中，也不得漏掉其中任何一个。
3. P0问题3至5个，总问题不超过8个，公司特定问题不超过3个。
4. 必须根据输入增加1至3个公司特定问题，可选gross_margin_quality、debt_liquidity、
earnings_sustainability、selling_expense_quality、revenue_tax_consistency或cash_flow_quality；
只选择现有摘要支持且Financial Agent已有观察项或指标的主题。
5. question_id唯一；每题均有reason、expected_evidence、completion_criteria。
6. 不得输出完整报告或计算结果；问题中的数字只能原样引用输入。
7. 不得生成联网、外部公告、同行数据或其他Agent证据要求；只使用招股书财务披露与确定性计算。
8. 不得使用造假、违规、违法、虚构、少缴、粉饰等未经核实的负面定性措辞。
9. expected_evidence和completion_criteria都必须是非空数组。
10. 只能要求Financial Agent使用已有能力：净现比；收入、应收账款和存货增长率；毛利率；
销售费用率；收入与已付所得税增长背离。不得要求新计算周转率、周转天数、资产负债率、
占收入比例、绝对差额或影响金额。

JSON Schema：{schema}

只读输入：{context.model_dump_json()}"""
        raw = ""
        try:
            if hasattr(self.client, "client") and hasattr(self.client, "settings"):
                def request():
                    return self.client.client.chat.completions.create(
                        model=str(self.client.settings.llm_model),
                        temperature=0.0,
                        top_p=1.0,
                        max_tokens=3000,
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "ResearchPlan",
                                "strict": True,
                                "schema": response_schema,
                            },
                        },
                        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    )
                response = self.client._with_retry(request)
                raw = response.choices[0].message.content or ""
            else:
                raw = self.client.complete_text(
                    system_prompt=SYSTEM_PROMPT, user_prompt=prompt, max_tokens=3000
                )
            return ManagerPlanAttempt(
                plan=ResearchPlan.model_validate(_extract_json(raw)), raw_response=raw
            )
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            return ManagerPlanAttempt(plan=None, raw_response=raw, parse_error=str(exc))
