package com.ipoagent.orchestration;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ipoagent.domain.ResearchChallenge;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class ReplanDecisionParser {
    private final ObjectMapper mapper;

    public ReplanDecisionParser(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    public List<ResearchChallenge> select(String modelOutput, List<ResearchChallenge> candidates,
                                          int maxTasks) {
        try {
            String json = extractJson(modelOutput);
            ReplanDecision decision = mapper.readValue(json, ReplanDecision.class);
            Set<String> selected = new LinkedHashSet<>(decision.findingRuleCodes());
            return candidates.stream()
                    .filter(challenge -> selected.contains(challenge.findingRuleCode()))
                    .limit(maxTasks)
                    .toList();
        } catch (RuntimeException | JsonProcessingException exception) {
            return List.of();
        }
    }

    private String extractJson(String text) {
        int start = text.indexOf('{');
        int end = text.lastIndexOf('}');
        if (start < 0 || end < start) throw new IllegalArgumentException("model output contains no JSON object");
        return text.substring(start, end + 1);
    }

    public record ReplanDecision(List<String> findingRuleCodes, String rationale) {
        public ReplanDecision {
            findingRuleCodes = findingRuleCodes == null ? List.of() : List.copyOf(findingRuleCodes);
        }
    }
}
