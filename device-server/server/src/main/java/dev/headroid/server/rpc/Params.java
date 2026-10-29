// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

import java.util.Collections;
import java.util.Map;

/** Typed access to JSON-RPC params; type errors become {@link RpcException#INVALID_PARAMS}. */
public final class Params {

    private final Map<String, Object> values;

    public Params(Map<String, Object> values) {
        this.values = values != null ? values : Collections.emptyMap();
    }

    public boolean has(String name) {
        return values.get(name) != null;
    }

    private static RpcException invalid(String name, String problem) {
        return new RpcException(RpcException.INVALID_PARAMS, name + ": " + problem);
    }

    private Object require(String name) {
        Object value = values.get(name);
        if (value == null) {
            throw invalid(name, "required");
        }
        return value;
    }

    private static int toInt(String name, Object value) {
        if (!(value instanceof Number)) {
            throw invalid(name, "expected an integer");
        }
        double d = ((Number) value).doubleValue();
        if (d != Math.rint(d) || d < Integer.MIN_VALUE || d > Integer.MAX_VALUE) {
            throw invalid(name, "expected a 32-bit integer");
        }
        return (int) d;
    }

    public int getInt(String name) {
        return toInt(name, require(name));
    }

    public int optInt(String name, int defaultValue) {
        Object value = values.get(name);
        return value == null ? defaultValue : toInt(name, value);
    }

    public double getDouble(String name) {
        Object value = require(name);
        if (!(value instanceof Number)) {
            throw invalid(name, "expected a number");
        }
        return ((Number) value).doubleValue();
    }

    public String getString(String name) {
        Object value = require(name);
        if (!(value instanceof String)) {
            throw invalid(name, "expected a string");
        }
        return (String) value;
    }

    public String optString(String name, String defaultValue) {
        Object value = values.get(name);
        if (value == null) {
            return defaultValue;
        }
        if (!(value instanceof String)) {
            throw invalid(name, "expected a string");
        }
        return (String) value;
    }

    public boolean optBool(String name, boolean defaultValue) {
        Object value = values.get(name);
        if (value == null) {
            return defaultValue;
        }
        if (!(value instanceof Boolean)) {
            throw invalid(name, "expected a boolean");
        }
        return (Boolean) value;
    }
}
