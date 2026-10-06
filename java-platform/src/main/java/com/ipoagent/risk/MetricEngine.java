package com.ipoagent.risk;

import com.ipoagent.domain.FinancialFact;
import com.ipoagent.domain.MetricResult;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.TreeSet;

@Component
public class MetricEngine {

    public List<MetricResult> calculate(List<FinancialFact> facts, String reportingEntity) {
        Map<String, Map<String, FinancialFact>> byCode = new LinkedHashMap<>();
        facts.stream()
                .filter(fact -> reportingEntity == null || fact.reportingEntity() == null
                        || reportingEntity.equals(fact.reportingEntity()))
                .forEach(fact -> byCode.computeIfAbsent(fact.metricCode(), ignored -> new LinkedHashMap<>())
                        .putIfAbsent(fact.period(), fact));

        List<MetricResult> results = new ArrayList<>();
        addGrowth(results, byCode, "revenue", "revenue_growth");
        addGrowth(results, byCode, "net_profit", "net_profit_growth");
        addGrowth(results, byCode, "trade_receivable", "receivable_growth");
        addGrowth(results, byCode, "inventory", "inventory_growth");

        TreeSet<String> periods = new TreeSet<>();
        byCode.values().forEach(periodMap -> periods.addAll(periodMap.keySet()));
        for (String period : periods) {
            ratio(byCode, period, "gross_profit", "revenue", "gross_margin", "毛利/收入", true)
                    .ifPresent(results::add);
            ratio(byCode, period, "net_profit", "revenue", "net_margin", "净利润/收入", true)
                    .ifPresent(results::add);
            ratio(byCode, period, "operating_cash_flow", "net_profit", "ocf_to_net_profit",
                    "经营现金流/净利润", false).ifPresent(results::add);
            ratio(byCode, period, "current_assets", "current_liabilities", "current_ratio",
                    "流动资产/流动负债", false).ifPresent(results::add);
            ratio(byCode, period, "total_liabilities", "total_assets", "debt_ratio",
                    "总负债/总资产", true).ifPresent(results::add);
        }
        return results.stream()
                .sorted(Comparator.comparing(MetricResult::period).thenComparing(MetricResult::metricCode))
                .toList();
    }

    private void addGrowth(List<MetricResult> output,
                           Map<String, Map<String, FinancialFact>> byCode,
                           String factCode, String metricCode) {
        List<FinancialFact> values = byCode.getOrDefault(factCode, Map.of()).values().stream()
                .sorted(Comparator.comparing(FinancialFact::period))
                .toList();
        for (int index = 1; index < values.size(); index++) {
            FinancialFact previous = values.get(index - 1);
            FinancialFact current = values.get(index);
            if (previous.value() == 0) continue;
            double value = (current.value() - previous.value()) / Math.abs(previous.value());
            output.add(metric(metricCode, current.period(), value, true, "(本期-上期)/|上期|",
                    List.of(previous, current)));
        }
    }

    private Optional<MetricResult> ratio(Map<String, Map<String, FinancialFact>> byCode,
                                         String period, String numeratorCode, String denominatorCode,
                                         String metricCode, String formula, boolean percent) {
        FinancialFact numerator = get(byCode, numeratorCode, period);
        FinancialFact denominator = get(byCode, denominatorCode, period);
        if (numerator == null || denominator == null || denominator.value() == 0) return Optional.empty();
        return Optional.of(metric(metricCode, period, numerator.value() / denominator.value(), percent,
                formula, List.of(numerator, denominator)));
    }

    private FinancialFact get(Map<String, Map<String, FinancialFact>> byCode, String code, String period) {
        return byCode.getOrDefault(code, Map.of()).get(period);
    }

    private MetricResult metric(String code, String period, double value, boolean percent,
                                String formula, List<FinancialFact> sources) {
        String display = percent ? String.format("%.1f%%", value * 100) : String.format("%.2fx", value);
        List<Integer> pages = sources.stream().map(FinancialFact::page).filter(Objects::nonNull)
                .distinct().sorted().toList();
        return new MetricResult(code, period, value, display, formula,
                sources.stream().map(FinancialFact::factId).toList(), pages);
    }
}
