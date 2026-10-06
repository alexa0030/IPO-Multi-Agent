package com.ipoagent.domain;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record FinancialFact(
        @NotBlank String factId,
        @NotBlank String metricCode,
        @NotBlank String period,
        @NotNull Double value,
        String unit,
        Integer page,
        String reportingEntity
) {}
