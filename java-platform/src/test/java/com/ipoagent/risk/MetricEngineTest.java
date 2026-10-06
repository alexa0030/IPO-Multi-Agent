package com.ipoagent.risk;

import com.ipoagent.domain.FinancialFact;
import com.ipoagent.domain.MetricResult;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class MetricEngineTest {
    private final MetricEngine engine = new MetricEngine();

    @Test
    void calculatesHosonsoft2025MarginsAndCashConversion() {
        List<FinancialFact> facts = List.of(
                fact("revenue", 596_909d), fact("gross_profit", 325_279d),
                fact("net_profit", 142_277d), fact("operating_cash_flow", 84_389d)
        );

        List<MetricResult> metrics = engine.calculate(facts, "深圳市汉森软件股份有限公司");

        assertThat(value(metrics, "gross_margin")).isCloseTo(0.545, within(0.0005));
        assertThat(value(metrics, "net_margin")).isCloseTo(0.2384, within(0.0005));
        assertThat(value(metrics, "ocf_to_net_profit")).isCloseTo(0.5931, within(0.0005));
    }

    private FinancialFact fact(String code, double value) {
        return new FinancialFact("fact-" + code, code, "2025", value, "CNY thousand", 21,
                "深圳市汉森软件股份有限公司");
    }

    private double value(List<MetricResult> metrics, String code) {
        return metrics.stream().filter(metric -> metric.metricCode().equals(code)).findFirst().orElseThrow().value();
    }

    private org.assertj.core.data.Offset<Double> within(double value) {
        return org.assertj.core.data.Offset.offset(value);
    }
}
