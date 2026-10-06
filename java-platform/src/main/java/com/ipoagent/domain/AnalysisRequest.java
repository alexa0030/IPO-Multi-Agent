package com.ipoagent.domain;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

public record AnalysisRequest(
        @NotBlank String company,
        @NotBlank String documentId,
        String reportingEntity,
        @NotEmpty List<@Valid FinancialFact> facts
) {}
