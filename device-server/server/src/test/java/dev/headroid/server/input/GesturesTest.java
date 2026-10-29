// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.input;

import org.junit.Assert;
import org.junit.Test;

import java.util.List;

public class GesturesTest {

    @Test
    public void endpointsAndMonotonicTime() {
        List<long[]> points = Gestures.swipePoints(100, 1000, 100, 200, 300, 16);
        Assert.assertArrayEquals(new long[] {0, 100, 1000}, points.get(0));
        Assert.assertArrayEquals(new long[] {300, 100, 200}, points.get(points.size() - 1));
        for (int i = 1; i < points.size(); i++) {
            Assert.assertTrue(points.get(i)[0] > points.get(i - 1)[0]);
            Assert.assertTrue(points.get(i)[2] <= points.get(i - 1)[2]);
        }
        Assert.assertTrue(points.size() >= 300 / 16);
    }

    @Test
    public void zeroDurationStillTwoPoints() {
        List<long[]> points = Gestures.swipePoints(0, 0, 50, 50, 0, 16);
        Assert.assertEquals(2, points.size());
        Assert.assertArrayEquals(new long[] {0, 50, 50}, points.get(1));
    }
}
