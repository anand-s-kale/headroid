// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

import org.junit.Assert;
import org.junit.Test;

import java.util.Map;

public class ParamsTest {

    @SuppressWarnings("unchecked")
    private static Params params(String json) {
        return new Params((Map<String, Object>) Json.parse(json));
    }

    @Test
    public void readsTypedValues() {
        Params p = params("{\"i\":3,\"d\":2.5,\"s\":\"x\",\"b\":true,\"n\":null,\"f\":4.0}");
        Assert.assertEquals(3, p.getInt("i"));
        Assert.assertEquals(2.5, p.getDouble("d"), 0);
        Assert.assertEquals(3.0, p.getDouble("i"), 0);
        Assert.assertEquals(4, p.getInt("f")); // integral doubles are accepted as ints
        Assert.assertEquals("x", p.getString("s"));
        Assert.assertTrue(p.optBool("b", false));
        Assert.assertNull(p.optString("n", null));
        Assert.assertEquals(9, p.optInt("missing", 9));
        Assert.assertEquals("def", p.optString("missing", "def"));
    }

    private static void assertInvalid(Runnable r) {
        try {
            r.run();
            Assert.fail("expected RpcException");
        } catch (RpcException e) {
            Assert.assertEquals(RpcException.INVALID_PARAMS, e.getCode());
        }
    }

    @Test
    public void wrongOrMissingTypesAreInvalidParams() {
        Params p = params("{\"s\":\"x\",\"d\":2.5,\"big\":10000000000}");
        assertInvalid(() -> p.getInt("s"));
        assertInvalid(() -> p.getInt("d"));
        assertInvalid(() -> p.getInt("big"));
        assertInvalid(() -> p.getString("missing"));
        assertInvalid(() -> p.getInt("missing"));
        assertInvalid(() -> p.optBool("s", false));
    }

    @Test
    public void emptyParamsWhenNull() {
        Params p = new Params(null);
        Assert.assertEquals(1, p.optInt("x", 1));
    }
}
