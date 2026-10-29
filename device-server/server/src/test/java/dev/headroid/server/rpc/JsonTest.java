// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

import org.junit.Assert;
import org.junit.Test;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class JsonTest {

    @Test
    public void roundTripsNestedValues() {
        String text = "{\"a\":1,\"b\":[true,false,null,2.5,\"x\"],\"c\":{\"d\":-3}}";
        Object parsed = Json.parse(text);
        Assert.assertEquals(text, Json.write(parsed));

        @SuppressWarnings("unchecked")
        Map<String, Object> map = (Map<String, Object>) parsed;
        Assert.assertEquals(1L, map.get("a"));
        List<?> b = (List<?>) map.get("b");
        Assert.assertEquals(Arrays.asList(true, false, null, 2.5, "x"), b);
    }

    @Test
    public void parsesEscapesAndUnicode() {
        Object parsed = Json.parse("\"a\\\"b\\\\c\\n\\u00e9\\ud83d\\ude00\"");
        Assert.assertEquals("a\"b\\c\né😀", parsed);
        // control characters are escaped, non-ASCII is written as-is (UTF-8 on the wire)
        Assert.assertEquals("\"\\n\\u0001é\"", Json.write("\n\u0001é"));
    }

    @Test
    public void parsesNumbers() {
        Assert.assertEquals(0L, Json.parse("0"));
        Assert.assertEquals(-12L, Json.parse("-12"));
        Assert.assertEquals(1.5e3, Json.parse("1.5e3"));
        Assert.assertEquals(9007199254740993L, Json.parse("9007199254740993"));
    }

    @Test(expected = Json.JsonException.class)
    public void rejectsTrailingGarbage() {
        Json.parse("{\"a\":1} x");
    }

    @Test(expected = Json.JsonException.class)
    public void rejectsUnterminatedString() {
        Json.parse("\"abc");
    }

    @Test(expected = Json.JsonException.class)
    public void rejectsTooDeepNesting() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 1000; i++) {
            sb.append('[');
        }
        Json.parse(sb.toString());
    }

    @Test
    public void writesNonFiniteAsNull() {
        Assert.assertEquals("[null,null]", Json.write(Arrays.asList(Double.NaN, Double.POSITIVE_INFINITY)));
    }

    @Test
    public void writesPrimitiveArraysAndInts() {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("bounds", new int[] {1, 2, 3, 4});
        map.put("n", 7);
        map.put("f", 0.5f);
        Assert.assertEquals("{\"bounds\":[1,2,3,4],\"n\":7,\"f\":0.5}", Json.write(map));
    }
}
