package com.ipoagent.domain;

import java.util.List;

public record ResearchTask(
        String taskId,
        TaskType taskType,
        List<String> dependencies,
        TaskStatus status,
        int attempt,
        String parentTaskId,
        String resultSummary
) {
    public enum TaskType { CALCULATE_METRICS, SCREEN_RISKS, FOLLOW_UP_EVIDENCE }
    public enum TaskStatus { PENDING, COMPLETED, UNABLE_TO_VERIFY, FAILED }

    public static ResearchTask pending(String id, TaskType type, List<String> dependencies,
                                       int attempt, String parentTaskId) {
        return new ResearchTask(id, type, List.copyOf(dependencies), TaskStatus.PENDING,
                attempt, parentTaskId, null);
    }

    public ResearchTask completed(String summary) {
        return new ResearchTask(taskId, taskType, dependencies, TaskStatus.COMPLETED,
                attempt, parentTaskId, summary);
    }

    public ResearchTask unableToVerify(String summary) {
        return new ResearchTask(taskId, taskType, dependencies, TaskStatus.UNABLE_TO_VERIFY,
                attempt, parentTaskId, summary);
    }
}
