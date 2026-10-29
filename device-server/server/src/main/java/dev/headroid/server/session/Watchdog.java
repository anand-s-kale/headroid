// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.session;

/**
 * Runs the session teardown when the host goes away. A short grace period lets a host that lost Wi-Fi for a moment
 * reconnect and keep its displays; after it, apps are stopped and displays released.
 */
public final class Watchdog {

    public interface Cancellable {
        void cancel();
    }

    public interface Scheduler {
        Cancellable schedule(Runnable task, long delayMs);
    }

    private final Scheduler scheduler;
    private final long graceMs;
    private final Runnable teardown;

    private Cancellable pending;
    private boolean tornDown;

    public Watchdog(Scheduler scheduler, long graceMs, Runnable teardown) {
        this.scheduler = scheduler;
        this.graceMs = graceMs;
        this.teardown = teardown;
    }

    public synchronized void onConnect() {
        if (pending != null) {
            pending.cancel();
            pending = null;
        }
        tornDown = false;
    }

    public void onDisconnect() {
        synchronized (this) {
            if (tornDown || pending != null) {
                return;
            }
            if (graceMs > 0) {
                pending = scheduler.schedule(this::onGraceExpired, graceMs);
                return;
            }
        }
        teardownNow();
    }

    private void onGraceExpired() {
        synchronized (this) {
            pending = null;
        }
        teardownNow();
    }

    /** Tears down at once (shutdown request, process exit). Does nothing if nothing happened since the last teardown. */
    public void teardownNow() {
        synchronized (this) {
            if (pending != null) {
                pending.cancel();
                pending = null;
            }
            if (tornDown) {
                return;
            }
            tornDown = true;
        }
        teardown.run();
    }
}
