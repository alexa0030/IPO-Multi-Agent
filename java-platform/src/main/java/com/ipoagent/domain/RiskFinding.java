package com.ipoagent.domain;

import java.util.List;

public record RiskFinding(
        String ruleCode,
        String period,
        String category,
        String title,
        String severity,
        String assessmentStatus,
        String description,
        List<String> evidenceMetricCodes,
        List<Integer> sourcePages
) {}
