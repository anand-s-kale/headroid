// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import java.io.IOException;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Xiaomi HyperOS freezes background apps about 20 s after the screen turns off ({@code GreezeManager}, service
 * {@code greezer}), and an app shown only on a virtual display counts as background. A frozen app stops running and
 * drawing, so its UI tree comes back empty while Android's own records still say it is resumed and not frozen
 * (POCO F6, 2026-11-04). The owner can exempt the app with Battery saver "No restrictions". Parsing is pure logic so it
 * can be unit-tested; {@link #frozenPackage} runs the commands.
 */
public final class HyperOsFreezer {

    private static final Pattern FROZEN = Pattern.compile("^Frozen processes:\\[([^\\]]*)\\]", Pattern.MULTILINE);

    private HyperOsFreezer() {
        // not instantiable
    }

    /** The pids in the "Frozen processes" line of {@code dumpsys greezer}; empty on phones without it. */
    static Set<Integer> frozenPids(String dump) {
        Set<Integer> result = new TreeSet<>();
        Matcher m = dump == null ? null : FROZEN.matcher(dump);
        if (m == null || !m.find()) {
            return result;
        }
        for (String pid : m.group(1).split(",")) {
            pid = pid.trim();
            if (!pid.isEmpty()) {
                result.add(Integer.parseInt(pid));
            }
        }
        return result;
    }

    /** The first package with a frozen process, given each package's {@code pidof} output, or null. */
    static String firstFrozen(Set<Integer> frozen, Map<String, String> pidofByPackage) {
        for (Map.Entry<String, String> e : pidofByPackage.entrySet()) {
            for (String pid : e.getValue().trim().split("\\s+")) {
                if (!pid.isEmpty() && frozen.contains(Integer.parseInt(pid))) {
                    return e.getKey();
                }
            }
        }
        return null;
    }

    public static String frozenMessage(String pkg) {
        return pkg + " is frozen by HyperOS (GreezeManager) because the phone's screen is off. On the phone open Settings > Apps > "
                + pkg + " > Battery saver and choose \"No restrictions\", or keep the screen on";
    }

    /** The first of {@code packages} that HyperOS has frozen right now, or null (also on other phones and on errors). */
    public static String frozenPackage(Collection<String> packages) {
        if (packages.isEmpty()) {
            return null;
        }
        try {
            Set<Integer> frozen = frozenPids(AppMuter.run("dumpsys", "greezer"));
            if (frozen.isEmpty()) {
                return null;
            }
            Map<String, String> pids = new LinkedHashMap<>();
            for (String pkg : packages) {
                try {
                    pids.put(pkg, AppMuter.run("pidof", pkg));
                } catch (IOException e) {
                    // pidof exits 1 when the app is not running
                    pids.put(pkg, "");
                }
            }
            return firstFrozen(frozen, pids);
        } catch (IOException | NumberFormatException e) {
            return null;
        }
    }
}
