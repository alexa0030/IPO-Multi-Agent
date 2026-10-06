package com.ipoagent.orchestration;

import com.ipoagent.domain.ResearchTask;

import java.util.List;

public record ReplanResult(List<ResearchTask> tasks, String plannerMode, String detail) {
    public ReplanResult {
        tasks = List.copyOf(tasks);
    }

    public static ReplanResult deterministic(List<ResearchTask> tasks, String detail) {
        return new ReplanResult(tasks, "deterministic", detail);
    }

    public static ReplanResult llm(List<ResearchTask> tasks, String detail) {
        return new ReplanResult(tasks, "llm", detail);
    }

    public static ReplanResult fallback(List<ResearchTask> tasks, String detail) {
        return new ReplanResult(tasks, "deterministic_fallback", detail);
    }
}
