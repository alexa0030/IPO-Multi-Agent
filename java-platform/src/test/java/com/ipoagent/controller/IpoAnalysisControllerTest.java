package com.ipoagent.controller;

import com.ipoagent.domain.AnalysisJob;
import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.FinancialFact;
import com.ipoagent.service.AnalysisJobService;
import com.ipoagent.client.ProspectusParserClient;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class IpoAnalysisControllerTest {
    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper objectMapper;
    @Autowired AnalysisJobService service;
    @MockBean ProspectusParserClient parserClient;

    @Test
    void createsAndReadsAnalysisJob() throws Exception {
        AnalysisRequest request = new AnalysisRequest("深圳市汉森软件股份有限公司", "hosonsoft-2025",
                "深圳市汉森软件股份有限公司", List.of(
                new FinancialFact("revenue", "revenue", "2025", 596_909d, "CNY thousand", 21,
                        "深圳市汉森软件股份有限公司"),
                new FinancialFact("profit", "net_profit", "2025", 142_277d, "CNY thousand", 21,
                        "深圳市汉森软件股份有限公司"),
                new FinancialFact("ocf", "operating_cash_flow", "2025", 84_389d, "CNY thousand", 23,
                        "深圳市汉森软件股份有限公司")
        ));

        String body = mockMvc.perform(post("/api/v1/ipo/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsBytes(request)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("COMPLETED"))
                .andExpect(jsonPath("$.findings[0].ruleCode").value("weak_cash_conversion"))
                .andReturn().getResponse().getContentAsString();

        AnalysisJob created = objectMapper.readValue(body, AnalysisJob.class);
        mockMvc.perform(get("/api/v1/ipo/jobs/{id}", created.jobId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.company").value("深圳市汉森软件股份有限公司"));
    }
}
