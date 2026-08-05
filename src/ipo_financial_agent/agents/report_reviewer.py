"""Final evidence and scope reviewer for the generated due-diligence report."""

from __future__ import annotations

import re

from ipo_financial_agent.llm.client import OpenAICompatibleClient
from ipo_financial_agent.models_agent import ReportReview


REQUIRED_SECTIONS = (
    "公司概况、股权与商业模式",
    "行业与竞争",
    "历史财务表现与盈利质量",
    "未来持续盈利能力",
    "法务、合规、治理与负面事项",
    "跨 Agent 冲突与重大风险",
    "综合尽调判断",
)

REQUIRED_FINANCIAL_STATEMENTS = (
    "资产负债表",
    "利润表",
    "现金流量表",
)

FORBIDDEN_SCOPE = (
    "建议投资金额",
    "投资金额为",
    "估值上限",
    "退出期限",
    "目标收益率",
)


class EvidenceComplianceReviewerAgent:
    """Review the writer's output without repeating specialist research."""

    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client

    def review(self, *, company: str, report: str) -> ReportReview:
        deterministic = self._deterministic_review(report)
        if self.client is None:
            return deterministic
        prompt = f"""你是港股 IPO 尽调报告终审，不重新研究公司，只审查现有报告。
公司：{company}

检查：
1. 公司股权与业务、行业竞争、财务、未来盈利、负面风险是否完整；
2. 重要事实是否带招股书页码、Evidence ID 或真实 URL；
3. 是否把发行人自述当作外部事实；
4. 是否出现无依据的数字、主体关系或绝对化结论；
5. 是否越界给出投资金额、估值上限、退出期限或收益率。

只返回 ReportReview JSON。revision_instructions 必须可执行、简短；不要重写报告。

待审报告：
{report[:30000]}
"""
        try:
            reviewed = self.client.complete_json(
                system_prompt="你是严谨的投资机构报告终审与证据审计员。",
                user_prompt=prompt,
                response_model=ReportReview,
                max_tokens=1800,
            )
        except Exception as error:
            deterministic.summary = (
                f"LLM 终审不可用，已完成确定性检查：{type(error).__name__}"
            )
            return deterministic

        reviewed.missing_sections = list(
            dict.fromkeys([*deterministic.missing_sections, *reviewed.missing_sections])
        )
        reviewed.scope_violations = list(
            dict.fromkeys([*deterministic.scope_violations, *reviewed.scope_violations])
        )
        reviewed.citation_issues = list(
            dict.fromkeys([*deterministic.citation_issues, *reviewed.citation_issues])
        )
        reviewed.revision_instructions = list(
            dict.fromkeys(
                [*deterministic.revision_instructions, *reviewed.revision_instructions]
            )
        )
        reviewed.passed = not (
            reviewed.missing_sections
            or reviewed.scope_violations
            or reviewed.unsupported_claims
            or reviewed.citation_issues
        )
        # The model may return internally inconsistent values (for example,
        # passed=true with score=0).  The issue ledger is authoritative.
        reviewed.score = max(
            0,
            100
            - 10 * len(reviewed.missing_sections)
            - 15 * len(reviewed.scope_violations)
            - 15 * len(reviewed.unsupported_claims)
            - 20 * len(reviewed.citation_issues)
            - min(20, 3 * len(reviewed.revision_instructions)),
        )
        return reviewed

    @staticmethod
    def _deterministic_review(report: str) -> ReportReview:
        missing = [
            section
            for section in (*REQUIRED_SECTIONS, *REQUIRED_FINANCIAL_STATEMENTS)
            if section not in report
        ]
        scope: list[str] = []
        for phrase in FORBIDDEN_SCOPE:
            for match in re.finditer(re.escape(phrase), report):
                sentence_start = max(
                    report.rfind(separator, 0, match.start())
                    for separator in ("\n", "。", "；", "!", "！")
                )
                sentence_end_candidates = [
                    position
                    for separator in ("\n", "。", "；", "!", "！")
                    if (position := report.find(separator, match.end())) >= 0
                ]
                sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(report)
                sentence = report[sentence_start + 1 : sentence_end]
                prohibition = ("不包含", "不提供", "不给出", "不得", "禁止", "不建议", "未给出")
                if any(marker in sentence for marker in prohibition):
                    continue
                scope.append(phrase)
                break
        citation_count = len(
            re.findall(r"ev_[0-9a-f]{8,}|招股书\s*P\d+|https?://", report)
        )
        citation_issues = [] if citation_count else ["报告没有可识别的页码、Evidence ID 或 URL 引用。"]
        instructions = [f"补齐章节：{item}" for item in missing]
        instructions.extend(f"删除越界内容：{item}" for item in scope)
        instructions.extend(citation_issues)
        score = max(0, 100 - 10 * len(missing) - 15 * len(scope) - 20 * len(citation_issues))
        passed = not (missing or scope or citation_issues)
        return ReportReview(
            passed=passed,
            score=score,
            missing_sections=missing,
            citation_issues=citation_issues,
            scope_violations=scope,
            revision_instructions=instructions,
            summary=(
                "确定性终审通过。" if passed else "确定性终审发现需修订事项。"
            ),
        )
