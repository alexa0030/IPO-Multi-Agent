package com.ipoagent.domain;

import java.time.Instant;

public record AgentTrace(
        String stage,
        String status,
        String detail,
        Instant completedAt
) {
    public static AgentTrace completed(String stage, String detail) {
        return new AgentTrace(stage, "completed", detail, Instant.now());
    }
}
