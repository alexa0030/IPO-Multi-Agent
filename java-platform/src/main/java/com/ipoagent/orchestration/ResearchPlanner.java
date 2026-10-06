package com.ipoagent.orchestration;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.ResearchTask;

import java.util.List;

public interface ResearchPlanner {
    List<ResearchTask> initialPlan(AnalysisRequest request);

    List<ResearchTask> replan(List<ResearchChallenge> challenges, int round);
}
