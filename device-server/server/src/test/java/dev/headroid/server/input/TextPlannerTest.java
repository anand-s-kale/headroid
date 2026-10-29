// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.input;

import org.junit.Assert;
import org.junit.Test;

import java.util.function.Function;

public class TextPlannerTest {

    // Fake key map: ASCII only, two events per char, null for anything else (like KeyCharacterMap.getEvents)
    private static final Function<char[], String[]> ASCII_MAP = chars -> {
        String[] events = new String[chars.length * 2];
        for (int i = 0; i < chars.length; i++) {
            if (chars[i] > 0x7e) {
                return null;
            }
            events[2 * i] = "down:" + chars[i];
            events[2 * i + 1] = "up:" + chars[i];
        }
        return events;
    };

    @Test
    public void asciiUsesKeys() {
        TextPlanner.Plan<String> plan = TextPlanner.plan("hi", ASCII_MAP);
        Assert.assertFalse(plan.useSetText);
        Assert.assertArrayEquals(new String[] {"down:h", "up:h", "down:i", "up:i"}, plan.events);
    }

    @Test
    public void nonAsciiUsesSetText() {
        TextPlanner.Plan<String> plan = TextPlanner.plan("héllo 😀", ASCII_MAP);
        Assert.assertTrue(plan.useSetText);
        Assert.assertNull(plan.events);
    }

    @Test
    public void emptyTextDoesNothing() {
        TextPlanner.Plan<String> plan = TextPlanner.plan("", ASCII_MAP);
        Assert.assertFalse(plan.useSetText);
        Assert.assertNull(plan.events);
    }
}
