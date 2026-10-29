// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

import dev.headroid.server.rpc.RpcException;

import java.util.function.Consumer;
import java.util.function.Function;

/**
 * Holds the latest frame of a display. A static screen produces no new frames, so the last one is kept until a newer
 * one replaces it; the replaced frame is closed at once so the producer never runs out of buffers.
 */
public final class FrameStore<T> {

    private final Consumer<T> closer;
    private T latest;
    private long frameCount;
    private boolean closed;

    public FrameStore(Consumer<T> closer) {
        this.closer = closer;
    }

    public void offer(T frame) {
        if (frame == null) {
            return;
        }
        T previous;
        synchronized (this) {
            if (closed) {
                previous = frame;
            } else {
                previous = latest;
                latest = frame;
                frameCount++;
            }
        }
        if (previous != null) {
            closer.accept(previous);
        }
    }

    /** Runs {@code reader} on the latest frame while holding it; the frame is not closed meanwhile. */
    public synchronized <R> R withLatest(Function<T, R> reader) {
        if (latest == null) {
            throw new RpcException(RpcException.NO_FRAME, "no frame yet");
        }
        return reader.apply(latest);
    }

    public synchronized long frameCount() {
        return frameCount;
    }

    public void close() {
        T previous;
        synchronized (this) {
            closed = true;
            previous = latest;
            latest = null;
        }
        if (previous != null) {
            closer.accept(previous);
        }
    }
}
