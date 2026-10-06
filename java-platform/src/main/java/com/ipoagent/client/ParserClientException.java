package com.ipoagent.client;

public class ParserClientException extends RuntimeException {
    public ParserClientException(String message, Throwable cause) {
        super(message, cause);
    }

    public ParserClientException(String message) {
        super(message);
    }
}
