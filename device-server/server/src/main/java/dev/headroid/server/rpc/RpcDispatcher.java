// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Routes newline-delimited JSON-RPC 2.0 requests to registered methods. One line in, at most one line out. */
public final class RpcDispatcher {

    /** Called for every handled request, e.g. to log or to account activity. */
    public interface Observer {
        void onCall(String method, long durationMs, Integer errorCode);
    }

    private final Map<String, RpcMethod> methods = new ConcurrentHashMap<>();
    private Observer observer;

    public void register(String name, RpcMethod method) {
        methods.put(name, method);
    }

    public void setObserver(Observer observer) {
        this.observer = observer;
    }

    /** Handles one request line; returns the response line, or {@code null} for notifications and blank lines. */
    public String handleLine(String line) {
        if (line.trim().isEmpty()) {
            return null;
        }

        Object parsed;
        try {
            parsed = Json.parse(line);
        } catch (Json.JsonException e) {
            return Json.write(error(null, RpcException.PARSE_ERROR, "Parse error: " + e.getMessage()));
        }

        if (!(parsed instanceof Map)) {
            return Json.write(error(null, RpcException.INVALID_REQUEST, "Request must be a JSON object (batches are not supported)"));
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> request = (Map<String, Object>) parsed;
        boolean isNotification = !request.containsKey("id");
        Object id = request.get("id");
        if (id != null && !(id instanceof String) && !(id instanceof Number)) {
            return Json.write(error(null, RpcException.INVALID_REQUEST, "Invalid id"));
        }

        Object method = request.get("method");
        Object params = request.get("params");
        if (!(method instanceof String)) {
            return isNotification ? null : Json.write(error(id, RpcException.INVALID_REQUEST, "Missing method"));
        }
        if (params != null && !(params instanceof Map)) {
            return isNotification ? null : Json.write(error(id, RpcException.INVALID_REQUEST, "params must be an object"));
        }

        String name = (String) method;
        long start = System.nanoTime();
        Map<String, Object> response;
        Integer errorCode = null;
        RpcMethod target = methods.get(name);
        if (target == null) {
            errorCode = RpcException.METHOD_NOT_FOUND;
            response = error(id, errorCode, "Method not found: " + name);
        } else {
            try {
                @SuppressWarnings("unchecked")
                Object result = target.call(new Params((Map<String, Object>) params));
                response = new LinkedHashMap<>();
                response.put("jsonrpc", "2.0");
                response.put("id", id);
                response.put("result", result != null ? result : Collections.emptyMap());
            } catch (RpcException e) {
                errorCode = e.getCode();
                response = error(id, errorCode, e.getMessage());
            } catch (Exception | AssertionError e) {
                errorCode = RpcException.INTERNAL;
                response = error(id, errorCode, e.getClass().getSimpleName() + ": " + e.getMessage());
            }
        }

        if (observer != null) {
            observer.onCall(name, (System.nanoTime() - start) / 1_000_000, errorCode);
        }
        return isNotification ? null : Json.write(response);
    }

    private static Map<String, Object> error(Object id, int code, String message) {
        Map<String, Object> error = new LinkedHashMap<>();
        error.put("code", code);
        error.put("message", message);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("jsonrpc", "2.0");
        response.put("id", id);
        response.put("error", error);
        return response;
    }

    /** Builds a server-to-host notification line ({@code method: "event"}). */
    public static String event(String type, Map<String, Object> data) {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("type", type);
        if (data != null) {
            params.putAll(data);
        }
        Map<String, Object> notification = new LinkedHashMap<>();
        notification.put("jsonrpc", "2.0");
        notification.put("method", "event");
        notification.put("params", params);
        return Json.write(notification);
    }
}
