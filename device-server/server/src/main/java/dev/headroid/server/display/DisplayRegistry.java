// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

import dev.headroid.server.rpc.RpcException;

import com.genymobile.scrcpy.util.Ln;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The displays this server owns. Every RPC resolves its {@code displayId} here, so display 0 (the owner's screen) and
 * displays created by anyone else can never be targeted.
 */
public final class DisplayRegistry<D extends ManagedDisplay> {

    private final Map<Integer, D> displays = new LinkedHashMap<>();

    public synchronized void add(D display) {
        if (display.id() == 0) {
            throw new IllegalArgumentException("display 0 is never managed by headroid");
        }
        displays.put(display.id(), display);
    }

    public synchronized D require(int displayId) {
        D display = displays.get(displayId);
        if (display == null) {
            throw new RpcException(RpcException.INVALID_PARAMS, "displayId " + displayId + ": display not owned by headroid");
        }
        return display;
    }

    public synchronized List<D> all() {
        return new ArrayList<>(displays.values());
    }

    public void release(int displayId) {
        D display;
        synchronized (this) {
            display = require(displayId);
            displays.remove(displayId);
        }
        display.release();
    }

    /** Releases every display, continuing past failures. */
    public void releaseAll() {
        List<D> toRelease;
        synchronized (this) {
            toRelease = new ArrayList<>(displays.values());
            displays.clear();
        }
        for (D display : toRelease) {
            try {
                display.release();
            } catch (RuntimeException e) {
                Ln.e("Could not release display " + display.id(), e);
            }
        }
    }
}
