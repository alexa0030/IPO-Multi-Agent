package com.ipoagent.risk;

import com.ipoagent.domain.MetricResult;
import com.ipoagent.domain.RiskFinding;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class RiskRuleEngineTest {
    private final RiskRuleEngine engine = new RiskRuleEngine();

    @Test
    void flagsWeakCashConversionAsObservationRatherThanConclusion() {
        MetricResult metric = new MetricResult("ocf_to_net_profit", "2025", 0.593,
                "0.59x", "经营现金流/净利润", List.of("ocf", "profit"), List.of(21, 23));

        List<RiskFinding> findings = engine.scan(List.of(metric));

        assertThat(findings).singleElement().satisfies(finding -> {
            assertThat(finding.ruleCode()).isEqualTo("weak_cash_conversion");
            assertThat(finding.severity()).isEqualTo("medium");
            assertThat(finding.assessmentStatus()).isEqualTo("observation");
        });
    }

    @Test
    void flagsThreePeriodMarginDeclineWithoutOverstatingRisk() {
        List<MetricResult> metrics = List.of(
                margin("2023", 0.569), margin("2024", 0.556), margin("2025", 0.545));

        List<RiskFinding> findings = engine.scan(metrics);

        assertThat(findings).singleElement().satisfies(finding -> {
            assertThat(finding.ruleCode()).isEqualTo("gross_margin_decline");
            assertThat(finding.severity()).isEqualTo("low");
            assertThat(finding.description()).contains("不直接等同于盈利能力恶化");
        });
    }

    private MetricResult margin(String period, double value) {
        return new MetricResult("gross_margin", period, value, String.format("%.1f%%", value * 100),
                "毛利/收入", List.of("gp-" + period, "rev-" + period), List.of(21));
    }
}
