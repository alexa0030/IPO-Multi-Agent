package com.ipoagent.workflow;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.AgentTrace;
import com.ipoagent.domain.MetricResult;
import com.ipoagent.domain.RiskFinding;

import java.util.List;

public interface IpoResearchWorkflow {
    WorkflowResult execute(AnalysisRequest request);

    record WorkflowResult(List<MetricResult> metrics, List<RiskFinding> findings, List<AgentTrace> trace) {}
}
