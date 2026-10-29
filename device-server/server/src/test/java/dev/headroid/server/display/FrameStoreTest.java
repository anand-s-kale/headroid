// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

import dev.headroid.server.rpc.RpcException;

import org.junit.Assert;
import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public class FrameStoreTest {

    @Test
    public void closesPreviousFrame() {
        List<String> closed = new ArrayList<>();
        FrameStore<String> store = new FrameStore<>(closed::add);
        store.offer("a");
        store.offer("b");
        Assert.assertEquals(Collections.singletonList("a"), closed);
        Assert.assertEquals("b", store.withLatest(f -> f));
        Assert.assertEquals(2, store.frameCount());
    }

    @Test
    public void noFrameYet() {
        FrameStore<String> store = new FrameStore<>(f -> { });
        try {
            store.withLatest(f -> f);
            Assert.fail();
        } catch (RpcException e) {
            Assert.assertEquals(RpcException.NO_FRAME, e.getCode());
        }
    }

    @Test
    public void keepsLastFrameWhenIdle() {
        FrameStore<String> store = new FrameStore<>(f -> { });
        store.offer("only");
        Assert.assertEquals("only", store.withLatest(f -> f));
        Assert.assertEquals("only", store.withLatest(f -> f));
    }

    @Test
    public void nullOfferIgnored() {
        FrameStore<String> store = new FrameStore<>(f -> { });
        store.offer("a");
        store.offer(null);
        Assert.assertEquals("a", store.withLatest(f -> f));
    }

    @Test
    public void closeReleasesLatestAndRejectsNewFrames() {
        List<String> closed = new ArrayList<>();
        FrameStore<String> store = new FrameStore<>(closed::add);
        store.offer("a");
        store.close();
        store.offer("b");
        Assert.assertEquals(Arrays.asList("a", "b"), closed);
    }
}
