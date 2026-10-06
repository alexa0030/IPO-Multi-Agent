package com.ipoagent.orchestration;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.ResearchTask;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

@Component
@Primary
@ConditionalOnProperty(name = "ipo.agent.llm-planner-enabled", havingValue = "true")
public class LlmResearchPlanner implements ResearchPlanner {
    private final IpoResearchPlanner fallback;
    private final ChatClient chatClient;
    private final ObjectMapper mapper;
    private final ReplanDecisionParser parser;

    public LlmResearchPlanner(IpoResearchPlanner fallback, ChatModel chatModel, ObjectMapper mapper) {
        this.fallback = fallback;
        this.chatClient = ChatClient.create(chatModel);
        this.mapper = mapper;
        this.parser = new ReplanDecisionParser(mapper);
    }

    @Override
    public List<ResearchTask> initialPlan(AnalysisRequest request) {
        // Financial calculation and screening are mandatory deterministic gates.
        return fallback.initialPlan(request);
    }

    @Override
    public List<ResearchTask> replan(List<ResearchChallenge> challenges, int round) {
        if (challenges.isEmpty()) return List.of();
        try {
            String candidates = mapper.writeValueAsString(challenges.stream().map(challenge -> Map.of(
                    "findingRuleCode", challenge.findingRuleCode(),
                    "question", challenge.question(),
                    "requiredEvidence", challenge.requiredEvidence()
            )).toList());
            String output = chatClient.prompt()
                    .system("你是IPO尽调任务规划器。只能从候选findingRuleCode中选择最多3项最值得补证的问题。"
                            + "只返回JSON：{\"findingRuleCodes\":[...],\"rationale\":\"...\"}。"
                            + "不要计算或修改任何财务数字。")
                    .user("候选Challenge：" + candidates)
                    .call()
                    .content();
            List<ResearchChallenge> selected = parser.select(output, challenges, 3);
            return selected.isEmpty() ? fallback.replan(challenges, round) : fallback.replan(selected, round);
        } catch (JsonProcessingException | RuntimeException exception) {
            return fallback.replan(challenges, round);
        }
    }
}
