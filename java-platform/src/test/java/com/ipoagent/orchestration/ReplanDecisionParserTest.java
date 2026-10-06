package com.ipoagent.orchestration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ipoagent.domain.ResearchChallenge;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ReplanDecisionParserTest {
    private final ReplanDecisionParser parser = new ReplanDecisionParser(new ObjectMapper());
    private final List<ResearchChallenge> candidates = List.of(
            challenge("weak_cash_conversion"),
            challenge("inventory_vs_revenue"),
            challenge("receivable_vs_revenue"),
            challenge("high_debt_ratio")
    );

    @Test
    void acceptsOnlyKnownCodesAndAppliesTaskBudget() {
        String output = "```json\n{\"findingRuleCodes\":[\"unknown\",\"inventory_vs_revenue\","
                + "\"weak_cash_conversion\",\"high_debt_ratio\"],\"rationale\":\"focus\"}\n```";

        List<ResearchChallenge> selected = parser.select(output, candidates, 2);

        assertThat(selected).extracting(ResearchChallenge::findingRuleCode)
                .containsExactly("weak_cash_conversion", "inventory_vs_revenue");
    }

    @Test
    void malformedModelOutputFailsClosed() {
        assertThat(parser.select("not-json", candidates, 3)).isEmpty();
    }

    private ResearchChallenge challenge(String code) {
        return new ResearchChallenge("challenge:" + code, code, "question", List.of("evidence"), "open");
    }
}
