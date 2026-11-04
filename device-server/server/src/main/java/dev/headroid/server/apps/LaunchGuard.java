// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import java.util.Collection;
import java.util.Set;
import java.util.TreeSet;

/**
 * Decides whether a launch could land in someone else's task, which may sit on the owner's display 0.
 * FLAG_ACTIVITY_MULTIPLE_TASK only helps for standard activities: singleTask, singleInstance and singleInstancePerTask
 * activities reuse their existing task whatever the flags, and a link handler may be a trampoline that starts the real
 * activity itself (Chrome's IntentDispatcher, deep-link routers). Pure logic, so it can be unit-tested.
 */
public final class LaunchGuard {

    // ActivityInfo.LAUNCH_SINGLE_TASK, LAUNCH_SINGLE_INSTANCE, LAUNCH_SINGLE_INSTANCE_PER_TASK (API 31)
    private static final int SINGLE_TASK = 2;
    private static final int SINGLE_INSTANCE = 3;
    private static final int SINGLE_INSTANCE_PER_TASK = 4;

    private LaunchGuard() {
        // not instantiable
    }

    /** Whether an activity of this launch mode reuses an existing task instead of starting a new one. */
    public static boolean reusesTask(int launchMode) {
        return launchMode == SINGLE_TASK || launchMode == SINGLE_INSTANCE || launchMode == SINGLE_INSTANCE_PER_TASK;
    }

    /**
     * Null when {@code pkg} may open a link on a hidden display, else why not. Any activity of the package on a display
     * this session does not own refuses: the handler may hand the link on to an activity in that task, whatever its own
     * launch mode, so this also covers singleTask and singleInstance handlers.
     */
    public static String whyNotOpenUrl(String pkg, Set<Integer> displaysWithActivities, Collection<Integer> ownDisplays) {
        Set<Integer> others = foreign(displaysWithActivities, ownDisplays);
        return others.isEmpty() ? null : "url: " + pkg + " is open on display " + others + "; close it on the phone first";
    }

    /**
     * Null when the activity of {@code pkg} with {@code launchMode} may be launched on a hidden display, else why not.
     * A standard activity always may (it gets a new task); a task-reusing one only when the package has no activities on
     * a display this session does not own.
     */
    public static String whyNotLaunch(String pkg, int launchMode, Set<Integer> displaysWithActivities, Collection<Integer> ownDisplays) {
        if (!reusesTask(launchMode)) {
            return null;
        }
        Set<Integer> others = foreign(displaysWithActivities, ownDisplays);
        return others.isEmpty() ? null : "package: " + pkg + " is open on display " + others
                + " and its activity is singleTask/singleInstance, so it would reuse that task instead of opening on the"
                + " hidden display; close it on the phone first";
    }

    private static Set<Integer> foreign(Set<Integer> displaysWithActivities, Collection<Integer> ownDisplays) {
        Set<Integer> others = new TreeSet<>(displaysWithActivities);
        others.removeAll(ownDisplays);
        return others;
    }
}
