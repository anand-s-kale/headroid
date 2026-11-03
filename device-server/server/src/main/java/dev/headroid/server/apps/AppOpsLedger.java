// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Remembers the app-op modes headroid changed and what they were before, so they can be put back. Pure bookkeeping,
 * kept apart from the shell calls so it can be unit-tested. Serialized as lines {@code package op mode} so a server
 * killed before teardown can restore them on its next start.
 */
public final class AppOpsLedger {

    /** Applies one app-op mode. */
    public interface Setter {
        void set(String pkg, String op, String mode) throws Exception;
    }

    // package -> (op -> original mode)
    private final Map<String, Map<String, String>> originals = new LinkedHashMap<>();

    /** Records the original mode of an op, unless it was already recorded (the first value is the owner's). */
    public synchronized void remember(String pkg, String op, String originalMode) {
        originals.computeIfAbsent(pkg, k -> new LinkedHashMap<>()).putIfAbsent(op, originalMode);
    }

    public synchronized boolean has(String pkg, String op) {
        Map<String, String> ops = originals.get(pkg);
        return ops != null && ops.containsKey(op);
    }

    public synchronized boolean isEmpty() {
        return originals.isEmpty();
    }

    /**
     * Restores the original modes of one package and forgets them. Entries that fail to restore are kept, so a later
     * attempt (or the next server start) can retry. Returns the failures as {@code "op: message"}.
     */
    public List<String> restore(String pkg, Setter setter) {
        Map<String, String> ops;
        synchronized (this) {
            ops = originals.get(pkg);
            if (ops == null) {
                return new ArrayList<>();
            }
            ops = new LinkedHashMap<>(ops);
        }
        List<String> failures = new ArrayList<>();
        for (Map.Entry<String, String> e : ops.entrySet()) {
            try {
                setter.set(pkg, e.getKey(), e.getValue());
                synchronized (this) {
                    Map<String, String> current = originals.get(pkg);
                    if (current != null) {
                        current.remove(e.getKey());
                        if (current.isEmpty()) {
                            originals.remove(pkg);
                        }
                    }
                }
            } catch (Exception ex) {
                failures.add(e.getKey() + ": " + ex.getMessage());
            }
        }
        return failures;
    }

    /** Restores every package. Returns the failures as {@code "package op: message"}. */
    public List<String> restoreAll(Setter setter) {
        List<String> packages;
        synchronized (this) {
            packages = new ArrayList<>(originals.keySet());
        }
        List<String> failures = new ArrayList<>();
        for (String pkg : packages) {
            for (String failure : restore(pkg, setter)) {
                failures.add(pkg + " " + failure);
            }
        }
        return failures;
    }

    public synchronized String serialize() {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, Map<String, String>> p : originals.entrySet()) {
            for (Map.Entry<String, String> o : p.getValue().entrySet()) {
                sb.append(p.getKey()).append(' ').append(o.getKey()).append(' ').append(o.getValue()).append('\n');
            }
        }
        return sb.toString();
    }

    public static AppOpsLedger parse(String text) {
        AppOpsLedger ledger = new AppOpsLedger();
        if (text == null) {
            return ledger;
        }
        for (String line : text.split("\n")) {
            String[] parts = line.trim().split("\\s+");
            if (parts.length == 3) {
                ledger.remember(parts[0], parts[1], parts[2]);
            }
        }
        return ledger;
    }

    /**
     * Reads the package-level mode of {@code op} from {@code cmd appops get <pkg> <op>} output, or {@code "default"}
     * when the package has no explicit mode for it. Uid-level lines ({@code Uid mode: ...}) are ignored: headroid only
     * sets package modes.
     */
    public static String parseMode(String op, String output) {
        if (output != null) {
            for (String line : output.split("\n")) {
                String t = line.trim();
                if (t.startsWith(op + ":")) {
                    String rest = t.substring(op.length() + 1).trim();
                    int end = rest.indexOf(';');
                    String mode = (end >= 0 ? rest.substring(0, end) : rest).trim();
                    if (!mode.isEmpty()) {
                        return mode;
                    }
                }
            }
        }
        return "default";
    }

    /**
     * Reads a runtime permission from {@code dumpsys package <pkg>} output: {@code "granted"}, {@code "revoked"}, or
     * null when the package does not request it.
     */
    public static String parsePermission(String permission, String output) {
        if (output != null) {
            for (String line : output.split("\n")) {
                String t = line.trim();
                if (t.startsWith(permission + ": granted=")) {
                    return t.startsWith(permission + ": granted=true") ? "granted" : "revoked";
                }
            }
        }
        return null;
    }
}
