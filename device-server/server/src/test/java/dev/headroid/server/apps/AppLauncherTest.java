// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class AppLauncherTest {

    // Intent.FLAG_ACTIVITY_* values (AOSP)
    private static final int NEW_TASK = 0x10000000;
    private static final int MULTIPLE_TASK = 0x08000000;
    private static final int EXCLUDE_FROM_RECENTS = 0x00800000;

    @Test
    public void launchesInOwnTaskHiddenFromRecents() {
        // without EXCLUDE_FROM_RECENTS every session left an entry in the owner's Recents, and tapping it opened the
        // app under test on the owner's screen (POCO F6, 2026-11-04)
        assertEquals(NEW_TASK | MULTIPLE_TASK | EXCLUDE_FROM_RECENTS, AppLauncher.LAUNCH_FLAGS);
    }
}
