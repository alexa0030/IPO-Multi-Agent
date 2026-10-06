package com.ipoagent.risk;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.MetricResult;
import com.ipoagent.domain.RiskFinding;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class ContractParityTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final MetricEngine metricEngine = new MetricEngine();
    private final RiskRuleEngine riskRuleEngine = new RiskRuleEngine();

    @Test
    void javaEngineMatchesVerifiedHosonsoftContract() throws Exception {
        Path fixture = locateFixture();
        AnalysisRequest request = mapper.readValue(Files.readString(fixture), AnalysisRequest.class);

        List<MetricResult> metrics = metricEngine.calculate(request.facts(), request.reportingEntity());
        Map<String, MetricResult> latest = metrics.stream()
                .filter(metric -> metric.period().equals("2025"))
                .collect(Collectors.toMap(MetricResult::metricCode, Function.identity()));

        assertThat(latest.get("gross_margin").value()).isCloseTo(0.545, within(0.0005));
        assertThat(latest.get("net_margin").value()).isCloseTo(0.238, within(0.0005));
        assertThat(latest.get("ocf_to_net_profit").value()).isCloseTo(0.593, within(0.0005));
        assertThat(latest.get("current_ratio").value()).isCloseTo(3.7, within(0.01));

        List<RiskFinding> findings = riskRuleEngine.scan(metrics);
        assertThat(findings).extracting(RiskFinding::ruleCode)
                .contains("inventory_vs_revenue", "receivable_vs_revenue",
                        "weak_cash_conversion", "gross_margin_decline");
        assertThat(findings).allMatch(finding -> finding.assessmentStatus().equals("observation"));
    }

    private Path locateFixture() {
        List<Path> candidates = List.of(
                Path.of("contracts", "fixtures", "hosonsoft-financial-facts.json"),
                Path.of("..", "contracts", "fixtures", "hosonsoft-financial-facts.json")
        );
        return candidates.stream().filter(Files::exists).findFirst()
                .orElseThrow(() -> new IllegalStateException("shared Hosonsoft fixture not found"));
    }
}
