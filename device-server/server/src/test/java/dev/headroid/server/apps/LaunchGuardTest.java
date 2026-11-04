// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.List;
import java.util.Set;

public class LaunchGuardTest {

    // ActivityInfo.LAUNCH_* values (AOSP)
    private static final int STANDARD = 0;
    private static final int SINGLE_TOP = 1;
    private static final int SINGLE_TASK = 2;
    private static final int SINGLE_INSTANCE = 3;
    private static final int SINGLE_INSTANCE_PER_TASK = 4;

    private static final List<Integer> OWN = List.of(40, 41);

    @Test
    public void launchModesThatReuseATask() {
        assertFalse(LaunchGuard.reusesTask(STANDARD));
        assertFalse(LaunchGuard.reusesTask(SINGLE_TOP));
        assertTrue(LaunchGuard.reusesTask(SINGLE_TASK));
        assertTrue(LaunchGuard.reusesTask(SINGLE_INSTANCE));
        assertTrue(LaunchGuard.reusesTask(SINGLE_INSTANCE_PER_TASK));
    }

    @Test
    public void openUrlRefusedWhileTheAppIsOpenOnAForeignDisplay() {
        // a trampoline (Chrome's IntentDispatcher) starts the real activity itself, into the owner's task on display 0
        assertEquals("url: com.android.chrome is open on display [0]; close it on the phone first",
                LaunchGuard.whyNotOpenUrl("com.android.chrome", Set.of(0, 40), OWN));
        assertEquals("url: a.b is open on display [7]; close it on the phone first",
                LaunchGuard.whyNotOpenUrl("a.b", Set.of(7), OWN));
    }

    @Test
    public void openUrlAllowedOnOwnDisplaysOnly() {
        // any foreign activity refuses, whatever the handler's launch mode, so singleTask needs no separate rule here
        assertNull(LaunchGuard.whyNotOpenUrl("a.b", Set.of(), OWN));
        assertNull(LaunchGuard.whyNotOpenUrl("a.b", Set.of(40, 41), OWN));
    }

    @Test
    public void launchOfAStandardActivityStaysAllowedWhileTheOwnerUsesTheApp() {
        // FLAG_ACTIVITY_MULTIPLE_TASK gives it a new task on the hidden display
        assertNull(LaunchGuard.whyNotLaunch("a.b", STANDARD, Set.of(0), OWN));
        assertNull(LaunchGuard.whyNotLaunch("a.b", SINGLE_TOP, Set.of(0), OWN));
    }

    @Test
    public void launchOfATaskReusingActivityRefusedWhileOpenOnAForeignDisplay() {
        for (int mode : new int[] {SINGLE_TASK, SINGLE_INSTANCE, SINGLE_INSTANCE_PER_TASK}) {
            String why = LaunchGuard.whyNotLaunch("a.b", mode, Set.of(0, 40), OWN);
            assertTrue(why, why.startsWith("package: a.b is open on display [0]"));
            assertTrue(why, why.endsWith("close it on the phone first"));
        }
    }

    @Test
    public void launchOfATaskReusingActivityAllowedOnOwnDisplays() {
        for (int mode : new int[] {SINGLE_TASK, SINGLE_INSTANCE, SINGLE_INSTANCE_PER_TASK}) {
            assertNull(LaunchGuard.whyNotLaunch("a.b", mode, Set.of(), OWN));
            assertNull(LaunchGuard.whyNotLaunch("a.b", mode, Set.of(41), OWN));
        }
    }
}
