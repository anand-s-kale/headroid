// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

import dev.headroid.server.rpc.RpcException;

import org.junit.Assert;
import org.junit.Test;

public class DisplayRegistryTest {

    static final class FakeDisplay implements ManagedDisplay {
        final int id;
        int releases;

        FakeDisplay(int id) {
            this.id = id;
        }

        @Override
        public int id() {
            return id;
        }

        @Override
        public void release() {
            releases++;
        }
    }

    private static void assertInvalid(DisplayRegistry<? extends ManagedDisplay> registry, int id) {
        try {
            registry.require(id);
            Assert.fail("expected RpcException for display " + id);
        } catch (RpcException e) {
            Assert.assertEquals(RpcException.INVALID_PARAMS, e.getCode());
            Assert.assertTrue(e.getMessage().contains("not owned by headroid"));
        }
    }

    @Test
    public void rejectsDisplayZeroAndUnknown() {
        DisplayRegistry<FakeDisplay> registry = new DisplayRegistry<>();
        registry.add(new FakeDisplay(5));
        assertInvalid(registry, 0);
        assertInvalid(registry, 7);
        Assert.assertEquals(5, registry.require(5).id());
    }

    @Test(expected = IllegalArgumentException.class)
    public void addRefusesDisplayZero() {
        new DisplayRegistry<FakeDisplay>().add(new FakeDisplay(0));
    }

    @Test
    public void releaseAllReleasesEachOnce() {
        DisplayRegistry<FakeDisplay> registry = new DisplayRegistry<>();
        FakeDisplay a = new FakeDisplay(3);
        FakeDisplay b = new FakeDisplay(4);
        registry.add(a);
        registry.add(b);
        registry.releaseAll();
        registry.releaseAll();
        Assert.assertEquals(1, a.releases);
        Assert.assertEquals(1, b.releases);
        Assert.assertTrue(registry.all().isEmpty());
    }

    @Test
    public void releaseOne() {
        DisplayRegistry<FakeDisplay> registry = new DisplayRegistry<>();
        FakeDisplay a = new FakeDisplay(3);
        registry.add(a);
        registry.release(3);
        Assert.assertEquals(1, a.releases);
        assertInvalid(registry, 3);
    }

    @Test
    public void releaseContinuesAfterFailure() {
        DisplayRegistry<ManagedDisplay> registry = new DisplayRegistry<>();
        FakeDisplay ok = new FakeDisplay(4);
        registry.add(new ManagedDisplay() {
            @Override
            public int id() {
                return 3;
            }

            @Override
            public void release() {
                throw new IllegalStateException("boom");
            }
        });
        registry.add(ok);
        registry.releaseAll();
        Assert.assertEquals(1, ok.releases);
        Assert.assertTrue(registry.all().isEmpty());
    }
}
