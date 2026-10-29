// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

/** A JSON-RPC error with a protocol error code (see the wire protocol in the implementation plan). */
public class RpcException extends RuntimeException {

    public static final int PARSE_ERROR = -32700;
    public static final int INVALID_REQUEST = -32600;
    public static final int METHOD_NOT_FOUND = -32601;
    public static final int INVALID_PARAMS = -32602;
    public static final int INTERNAL = -32000;
    public static final int NO_FOCUSED_EDITABLE = -32010;
    public static final int NO_FRAME = -32011;
    public static final int UIA_UNAVAILABLE = -32012;
    public static final int PAUSED = -32013;

    private final int code;

    public RpcException(int code, String message) {
        super(message);
        this.code = code;
    }

    public RpcException(int code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    public int getCode() {
        return code;
    }
}
