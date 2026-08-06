from ipo_financial_agent.agents.report_reviewer import EvidenceComplianceReviewerAgent
from ipo_financial_agent.models_agent import ReportReview


class InconsistentReviewerClient:
    def complete_json(self, **_: object) -> ReportReview:
        return ReportReview(
            passed=True,
            score=0,
            revision_instructions=["可选的措辞优化"],
            summary="模型返回了矛盾分数",
        )


def _complete_report() -> str:
    return """# 示例公司港股 IPO 公司尽调报告

## 公司概况、股权与商业模式
事实 [ev_12345678 | 招股书 P10]
### 公司沿革、股权与控制权
事实待核验。
### 融资、并购及重大资本事件
事实待核验。
### 产品、服务与商业模式
事实待核验。
### 客户与供应商
事实待核验。
### 研发、生产、销售、交付与回款
事实待核验。
### 子公司、经营主体与管理层
事实待核验。
## 行业与竞争
证据不足，待联网核验。
## 历史财务表现与盈利质量
### 资产负债表
| 项目 | 2024年 |
|---|---:|
| 现金 | 100 |
### 利润表
| 项目 | 2024年 |
|---|---:|
| 收入 | 200 |
### 现金流量表
| 项目 | 2024年 |
|---|---:|
| 经营现金流 | 20 |
## 未来持续盈利能力
证据不足，待核验。
## 法务、合规、治理与负面事项
证据不足，待核验。
## 跨 Agent 冲突与重大风险
暂无已验证冲突。
## 综合尽调判断
维持待核验结论。
"""


def test_deterministic_reviewer_accepts_complete_grounded_report() -> None:
    review = EvidenceComplianceReviewerAgent().review(
        company="示例公司", report=_complete_report()
    )
    assert review.passed is True
    assert review.score == 100
    assert review.missing_sections == []


def test_deterministic_reviewer_detects_missing_statement_and_scope_violation() -> None:
    report = _complete_report().replace("### 现金流量表", "### 现金收支摘要")
    report += "\n建议投资金额为 1 亿元。"
    review = EvidenceComplianceReviewerAgent().review(company="示例公司", report=report)
    assert review.passed is False
    assert "现金流量表" in review.missing_sections
    assert "建议投资金额" in review.scope_violations


def test_deterministic_reviewer_requires_traceable_citation() -> None:
    report = _complete_report().replace("[ev_12345678 | 招股书 P10]", "")
    review = EvidenceComplianceReviewerAgent().review(company="示例公司", report=report)
    assert review.passed is False
    assert review.citation_issues


def test_deterministic_reviewer_does_not_flag_scope_disclaimer() -> None:
    report = _complete_report() + "\n本报告不包含建议投资金额、估值上限或退出期限。"
    review = EvidenceComplianceReviewerAgent().review(company="示例公司", report=report)
    assert review.scope_violations == []


def test_llm_reviewer_score_is_recomputed_from_authoritative_issue_ledger() -> None:
    review = EvidenceComplianceReviewerAgent(InconsistentReviewerClient()).review(
        company="示例公司", report=_complete_report()
    )
    assert review.passed is True
    assert review.score == 97


def test_reviewer_excerpt_samples_late_sections_in_long_report() -> None:
    report = (
        "# 长报告\n\n"
        "## 一、公司概况、股权与商业模式\n"
        + "公司正文。" * 8000
        + "\n## 二、行业与竞争\n行业正文。"
        + "\n## 附录A：三大财务报表原表\n### 现金流量表\n期末现金。"
    )

    excerpt = EvidenceComplianceReviewerAgent._review_excerpt(report)

    assert len(excerpt) <= 30000
    assert "行业与竞争" in excerpt
    assert "现金流量表" in excerpt
