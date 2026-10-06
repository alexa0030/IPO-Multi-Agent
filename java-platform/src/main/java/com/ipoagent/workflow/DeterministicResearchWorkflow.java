package com.ipoagent.workflow;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.AgentTrace;
import com.ipoagent.domain.MetricResult;
import com.ipoagent.domain.RiskFinding;
import com.ipoagent.risk.MetricEngine;
import com.ipoagent.risk.RiskRuleEngine;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class DeterministicResearchWorkflow implements IpoResearchWorkflow {
    private final MetricEngine metricEngine;
    private final RiskRuleEngine riskRuleEngine;

    public DeterministicResearchWorkflow(MetricEngine metricEngine, RiskRuleEngine riskRuleEngine) {
        this.metricEngine = metricEngine;
        this.riskRuleEngine = riskRuleEngine;
    }

    @Override
    public WorkflowResult execute(AnalysisRequest request) {
        List<AgentTrace> trace = new ArrayList<>();
        trace.add(AgentTrace.completed("intake", "接收结构化财务事实并锁定报告主体"));
        List<MetricResult> metrics = metricEngine.calculate(request.facts(), request.reportingEntity());
        trace.add(AgentTrace.completed("financial-metric-tool", "确定性计算 " + metrics.size() + " 项指标"));
        List<RiskFinding> findings = riskRuleEngine.scan(metrics);
        trace.add(AgentTrace.completed("risk-rule-tool", "规则初筛形成 " + findings.size() + " 项观察"));
        trace.add(AgentTrace.completed("review-gate", "规则命中保留为 observation，等待 Agent 解释与补证"));
        return new WorkflowResult(metrics, findings, trace);
    }
}
