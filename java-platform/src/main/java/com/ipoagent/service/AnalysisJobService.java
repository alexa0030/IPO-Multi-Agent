package com.ipoagent.service;

import com.ipoagent.client.ProspectusParserClient;
import com.ipoagent.domain.AnalysisJob;
import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.ParserAnalysisRequest;
import com.ipoagent.workflow.IpoResearchWorkflow;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.NoSuchElementException;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class AnalysisJobService {
    private final IpoResearchWorkflow workflow;
    private final ProspectusParserClient parserClient;
    private final Map<String, AnalysisJob> jobs = new ConcurrentHashMap<>();

    public AnalysisJobService(IpoResearchWorkflow workflow, ProspectusParserClient parserClient) {
        this.workflow = workflow;
        this.parserClient = parserClient;
    }

    public AnalysisJob createFromParser(ParserAnalysisRequest request) {
        return create(parserClient.fetchVerifiedFacts(request));
    }

    public AnalysisJob create(AnalysisRequest request) {
        String id = UUID.randomUUID().toString();
        AnalysisJob running = AnalysisJob.running(id, request);
        jobs.put(id, running);
        try {
            IpoResearchWorkflow.WorkflowResult result = workflow.execute(request);
            AnalysisJob completed = running.completed(result.metrics(), result.findings(), result.tasks(),
                    result.challenges(), result.replanRounds(), result.trace());
            jobs.put(id, completed);
            return completed;
        } catch (RuntimeException exception) {
            AnalysisJob failed = running.failed(exception.getMessage(), running.trace());
            jobs.put(id, failed);
            return failed;
        }
    }

    public AnalysisJob get(String id) {
        AnalysisJob job = jobs.get(id);
        if (job == null) throw new NoSuchElementException("analysis job not found: " + id);
        return job;
    }
}
