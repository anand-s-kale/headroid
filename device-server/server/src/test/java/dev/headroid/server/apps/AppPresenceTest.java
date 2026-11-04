// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import org.junit.Assert;
import org.junit.Test;

import java.io.IOException;
import java.util.List;
import java.util.Set;

public class AppPresenceTest {

    // trimmed from a POCO F6 (Android 16) dump
    private static final String DUMP = String.join("\n",
            "Display #0 (activities from top to bottom):",
            "  * Task{a1 #12 type=standard A=10200:com.owner.music U=0 visible=true}",
            "    * Hist  #0: ActivityRecord{11 u0 com.owner.music/.Player t12}",
            "Display #40 (activities from top to bottom):",
            "  * Task{cf573f3 #4943 type=standard A=10814:dev.headroid.sample U=0 visible=true}",
            "    topResumedActivity=ActivityRecord{231381335 u0 dev.headroid.sample/.MainActivity t4943}",
            "    * Hist  #1: ActivityRecord{231381336 u0 dev.headroid.sample/.LoginActivity t4943}",
            "    * Hist  #0: ActivityRecord{231381335 u0 dev.headroid.sample/.MainActivity t4943}",
            "Display #41 (activities from top to bottom):",
            "    * Hist  #0: ActivityRecord{77 u0 com.owner.music/.Player t50}",
            "  mCurrentFocus=Window{e7de539 u0 dev.headroid.sample/dev.headroid.sample.MainActivity}",
            "  ResumedActivity: ActivityRecord{11 u0 com.owner.music/.Player t12}");

    @Test
    public void findsDisplaysFromHistoryLinesOnly() throws IOException {
        Assert.assertEquals(Set.of(40), AppPresence.displaysWithActivities(DUMP, "dev.headroid.sample"));
        Assert.assertEquals(Set.of(0, 41), AppPresence.displaysWithActivities(DUMP, "com.owner.music"));
        Assert.assertTrue(AppPresence.displaysWithActivities(DUMP, "com.owner").isEmpty());
    }

    @Test
    public void validDumpWithoutThePackageIsEmpty() throws IOException {
        // headers present, no history lines of the package: it is not open anywhere, so a launch is allowed
        String dump = String.join("\n",
                "Display #0 (activities from top to bottom):",
                "  * Task{a1 #12 type=home A=10100:com.miui.home U=0 visible=true}",
                "    * Hist  #0: ActivityRecord{11 u0 com.miui.home/.launcher.Launcher t12}");
        Assert.assertTrue(AppPresence.displaysWithActivities(dump, "com.android.chrome").isEmpty());
    }

    @Test
    public void dumpWithoutAnyDisplayHeaderFailsClosed() {
        // an unknown format must not read as "not open anywhere": LaunchGuard would let the launch through
        String[] dumps = {
            null,
            "",
            "Can't find service: activity",
            "ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\n"
                    + "    * Hist  #0: ActivityRecord{11 u0 com.owner.music/.Player t12}",
            "Screen #0 (activities from top to bottom):\n    * Hist  #0: ActivityRecord{11 u0 a.b/.C t1}",
        };
        for (String dump : dumps) {
            try {
                AppPresence.displaysWithActivities(dump, "com.owner.music");
                Assert.fail("no exception for " + dump);
            } catch (IOException e) {
                Assert.assertTrue(e.getMessage(), e.getMessage().contains("cannot tell where com.owner.music runs"));
            }
        }
    }

    @Test
    public void cachedProcessesAreNotInUse() {
        Assert.assertFalse(AppPresence.isInUse("18 (CACHED_RECENT)\n"));
        Assert.assertFalse(AppPresence.isInUse("19 (CACHED_EMPTY)"));
        Assert.assertFalse(AppPresence.isInUse("20 (NONEXISTENT)"));
        Assert.assertTrue(AppPresence.isInUse("4 (FOREGROUND_SERVICE)"));
        Assert.assertTrue(AppPresence.isInUse("2 (TOP)"));
    }

    @Test
    public void uidOfExactPackage() {
        String out = "package:com.android.systemui.overlay.common uid:10070\npackage:com.android.systemui uid:1000,99901000\n";
        Assert.assertEquals(Integer.valueOf(1000), AppPresence.parseUid(out, "com.android.systemui"));
        Assert.assertEquals(Integer.valueOf(10070), AppPresence.parseUid(out, "com.android.systemui.overlay.common"));
        Assert.assertNull(AppPresence.parseUid(out, "com.android"));
    }

    @Test
    public void stopsOnlyWhatHeadroidStartedAndOnlyUses() {
        Assert.assertNull(AppPresence.whyNotStop(false, Set.of(40), List.of(40)));
        Assert.assertNull(AppPresence.whyNotStop(false, Set.of(), List.of(40)));
        Assert.assertEquals("it was already running before headroid launched it",
                AppPresence.whyNotStop(true, Set.of(40), List.of(40)));
        Assert.assertEquals("it is also open on display [0]", AppPresence.whyNotStop(false, Set.of(0, 40), List.of(40)));
    }
}
