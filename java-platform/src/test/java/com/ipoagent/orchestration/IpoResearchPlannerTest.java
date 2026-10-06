package com.ipoagent.orchestration;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.FinancialFact;
import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.ResearchTask;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class IpoResearchPlannerTest {
    private final IpoResearchPlanner planner = new IpoResearchPlanner();

    @Test
    void initialPlanExpressesMetricToRiskDependency() {
        AnalysisRequest request = new AnalysisRequest("issuer", "doc-1", "issuer",
                List.of(new FinancialFact("f1", "revenue", "2025", 100d, null, 1, "issuer")));

        List<ResearchTask> tasks = planner.initialPlan(request);

        assertThat(tasks).hasSize(2);
        assertThat(tasks.get(0).taskType()).isEqualTo(ResearchTask.TaskType.CALCULATE_METRICS);
        assertThat(tasks.get(1).dependencies()).containsExactly(tasks.get(0).taskId());
    }

    @Test
    void replanCreatesTraceableFollowUpTasks() {
        ResearchChallenge challenge = new ResearchChallenge("c1", "weak_cash_conversion",
                "why", List.of("cash bridge"), "open");

        List<ResearchTask> tasks = planner.replan(List.of(challenge), 1);

        assertThat(tasks).singleElement().satisfies(task -> {
            assertThat(task.taskType()).isEqualTo(ResearchTask.TaskType.FOLLOW_UP_EVIDENCE);
            assertThat(task.parentTaskId()).isEqualTo("c1");
            assertThat(task.attempt()).isEqualTo(2);
        });
    }
}
