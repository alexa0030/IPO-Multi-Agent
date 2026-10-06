package com.ipoagent.orchestration;

import com.ipoagent.domain.ResearchChallenge;
import com.ipoagent.domain.ResearchTask;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(properties = {
        "ipo.agent.llm-planner-enabled=true",
        "spring.ai.model.chat=openai",
        "spring.ai.model.embedding=none",
        "spring.ai.openai.api-key=test-key",
        "spring.ai.openai.chat.options.model=qwen-test"
})
class LlmResearchPlannerIntegrationTest {
    private static final AtomicReference<String> REQUEST_PATH = new AtomicReference<>();
    private static final HttpServer server = startModelStub();

    @Autowired
    private ResearchPlanner planner;

    @AfterAll
    static void stopModelStub() {
        server.stop(0);
    }

    @DynamicPropertySource
    static void modelProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.ai.openai.base-url",
                () -> "http://127.0.0.1:" + server.getAddress().getPort());
    }

    @Test
    void callsCompatibleModelAndCreatesOnlySelectedFollowUpTask() {
        List<ResearchChallenge> challenges = List.of(
                challenge("weak_cash_conversion"),
                challenge("inventory_vs_revenue")
        );

        ReplanResult result = planner.replan(challenges, 1);
        List<ResearchTask> tasks = result.tasks();

        assertThat(planner).isInstanceOf(LlmResearchPlanner.class);
        assertThat(result.plannerMode()).isEqualTo("llm");
        assertThat(REQUEST_PATH.get()).isEqualTo("/v1/chat/completions");
        assertThat(tasks).hasSize(1);
        assertThat(tasks.get(0).parentTaskId()).isEqualTo("challenge:inventory_vs_revenue");
    }

    private static ResearchChallenge challenge(String code) {
        return new ResearchChallenge("challenge:" + code, code, "question", List.of("evidence"), "open");
    }

    private static HttpServer startModelStub() {
        try {
            HttpServer modelStub = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            modelStub.createContext("/", LlmResearchPlannerIntegrationTest::respond);
            modelStub.start();
            return modelStub;
        } catch (IOException exception) {
            throw new ExceptionInInitializerError(exception);
        }
    }

    private static void respond(HttpExchange exchange) throws IOException {
        REQUEST_PATH.set(exchange.getRequestURI().getPath());
        exchange.getRequestBody().readAllBytes();
        String body = """
                {"id":"chatcmpl-test","object":"chat.completion","created":1,"model":"qwen-test",
                 "choices":[{"index":0,"message":{"role":"assistant","content":"{\\"findingRuleCodes\\":[\\"inventory_vs_revenue\\"],\\"rationale\\":\\"priority\\"}"},"finish_reason":"stop"}],
                 "usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}
                """;
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }
}
