package com.ipoagent.domain;

import java.util.List;

public record MetricResult(
        String metricCode,
        String period,
        double value,
        String displayValue,
        String formula,
        List<String> sourceFactIds,
        List<Integer> sourcePages
) {}
