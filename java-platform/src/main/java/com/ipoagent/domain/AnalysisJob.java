package com.ipoagent.domain;

import java.time.Instant;
import java.util.List;

public record AnalysisJob(
        String jobId,
        String company,
        String documentId,
        JobStatus status,
        List<MetricResult> metrics,
        List<RiskFinding> findings,
        List<AgentTrace> trace,
        Instant createdAt,
        Instant completedAt,
        String error
) {
    public enum JobStatus { RUNNING, COMPLETED, FAILED }

    public static AnalysisJob running(String id, AnalysisRequest request) {
        return new AnalysisJob(id, request.company(), request.documentId(), JobStatus.RUNNING,
                List.of(), List.of(), List.of(), Instant.now(), null, null);
    }

    public AnalysisJob completed(List<MetricResult> newMetrics, List<RiskFinding> newFindings,
                                 List<AgentTrace> newTrace) {
        return new AnalysisJob(jobId, company, documentId, JobStatus.COMPLETED,
                List.copyOf(newMetrics), List.copyOf(newFindings), List.copyOf(newTrace),
                createdAt, Instant.now(), null);
    }

    public AnalysisJob failed(String message, List<AgentTrace> newTrace) {
        return new AnalysisJob(jobId, company, documentId, JobStatus.FAILED,
                metrics, findings, List.copyOf(newTrace), createdAt, Instant.now(), message);
    }
}
