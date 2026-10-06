package com.ipoagent.service;

import com.ipoagent.client.ProspectusParserClient;
import com.ipoagent.domain.AnalysisJob;
import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.FinancialFact;
import com.ipoagent.domain.ParserAnalysisRequest;
import com.ipoagent.risk.MetricEngine;
import com.ipoagent.risk.RiskRuleEngine;
import com.ipoagent.workflow.DeterministicResearchWorkflow;
import com.ipoagent.orchestration.InvestmentReviewGate;
import com.ipoagent.orchestration.IpoResearchPlanner;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class AnalysisJobServiceTest {

    @Test
    void fetchesVerifiedFactsBeforeRunningWorkflow() {
        ParserAnalysisRequest parserRequest = new ParserAnalysisRequest("汉森软件", "doc-1", "汉森软件");
        ProspectusParserClient parser = ignored -> new AnalysisRequest("汉森软件", "doc-1", "汉森软件",
                List.of(
                        fact("profit", "net_profit", 100d),
                        fact("cash", "operating_cash_flow", 40d)
                ));
        AnalysisJobService service = new AnalysisJobService(
                new DeterministicResearchWorkflow(new MetricEngine(), new RiskRuleEngine(),
                        new IpoResearchPlanner(), new InvestmentReviewGate()), parser);

        AnalysisJob job = service.createFromParser(parserRequest);

        assertThat(job.status()).isEqualTo(AnalysisJob.JobStatus.COMPLETED);
        assertThat(job.findings()).extracting("ruleCode").contains("weak_cash_conversion");
        assertThat(job.trace()).extracting("stage")
                .containsExactly("intake", "planner", "financial-metric-tool", "risk-rule-tool",
                        "review-gate", "bounded-replan");
        assertThat(job.replanRounds()).isEqualTo(1);
        assertThat(job.tasks()).extracting("status")
                .contains(com.ipoagent.domain.ResearchTask.TaskStatus.UNABLE_TO_VERIFY);
    }

    private FinancialFact fact(String id, String code, double value) {
        return new FinancialFact(id, code, "2025", value, "CNY thousand", 21, "汉森软件");
    }
}
