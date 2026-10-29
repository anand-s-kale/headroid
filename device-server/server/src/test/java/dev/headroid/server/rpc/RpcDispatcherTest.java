// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

import org.junit.Assert;
import org.junit.Before;
import org.junit.Test;

import java.util.Collections;
import java.util.Map;

public class RpcDispatcherTest {

    private RpcDispatcher dispatcher;

    @Before
    public void setUp() {
        dispatcher = new RpcDispatcher();
        dispatcher.register("echo", p -> Collections.singletonMap("value", p.getString("value")));
        dispatcher.register("add", p -> Collections.singletonMap("sum", p.getInt("a") + p.getInt("b")));
        dispatcher.register("boom", p -> {
            throw new IllegalStateException("kaput");
        });
        dispatcher.register("busy", p -> {
            throw new RpcException(RpcException.PAUSED, "paused");
        });
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> response(String line) {
        Assert.assertNotNull(line);
        return (Map<String, Object>) Json.parse(line);
    }

    @SuppressWarnings("unchecked")
    private static long errorCode(String line) {
        Map<String, Object> error = (Map<String, Object>) response(line).get("error");
        Assert.assertNotNull("expected an error in " + line, error);
        return (Long) error.get("code");
    }

    @Test
    public void callReturnsResultWithSameId() {
        Map<String, Object> r = response(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"add\",\"params\":{\"a\":2,\"b\":3}}"));
        Assert.assertEquals("2.0", r.get("jsonrpc"));
        Assert.assertEquals(7L, r.get("id"));
        Assert.assertEquals(5L, ((Map<?, ?>) r.get("result")).get("sum"));
    }

    @Test
    public void stringIdsAreEchoed() {
        Map<String, Object> r = response(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":\"x1\",\"method\":\"echo\",\"params\":{\"value\":\"hi\"}}"));
        Assert.assertEquals("x1", r.get("id"));
    }

    @Test
    public void parseErrorKeepsConnection() {
        String line = dispatcher.handleLine("{\"jsonrpc\":");
        Assert.assertEquals(RpcException.PARSE_ERROR, errorCode(line));
        Assert.assertTrue(response(line).containsKey("id"));
        Assert.assertNull(response(line).get("id"));
        // the dispatcher still serves the next line
        Assert.assertNotNull(response(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"echo\",\"params\":{\"value\":\"a\"}}"))
                .get("result"));
    }

    @Test
    public void missingMethodIsInvalidRequest() {
        Assert.assertEquals(RpcException.INVALID_REQUEST, errorCode(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1}")));
    }

    @Test
    public void nonObjectParamsIsInvalidRequest() {
        Assert.assertEquals(RpcException.INVALID_REQUEST,
                errorCode(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"echo\",\"params\":[1]}")));
    }

    @Test
    public void unknownMethod() {
        Assert.assertEquals(RpcException.METHOD_NOT_FOUND, errorCode(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"nope\"}")));
    }

    @Test
    public void batchArrayRejected() {
        Assert.assertEquals(RpcException.INVALID_REQUEST, errorCode(dispatcher.handleLine("[{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"echo\"}]")));
    }

    @Test
    public void paramsErrorsAreInvalidParams() {
        Assert.assertEquals(RpcException.INVALID_PARAMS, errorCode(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"add\",\"params\":{\"a\":1}}")));
        Assert.assertEquals(RpcException.INVALID_PARAMS,
                errorCode(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"add\",\"params\":{\"a\":1,\"b\":\"2\"}}")));
    }

    @Test
    public void exceptionBecomesInternal() {
        String line = dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"boom\"}");
        Assert.assertEquals(RpcException.INTERNAL, errorCode(line));
        Assert.assertTrue(line.contains("kaput"));
    }

    @Test
    public void rpcExceptionCodeIsKept() {
        Assert.assertEquals(RpcException.PAUSED, errorCode(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"busy\"}")));
    }

    @Test
    public void notificationReturnsNull() {
        Assert.assertNull(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"method\":\"echo\",\"params\":{\"value\":\"a\"}}"));
        Assert.assertNull(dispatcher.handleLine("{\"jsonrpc\":\"2.0\",\"method\":\"nope\"}"));
    }

    @Test
    public void blankLineIsIgnored() {
        Assert.assertNull(dispatcher.handleLine("   "));
    }
}
