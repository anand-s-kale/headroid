// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import com.genymobile.scrcpy.util.Ln;

import android.os.Build;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * Mutes apps under test so their sound and vibration do not reach the owner, by setting app-ops to {@code ignore} for
 * the package: the app keeps running as if it played them. Notifications are muted only on request, by revoking the
 * notification permission, because the app can see that (it may ask for the permission again). Text toasts need no
 * muting: SystemUI draws them on the app's display. The original modes are written to a file before they change, and restored when the
 * app is stopped, at teardown, or on the next server start if the server was killed before it could restore them.
 *
 * <p>App-ops are per package, not per display: while muted, the app is also silent if the owner opens it on display 0.
 */
public final class AppMuter {

    static final String[] OPS = {"PLAY_AUDIO", "VIBRATE"};
    /**
     * On Android 13+ the POST_NOTIFICATION app-op follows the runtime permission and an {@code appops set} is undone,
     * so notifications are muted by revoking the permission instead (recorded under this key, modes granted/revoked).
     */
    static final String NOTIFICATIONS = "permission:POST_NOTIFICATIONS";
    private static final String NOTIFICATIONS_PERMISSION = "android.permission.POST_NOTIFICATIONS";
    private static final File STATE_DIR = new File("/data/local/tmp");
    // one file per server process, so servers of different sessions never restore each other's apps
    private static final String STATE_PREFIX = "headroid-appops-";
    private static final long COMMAND_TIMEOUT_MS = 5000;

    private final AppOpsLedger ledger;
    private final File state;

    private AppMuter(AppOpsLedger ledger, File state) {
        this.ledger = ledger;
        this.state = state;
    }

    /**
     * Restores the modes left behind by servers that died before restoring them (their process is gone), then returns
     * the muter of this server.
     */
    public static AppMuter recover() {
        File[] files = STATE_DIR.listFiles((dir, name) -> name.startsWith(STATE_PREFIX) && name.endsWith(".txt"));
        if (files != null) {
            for (File file : files) {
                String pid = file.getName().substring(STATE_PREFIX.length(), file.getName().length() - 4);
                if (new File("/proc/" + pid).exists()) {
                    continue; // its server is still running and restores them itself
                }
                AppOpsLedger left = AppOpsLedger.parse(read(file));
                if (!left.isEmpty()) {
                    Ln.w("Restoring app-ops left by server " + pid + ": " + left.serialize().trim().replace('\n', ','));
                    new AppMuter(left, file).restoreAll();
                } else if (!file.delete()) {
                    Ln.w("Could not delete " + file);
                }
            }
        }
        return new AppMuter(new AppOpsLedger(), new File(STATE_DIR, STATE_PREFIX + android.os.Process.myPid() + ".txt"));
    }

    public void mute(String pkg, boolean notifications) {
        for (String op : OPS) {
            if (ledger.has(pkg, op)) {
                continue;
            }
            try {
                ledger.remember(pkg, op, AppOpsLedger.parseMode(op, run("cmd", "appops", "get", pkg, op)));
                // persist before changing anything, so a crash never leaves a mode we cannot undo
                write(state, ledger.serialize());
                run("cmd", "appops", "set", pkg, op, "ignore");
            } catch (IOException e) {
                Ln.w("Could not mute " + op + " for " + pkg + ": " + e.getMessage());
            }
        }
        if (notifications) {
            muteNotifications(pkg);
        }
    }

    private void muteNotifications(String pkg) {
        if (Build.VERSION.SDK_INT < 33 || ledger.has(pkg, NOTIFICATIONS)) {
            return;
        }
        try {
            String grant = AppOpsLedger.parsePermission(NOTIFICATIONS_PERMISSION, run("dumpsys", "package", pkg));
            if (!"granted".equals(grant)) {
                return; // not requested or already denied: nothing can reach the owner
            }
            if (isRunning(pkg)) {
                // revoking a runtime permission kills the app, which may be the owner's on display 0
                Ln.w("Not muting notifications of " + pkg + ": it is already running");
                return;
            }
            ledger.remember(pkg, NOTIFICATIONS, grant);
            write(state, ledger.serialize());
            run("pm", "revoke", pkg, NOTIFICATIONS_PERMISSION);
        } catch (IOException e) {
            Ln.w("Could not mute notifications of " + pkg + ": " + e.getMessage());
        }
    }

    static boolean isRunning(String pkg) throws IOException {
        try {
            return !run("pidof", pkg).trim().isEmpty();
        } catch (IOException e) {
            // pidof exits 1 when no process matches
            if (e.getMessage() != null && e.getMessage().contains(": exit 1")) {
                return false;
            }
            throw e;
        }
    }

    public void restore(String pkg) {
        report(ledger.restore(pkg, AppMuter::set));
        write(state, ledger.serialize());
    }

    public void restoreAll() {
        report(ledger.restoreAll(AppMuter::set));
        write(state, ledger.serialize());
    }

    private static void report(List<String> failures) {
        for (String failure : failures) {
            Ln.e("Could not restore app-op " + failure);
        }
    }

    private static void set(String pkg, String op, String mode) throws IOException {
        if (op.equals(NOTIFICATIONS)) {
            run("pm", "granted".equals(mode) ? "grant" : "revoke", pkg, NOTIFICATIONS_PERMISSION);
            return;
        }
        run("cmd", "appops", "set", pkg, op, mode);
    }

    static String run(String... cmd) throws IOException {
        Process process = new ProcessBuilder(cmd).redirectErrorStream(true).start();
        try {
            String out = readAll(process.getInputStream());
            if (!process.waitFor(COMMAND_TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                process.destroy();
                throw new IOException(String.join(" ", cmd) + ": timed out");
            }
            if (process.exitValue() != 0) {
                throw new IOException(String.join(" ", cmd) + ": exit " + process.exitValue() + ": " + out.trim());
            }
            return out;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException(String.join(" ", cmd) + ": interrupted");
        }
    }

    private static String readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) != -1) {
            out.write(buf, 0, n);
        }
        return out.toString(StandardCharsets.UTF_8.name());
    }

    private static String read(File file) {
        try {
            return new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        } catch (IOException e) {
            Ln.w("Could not read " + file + ": " + e.getMessage());
            return null;
        }
    }

    private static void write(File file, String text) {
        if (text.isEmpty()) {
            if (file.exists() && !file.delete()) {
                Ln.w("Could not delete " + file);
            }
            return;
        }
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        } catch (IOException e) {
            Ln.w("Could not write " + file + ": " + e.getMessage());
        }
    }
}
