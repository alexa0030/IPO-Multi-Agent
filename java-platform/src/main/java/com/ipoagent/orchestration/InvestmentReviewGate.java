package com.ipoagent.orchestration;

import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.RiskFinding;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class InvestmentReviewGate {

    public List<ResearchChallenge> review(List<RiskFinding> findings) {
        List<ResearchChallenge> challenges = new ArrayList<>();
        for (RiskFinding finding : findings) {
            if ("low".equals(finding.severity())) continue;
            challenges.add(new ResearchChallenge(
                    "challenge:" + finding.period() + ":" + finding.ruleCode(),
                    finding.ruleCode(),
                    questionFor(finding.ruleCode()),
                    requiredEvidenceFor(finding.ruleCode()),
                    "open"
            ));
        }
        return List.copyOf(challenges);
    }

    private String questionFor(String ruleCode) {
        return switch (ruleCode) {
            case "weak_cash_conversion" -> "现金转化偏弱能否由营运资金投入或一次性事项解释？";
            case "receivable_vs_revenue" -> "应收增长是否由信用政策、客户结构或并购口径变化解释？";
            case "inventory_vs_revenue" -> "存货增长是否有订单、库龄和期后销售证据支持？";
            case "low_current_ratio" -> "未来十二个月的现金、授信和债务到期安排是否充分？";
            case "high_debt_ratio" -> "高负债是否包含受限资金、担保或集中到期风险？";
            default -> "该规则观察是否有充分的业务解释和反证？";
        };
    }

    private List<String> requiredEvidenceFor(String ruleCode) {
        return switch (ruleCode) {
            case "weak_cash_conversion" -> List.of("现金流变动桥接", "应收及存货变化", "一次性事项");
            case "receivable_vs_revenue" -> List.of("账龄", "期后回款", "信用政策变化");
            case "inventory_vs_revenue" -> List.of("存货库龄", "跌价准备", "期后销售");
            case "low_current_ratio" -> List.of("债务到期表", "可用授信", "受限现金");
            case "high_debt_ratio" -> List.of("有息负债明细", "利息覆盖", "担保及契约条款");
            default -> List.of("管理层解释", "可核验原始证据");
        };
    }
}
