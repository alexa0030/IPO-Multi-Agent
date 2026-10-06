package com.ipoagent.controller;

import com.ipoagent.domain.AnalysisJob;
import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.ParserAnalysisRequest;
import com.ipoagent.service.AnalysisJobService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/ipo/jobs")
public class IpoAnalysisController {
    private final AnalysisJobService service;

    public IpoAnalysisController(AnalysisJobService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public AnalysisJob create(@Valid @RequestBody AnalysisRequest request) {
        return service.create(request);
    }

    @PostMapping("/from-parser")
    @ResponseStatus(HttpStatus.CREATED)
    public AnalysisJob createFromParser(@Valid @RequestBody ParserAnalysisRequest request) {
        return service.createFromParser(request);
    }

    @GetMapping("/{jobId}")
    public AnalysisJob get(@PathVariable String jobId) {
        return service.get(jobId);
    }
}
