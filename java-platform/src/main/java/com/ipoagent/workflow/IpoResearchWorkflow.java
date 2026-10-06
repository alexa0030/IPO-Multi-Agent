package com.ipoagent.workflow;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.AgentTrace;
import com.ipoagent.domain.MetricResult;
import com.ipoagent.domain.RiskFinding;
import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.ResearchTask;

import java.util.List;

public interface IpoResearchWorkflow {
    WorkflowResult execute(AnalysisRequest request);

    record WorkflowResult(
            List<MetricResult> metrics,
            List<RiskFinding> findings,
            List<ResearchTask> tasks,
            List<ResearchChallenge> challenges,
            int replanRounds,
            List<AgentTrace> trace
    ) {}
}
