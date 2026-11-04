// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;

public class HyperOsFreezerTest {

    // trimmed `dumpsys greezer` from a POCO F6 (HyperOS, Android 16)
    private static final String DUMP = "Settings:\n"
            + "  enable=true (persist.sys.powmillet.enable)\n"
            + "  fz_timeout=5000 (persist.sys.gz.fztimeout)\n"
            + "Frozen processes:[1079, 2617, 6394, 11456, 30074]\n"
            + "Greezer History : \n"
            + "2026-11-03T21:10:51.550870 - FZ uid = 10313 pid = [ 6249 ]  reason : PACKET caller : 1\n";

    @Test
    public void parsesFrozenPids() {
        assertEquals(new HashSet<>(Arrays.asList(1079, 2617, 6394, 11456, 30074)), HyperOsFreezer.frozenPids(DUMP));
    }

    @Test
    public void noGreezerMeansNothingFrozen() {
        // other vendors: the service does not exist and dumpsys prints an error
        assertTrue(HyperOsFreezer.frozenPids("Can't find service: greezer\n").isEmpty());
        assertTrue(HyperOsFreezer.frozenPids(null).isEmpty());
        assertTrue(HyperOsFreezer.frozenPids("Frozen processes:[]\n").isEmpty());
    }

    @Test
    public void namesTheFrozenPackage() {
        Map<String, String> pids = new LinkedHashMap<>();
        pids.put("com.example.other", "2000");
        pids.put("dev.headroid.sample", "11456");
        assertEquals("dev.headroid.sample", HyperOsFreezer.firstFrozen(HyperOsFreezer.frozenPids(DUMP), pids));
    }

    @Test
    public void anyFrozenProcessOfThePackageCounts() {
        // pidof prints every process of the package, space separated
        Map<String, String> pids = Collections.singletonMap("dev.headroid.sample", "4242 11456");
        assertEquals("dev.headroid.sample", HyperOsFreezer.firstFrozen(HyperOsFreezer.frozenPids(DUMP), pids));
    }

    @Test
    public void notFrozenOrNotRunning() {
        Map<String, String> pids = new LinkedHashMap<>();
        pids.put("dev.headroid.sample", "4242");
        pids.put("com.example.stopped", "");
        assertNull(HyperOsFreezer.firstFrozen(HyperOsFreezer.frozenPids(DUMP), pids));
    }

    @Test
    public void messageTellsTheOwnerWhatToDo() {
        String message = HyperOsFreezer.frozenMessage("dev.headroid.sample");
        assertTrue(message, message.contains("dev.headroid.sample"));
        assertTrue(message, message.contains("No restrictions"));
    }
}
