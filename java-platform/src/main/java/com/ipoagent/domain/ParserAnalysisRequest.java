package com.ipoagent.domain;

import jakarta.validation.constraints.NotBlank;

public record ParserAnalysisRequest(
        @NotBlank String company,
        @NotBlank String documentId,
        @NotBlank String reportingEntity
) {}
