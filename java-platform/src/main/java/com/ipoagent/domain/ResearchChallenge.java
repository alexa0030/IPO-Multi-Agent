package com.ipoagent.domain;

import java.util.List;

public record ResearchChallenge(
        String challengeId,
        String findingRuleCode,
        String question,
        List<String> requiredEvidence,
        String status
) {}
