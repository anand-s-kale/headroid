// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import org.junit.Assert;
import org.junit.Test;

import java.util.ArrayList;
import java.util.List;

public class AppOpsLedgerTest {

    @Test
    public void restoresOriginalModes() {
        AppOpsLedger ledger = new AppOpsLedger();
        ledger.remember("a.b", "PLAY_AUDIO", "default");
        ledger.remember("a.b", "VIBRATE", "allow");
        List<String> calls = new ArrayList<>();
        Assert.assertTrue(ledger.restoreAll((pkg, op, mode) -> calls.add(pkg + " " + op + " " + mode)).isEmpty());
        Assert.assertEquals(List.of("a.b PLAY_AUDIO default", "a.b VIBRATE allow"), calls);
        Assert.assertTrue(ledger.isEmpty());
    }

    @Test
    public void firstOriginalWins() {
        // a second launch sees the mode headroid set ("ignore"); the owner's mode is the first one
        AppOpsLedger ledger = new AppOpsLedger();
        ledger.remember("a.b", "PLAY_AUDIO", "allow");
        ledger.remember("a.b", "PLAY_AUDIO", "ignore");
        Assert.assertEquals("a.b PLAY_AUDIO allow\n", ledger.serialize());
    }

    @Test
    public void failedRestoreIsKeptForRetry() {
        AppOpsLedger ledger = new AppOpsLedger();
        ledger.remember("a.b", "PLAY_AUDIO", "default");
        ledger.remember("a.b", "VIBRATE", "default");
        List<String> failures = ledger.restore("a.b", (pkg, op, mode) -> {
            if (op.equals("VIBRATE")) {
                throw new IllegalStateException("boom");
            }
        });
        Assert.assertEquals(List.of("VIBRATE: boom"), failures);
        Assert.assertEquals("a.b VIBRATE default\n", ledger.serialize());
    }

    @Test
    public void serializeRoundTrip() {
        AppOpsLedger ledger = new AppOpsLedger();
        ledger.remember("a.b", "PLAY_AUDIO", "default");
        ledger.remember("c.d", "POST_NOTIFICATION", "allow");
        AppOpsLedger copy = AppOpsLedger.parse(ledger.serialize() + "\ngarbage line here x\n");
        Assert.assertEquals(ledger.serialize(), copy.serialize());
        Assert.assertTrue(AppOpsLedger.parse(null).isEmpty());
    }

    @Test
    public void parseModeReadsPackageLine() {
        Assert.assertEquals("allow", AppOpsLedger.parseMode("PLAY_AUDIO", "PLAY_AUDIO: allow; time=+1m2s ago\n"));
        Assert.assertEquals("ignore", AppOpsLedger.parseMode("VIBRATE", "Uid mode: VIBRATE: allow\nVIBRATE: ignore\n"));
        Assert.assertEquals("default", AppOpsLedger.parseMode("VIBRATE", "Uid mode: VIBRATE: allow\n"));
        Assert.assertEquals("default", AppOpsLedger.parseMode("PLAY_AUDIO", "No operations.\n"));
    }

    @Test
    public void parsePermissionReadsRuntimeGrant() {
        String perm = "android.permission.POST_NOTIFICATIONS";
        String dump = "    requested permissions:\n      android.permission.POST_NOTIFICATIONS\n"
                + "        android.permission.POST_NOTIFICATIONS: granted=true, flags=[ USER_SENSITIVE_WHEN_GRANTED]\n";
        Assert.assertEquals("granted", AppOpsLedger.parsePermission(perm, dump));
        Assert.assertEquals("revoked", AppOpsLedger.parsePermission(perm, perm + ": granted=false, flags=[ ]"));
        Assert.assertNull(AppOpsLedger.parsePermission(perm, "android.permission.CAMERA: granted=true"));
    }
}
