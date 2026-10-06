package com.ipoagent.workflow;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.AgentTrace;
import com.ipoagent.domain.MetricResult;
import com.ipoagent.domain.RiskFinding;
import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.ResearchTask;
import com.ipoagent.orchestration.InvestmentReviewGate;
import com.ipoagent.orchestration.ResearchPlanner;
import com.ipoagent.orchestration.ReplanResult;
import com.ipoagent.risk.MetricEngine;
import com.ipoagent.risk.RiskRuleEngine;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class DeterministicResearchWorkflow implements IpoResearchWorkflow {
    private final MetricEngine metricEngine;
    private final RiskRuleEngine riskRuleEngine;
    private final ResearchPlanner planner;
    private final InvestmentReviewGate reviewGate;
    private final int maxReplanRounds;

    public DeterministicResearchWorkflow(MetricEngine metricEngine, RiskRuleEngine riskRuleEngine,
                                         ResearchPlanner planner, InvestmentReviewGate reviewGate) {
        this.metricEngine = metricEngine;
        this.riskRuleEngine = riskRuleEngine;
        this.planner = planner;
        this.reviewGate = reviewGate;
        this.maxReplanRounds = 1;
    }

    @Override
    public WorkflowResult execute(AnalysisRequest request) {
        List<AgentTrace> trace = new ArrayList<>();
        trace.add(AgentTrace.completed("intake", "接收结构化财务事实并锁定报告主体"));
        List<ResearchTask> tasks = new ArrayList<>(planner.initialPlan(request));
        trace.add(AgentTrace.completed("planner", "生成包含依赖关系的初始任务DAG，共 " + tasks.size() + " 项任务"));
        List<MetricResult> metrics = metricEngine.calculate(request.facts(), request.reportingEntity());
        tasks.set(0, tasks.get(0).completed("计算 " + metrics.size() + " 项指标"));
        trace.add(AgentTrace.completed("financial-metric-tool", "确定性计算 " + metrics.size() + " 项指标"));
        List<RiskFinding> findings = riskRuleEngine.scan(metrics);
        tasks.set(1, tasks.get(1).completed("形成 " + findings.size() + " 项规则观察"));
        trace.add(AgentTrace.completed("risk-rule-tool", "规则初筛形成 " + findings.size() + " 项观察"));
        List<ResearchChallenge> challenges = reviewGate.review(findings);
        trace.add(AgentTrace.completed("review-gate", "形成 " + challenges.size()
                + " 项反证问题；规则命中继续保持 observation"));

        int replanRounds = 0;
        if (!challenges.isEmpty() && maxReplanRounds > 0) {
            replanRounds = 1;
            ReplanResult replan = planner.replan(challenges, replanRounds);
            List<ResearchTask> followUps = replan.tasks();
            for (ResearchTask followUp : followUps) {
                tasks.add(followUp.unableToVerify("尚未连接外部补证Executor，保留为证据缺口"));
            }
            trace.add(AgentTrace.completed("bounded-replan", "执行第1轮且仅一轮补证规划，共 "
                    + followUps.size() + " 项；plannerMode=" + replan.plannerMode()
                    + "；" + replan.detail() + "；未核实事项不自动升级为风险"));
        }
        return new WorkflowResult(metrics, findings, List.copyOf(tasks), challenges, replanRounds, trace);
    }
}
