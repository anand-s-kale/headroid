// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.input;

import java.util.ArrayList;
import java.util.List;

/** Pure gesture geometry, kept apart from MotionEvent so it can be unit-tested. */
public final class Gestures {

    private Gestures() {
        // not instantiable
    }

    /**
     * Returns a message for the first {@code (x, y)} pair in {@code xy} outside a {@code width}x{@code height} display,
     * or null when all are inside. Off-display touches reach no window, and Android only reports them as "failed".
     */
    public static String outsidePoint(int width, int height, int... xy) {
        for (int i = 0; i + 1 < xy.length; i += 2) {
            int x = xy[i];
            int y = xy[i + 1];
            if (x < 0 || y < 0 || x >= width || y >= height) {
                return "(" + x + ", " + y + ") is outside the " + width + "x" + height + " display";
            }
        }
        return null;
    }

    /** Points {@code {timeMs, x, y}} of a straight swipe, from t=0 at the start to t=durationMs at the end. */
    public static List<long[]> swipePoints(int x1, int y1, int x2, int y2, int durationMs, int stepMs) {
        int duration = Math.max(0, durationMs);
        int step = Math.max(1, stepMs);
        int steps = Math.max(1, duration / step);
        List<long[]> points = new ArrayList<>(steps + 1);
        for (int i = 0; i <= steps; i++) {
            double f = (double) i / steps;
            // steps <= duration, so t strictly increases unless the duration is 0
            long t = Math.round(duration * f);
            long x = Math.round(x1 + (x2 - x1) * f);
            long y = Math.round(y1 + (y2 - y1) * f);
            points.add(new long[] {t, x, y});
        }
        return points;
    }
}
