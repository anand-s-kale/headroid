// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.session;

import org.junit.Assert;
import org.junit.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class WatchdogTest {

    static final class FakeScheduler implements Watchdog.Scheduler {
        final List<Runnable> pending = new ArrayList<>();
        final List<Long> delays = new ArrayList<>();

        @Override
        public Watchdog.Cancellable schedule(Runnable task, long delayMs) {
            pending.add(task);
            delays.add(delayMs);
            return () -> pending.remove(task);
        }

        void runAll() {
            for (Runnable r : new ArrayList<>(pending)) {
                pending.remove(r);
                r.run();
            }
        }
    }

    @Test
    public void teardownRunsAfterGrace() {
        FakeScheduler scheduler = new FakeScheduler();
        int[] teardowns = {0};
        Watchdog watchdog = new Watchdog(scheduler, 15000, () -> teardowns[0]++);
        watchdog.onConnect();
        watchdog.onDisconnect();
        Assert.assertEquals(Collections.singletonList(15000L), scheduler.delays);
        Assert.assertEquals(0, teardowns[0]);
        scheduler.runAll();
        Assert.assertEquals(1, teardowns[0]);
    }

    @Test
    public void reconnectCancelsTeardown() {
        FakeScheduler scheduler = new FakeScheduler();
        int[] teardowns = {0};
        Watchdog watchdog = new Watchdog(scheduler, 15000, () -> teardowns[0]++);
        watchdog.onDisconnect();
        watchdog.onConnect();
        scheduler.runAll();
        Assert.assertEquals(0, teardowns[0]);
    }

    @Test
    public void teardownRunsOnce() {
        FakeScheduler scheduler = new FakeScheduler();
        int[] teardowns = {0};
        Watchdog watchdog = new Watchdog(scheduler, 1000, () -> teardowns[0]++);
        watchdog.onDisconnect();
        watchdog.onDisconnect(); // a second disconnect does not schedule a second teardown
        Assert.assertEquals(1, scheduler.pending.size());
        scheduler.runAll();
        watchdog.teardownNow(); // nothing new since the last teardown
        Assert.assertEquals(1, teardowns[0]);
    }

    @Test
    public void zeroGraceTearsDownImmediately() {
        FakeScheduler scheduler = new FakeScheduler();
        int[] teardowns = {0};
        Watchdog watchdog = new Watchdog(scheduler, 0, () -> teardowns[0]++);
        watchdog.onConnect();
        watchdog.onDisconnect();
        Assert.assertEquals(1, teardowns[0]);
        Assert.assertTrue(scheduler.pending.isEmpty());
    }

    @Test
    public void newSessionAfterTeardownCanTearDownAgain() {
        FakeScheduler scheduler = new FakeScheduler();
        int[] teardowns = {0};
        Watchdog watchdog = new Watchdog(scheduler, 10, () -> teardowns[0]++);
        watchdog.onConnect();
        watchdog.onDisconnect();
        scheduler.runAll();
        watchdog.onConnect();
        watchdog.onDisconnect();
        scheduler.runAll();
        Assert.assertEquals(2, teardowns[0]);
    }
}
