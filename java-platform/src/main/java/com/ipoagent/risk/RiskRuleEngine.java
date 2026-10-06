package com.ipoagent.risk;

import com.ipoagent.domain.MetricResult;
import com.ipoagent.domain.RiskFinding;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class RiskRuleEngine {

    public List<RiskFinding> scan(List<MetricResult> metrics) {
        Map<String, MetricResult> index = new LinkedHashMap<>();
        metrics.forEach(metric -> index.put(key(metric.metricCode(), metric.period()), metric));
        List<String> periods = metrics.stream().map(MetricResult::period).distinct().sorted().toList();
        List<RiskFinding> findings = new ArrayList<>();

        for (String period : periods) {
            compareGrowth(findings, index, period, "receivable_growth", "receivable_vs_revenue",
                    "收入质量", "应收账款增速明显高于收入增速");
            compareGrowth(findings, index, period, "inventory_growth", "inventory_vs_revenue",
                    "资产质量", "存货增速明显高于收入增速");

            MetricResult cash = index.get(key("ocf_to_net_profit", period));
            if (cash != null && cash.value() < 0.8) {
                findings.add(finding("weak_cash_conversion", period, "现金流", "经营现金流对净利润覆盖偏弱",
                        cash.value() < 0.5 ? "high" : "medium", "净现比为" + cash.displayValue()
                                + "，需结合应收、存货及一次性项目核实利润含金量。", List.of(cash)));
            }

            MetricResult current = index.get(key("current_ratio", period));
            if (current != null && current.value() < 1.2) {
                findings.add(finding("low_current_ratio", period, "流动性", "流动比率偏低",
                        current.value() < 1.0 ? "high" : "medium", "流动比率为" + current.displayValue()
                                + "，需关注短期偿债安排和可动用现金。", List.of(current)));
            }

            MetricResult debt = index.get(key("debt_ratio", period));
            if (debt != null && debt.value() > 0.65) {
                findings.add(finding("high_debt_ratio", period, "偿债能力", "资产负债率较高",
                        debt.value() > 0.8 ? "high" : "medium", "资产负债率为" + debt.displayValue()
                                + "，需核实有息负债、担保、到期结构及利息负担。", List.of(debt)));
            }
        }

        List<MetricResult> margins = metrics.stream()
                .filter(metric -> metric.metricCode().equals("gross_margin"))
                .sorted(Comparator.comparing(MetricResult::period)).toList();
        if (margins.size() >= 3) {
            List<MetricResult> latest = margins.subList(margins.size() - 3, margins.size());
            if (latest.get(0).value() > latest.get(1).value()
                    && latest.get(1).value() > latest.get(2).value()) {
                MetricResult ending = latest.get(2);
                findings.add(finding("gross_margin_decline", ending.period(), "盈利能力", "毛利率连续下降",
                        ending.value() >= 0.30 ? "low" : "medium",
                        "最近三个期间毛利率依次为" + latest.get(0).displayValue() + "、"
                                + latest.get(1).displayValue() + "、" + ending.displayValue()
                                + "；该命中是待解释观察项，不直接等同于盈利能力恶化。", latest));
            }
        }
        return List.copyOf(findings);
    }

    private void compareGrowth(List<RiskFinding> output, Map<String, MetricResult> index, String period,
                               String growthCode, String ruleCode, String category, String title) {
        MetricResult revenue = index.get(key("revenue_growth", period));
        MetricResult compared = index.get(key(growthCode, period));
        if (revenue != null && compared != null && compared.value() - revenue.value() >= 0.20) {
            output.add(finding(ruleCode, period, category, title, "medium",
                    compared.displayValue() + "，收入增速为" + revenue.displayValue()
                            + "，需结合业务变化和明细证据进一步核实。", List.of(compared, revenue)));
        }
    }

    private RiskFinding finding(String code, String period, String category, String title,
                                String severity, String description, List<MetricResult> evidence) {
        return new RiskFinding(code, period, category, title, severity, "observation", description,
                evidence.stream().map(MetricResult::metricCode).distinct().toList(),
                evidence.stream().flatMap(metric -> metric.sourcePages().stream()).distinct().sorted().toList());
    }

    private String key(String code, String period) {
        return code + "|" + period;
    }
}
