// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import java.io.IOException;
import java.util.Collection;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Decides whether stopping an app would hurt someone else. A force-stop kills the app's process everywhere: the owner's
 * copy on display 0 (their music, their chat) and copies other sessions run on their own hidden displays. Pure logic
 * over {@code dumpsys activity activities} text, so it can be unit-tested.
 */
public final class AppPresence {

    private static final Pattern DISPLAY = Pattern.compile("^\\s*Display #(\\d+) ");

    private AppPresence() {
        // not instantiable
    }

    /** The displays that hold activities of {@code pkg}, from the activity history lines of the dump. */
    public static Set<Integer> displaysWithActivities(String dump, String pkg) {
        Set<Integer> result = new TreeSet<>();
        if (dump == null) {
            return result;
        }
        Pattern hist = Pattern.compile("^\\s*\\* Hist\\s+#\\d+: ActivityRecord\\{\\S+ u\\d+ " + Pattern.quote(pkg) + "/");
        Integer display = null;
        for (String line : dump.split("\n")) {
            Matcher m = DISPLAY.matcher(line);
            if (m.find()) {
                display = Integer.parseInt(m.group(1));
            } else if (display != null && hist.matcher(line).find()) {
                result.add(display);
            }
        }
        return result;
    }

    /**
     * Returns null when {@code pkg} may be force-stopped, or why not: it was already running before headroid launched it
     * (someone else's process), or it has activities on displays this session does not own.
     */
    public static String whyNotStop(boolean wasRunningBefore, Set<Integer> displaysWithActivities, Collection<Integer> ownDisplays) {
        if (wasRunningBefore) {
            return "it was already running before headroid launched it";
        }
        Set<Integer> others = new TreeSet<>(displaysWithActivities);
        others.removeAll(ownDisplays);
        if (!others.isEmpty()) {
            return "it is also open on display " + others;
        }
        return null;
    }

    /**
     * Whether someone is using the app right now: a process that is not merely cached (a cached process has no visible
     * activity and no running service, and Android may kill it at any time). Errors count as in use, so a failure never
     * leads to a force-stop.
     */
    public static boolean isRunning(String pkg) {
        try {
            Integer uid = parseUid(AppMuter.run("pm", "list", "packages", "-U", pkg), pkg);
            return uid == null || isInUse(AppMuter.run("am", "get-uid-state", String.valueOf(uid)));
        } catch (IOException e) {
            return true;
        }
    }

    /** The uid of {@code pkg} from {@code pm list packages -U} output (which also lists packages it is a prefix of). */
    static Integer parseUid(String output, String pkg) {
        Matcher m = Pattern.compile("^package:" + Pattern.quote(pkg) + " uid:(\\d+)", Pattern.MULTILINE).matcher(output);
        return m.find() ? Integer.parseInt(m.group(1)) : null;
    }

    /** From {@code am get-uid-state} output such as {@code "18 (CACHED_RECENT)"}: false when cached or not running. */
    static boolean isInUse(String output) {
        String state = output == null ? "" : output.trim();
        return !(state.contains("(CACHED") || state.contains("(NONEXISTENT)"));
    }

    /** The displays that hold activities of {@code pkg} right now. */
    public static Set<Integer> displaysWithActivities(String pkg) throws IOException {
        return displaysWithActivities(AppMuter.run("dumpsys", "activity", "activities"), pkg);
    }
}
