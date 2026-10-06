package com.ipoagent.client;

import com.ipoagent.domain.AnalysisRequest;
import com.ipoagent.domain.ParserAnalysisRequest;

public interface ProspectusParserClient {
    AnalysisRequest fetchVerifiedFacts(ParserAnalysisRequest request);
}
