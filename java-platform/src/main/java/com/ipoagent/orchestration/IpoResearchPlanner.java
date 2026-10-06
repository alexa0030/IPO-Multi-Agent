package com.ipoagent.orchestration;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.ResearchTask;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class IpoResearchPlanner implements ResearchPlanner {

    @Override
    public List<ResearchTask> initialPlan(AnalysisRequest request) {
        String prefix = request.documentId();
        ResearchTask metrics = ResearchTask.pending(prefix + ":metrics",
                ResearchTask.TaskType.CALCULATE_METRICS, List.of(), 1, null);
        ResearchTask risks = ResearchTask.pending(prefix + ":risks",
                ResearchTask.TaskType.SCREEN_RISKS, List.of(metrics.taskId()), 1, null);
        return List.of(metrics, risks);
    }

    @Override
    public ReplanResult replan(List<ResearchChallenge> challenges, int round) {
        List<ResearchTask> tasks = new ArrayList<>();
        for (ResearchChallenge challenge : challenges) {
            tasks.add(ResearchTask.pending(
                    "follow-up:" + round + ":" + challenge.findingRuleCode(),
                    ResearchTask.TaskType.FOLLOW_UP_EVIDENCE,
                    List.of(),
                    round + 1,
                    challenge.challengeId()
            ));
        }
        return ReplanResult.deterministic(tasks, "按全部Reviewer Challenge生成补证任务");
    }
}
