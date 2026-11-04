// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.ui;

import org.junit.Assert;
import org.junit.Test;

public class FocusedTextTest {

    @Test
    public void appendsToTheCurrentText() {
        Assert.assertEquals("abcdé", FocusedText.value("abc", false, "dé", false));
    }

    @Test
    public void hintIsNotContent() {
        Assert.assertEquals("dé", FocusedText.value("Email", true, "dé", false));
        Assert.assertEquals("dé", FocusedText.value(null, false, "dé", false));
    }

    @Test
    public void replaceWithEmptyClears() {
        Assert.assertEquals("", FocusedText.value("abc", false, "", true));
        Assert.assertEquals("x", FocusedText.value("abc", false, "x", true));
    }
}
