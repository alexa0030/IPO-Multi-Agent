package com.ipoagent.client;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.ParserAnalysisRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

@Component
public class HttpProspectusParserClient implements ProspectusParserClient {
    private final RestClient restClient;

    public HttpProspectusParserClient(RestClient.Builder builder,
                                      @Value("${ipo.parser.base-url:http://localhost:8090}") String baseUrl) {
        this.restClient = builder.baseUrl(baseUrl).build();
    }

    @Override
    public AnalysisRequest fetchVerifiedFacts(ParserAnalysisRequest request) {
        try {
            AnalysisRequest response = restClient.post()
                    .uri("/api/v1/parser/facts")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(AnalysisRequest.class);
            if (response == null || response.facts() == null || response.facts().isEmpty()) {
                throw new ParserClientException("parser returned no verified financial facts");
            }
            if (!request.documentId().equals(response.documentId())) {
                throw new ParserClientException("parser response documentId does not match request");
            }
            return response;
        } catch (ParserClientException exception) {
            throw exception;
        } catch (RestClientException exception) {
            throw new ParserClientException("prospectus parser request failed", exception);
        }
    }
}
