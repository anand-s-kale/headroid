// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

import org.junit.Assert;
import org.junit.Test;

public class DisplayFlagsTest {

    private static boolean has(int flags, int bit) {
        return (flags & (1 << bit)) != 0;
    }

    @Test
    public void api34HasStealTopFocusDisabled() {
        int flags = DisplayFlags.forSdk(34);
        Assert.assertTrue(has(flags, 16)); // STEAL_TOP_FOCUS_DISABLED
        Assert.assertTrue(has(flags, 14)); // OWN_FOCUS
        Assert.assertTrue(has(flags, 8)); // DESTROY_CONTENT_ON_REMOVAL
        Assert.assertTrue(has(flags, 10)); // TRUSTED
        Assert.assertTrue(has(flags, 13)); // TOUCH_FEEDBACK_DISABLED
        Assert.assertFalse(has(flags, 9)); // never SHOULD_SHOW_SYSTEM_DECORATIONS
        Assert.assertEquals(DisplayFlags.forSdk(34), DisplayFlags.forSdk(36));
    }

    @Test
    public void api33HasNoOwnFocus() {
        int flags = DisplayFlags.forSdk(33);
        Assert.assertTrue(has(flags, 10));
        Assert.assertTrue(has(flags, 12)); // ALWAYS_UNLOCKED
        Assert.assertFalse(has(flags, 14));
        Assert.assertFalse(has(flags, 16));
    }

    @Test
    public void api30Minimal() {
        int flags = DisplayFlags.forSdk(30);
        Assert.assertEquals(DisplayFlags.PUBLIC | DisplayFlags.PRESENTATION | DisplayFlags.OWN_CONTENT_ONLY | DisplayFlags.SUPPORTS_TOUCH
                | DisplayFlags.ROTATES_WITH_CONTENT | DisplayFlags.DESTROY_CONTENT_ON_REMOVAL, flags);
    }

    @Test
    public void describeNamesFlags() {
        Assert.assertTrue(DisplayFlags.describe(DisplayFlags.forSdk(34)).contains("STEAL_TOP_FOCUS_DISABLED"));
    }
}
