// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.input;

import dev.headroid.server.rpc.RpcException;

import com.genymobile.scrcpy.device.Device;

import android.os.SystemClock;
import android.view.InputDevice;
import android.view.KeyCharacterMap;
import android.view.KeyEvent;
import android.view.MotionEvent;

import java.util.List;

/**
 * Injects input into one hidden display from inside the server process (no {@code adb shell input}, no new JVM per
 * action). Events carry the target display id, so they never reach the owner's display.
 */
public final class InputInjector {

    private static final int STEP_MS = 16;

    private final int displayId;

    public InputInjector(int displayId) {
        if (displayId == 0) {
            throw new IllegalArgumentException("never inject into display 0");
        }
        this.displayId = displayId;
    }

    private void inject(android.view.InputEvent event, int mode) {
        if (!Device.injectEvent(event, displayId, mode)) {
            throw new RpcException(RpcException.INTERNAL, "input injection refused on display " + displayId);
        }
    }

    private void touch(long downTime, long eventTime, int action, float x, float y) {
        MotionEvent event = MotionEvent.obtain(downTime, eventTime, action, x, y, 0);
        event.setSource(InputDevice.SOURCE_TOUCHSCREEN);
        try {
            // wait for DOWN/UP to be dispatched, keep MOVE asynchronous so swipes stay smooth
            inject(event, action == MotionEvent.ACTION_MOVE ? Device.INJECT_MODE_ASYNC : Device.INJECT_MODE_WAIT_FOR_RESULT);
        } finally {
            event.recycle();
        }
    }

    public void tap(int x, int y) {
        long now = SystemClock.uptimeMillis();
        touch(now, now, MotionEvent.ACTION_DOWN, x, y);
        touch(now, SystemClock.uptimeMillis(), MotionEvent.ACTION_UP, x, y);
    }

    public void longPress(int x, int y, int durationMs) {
        long down = SystemClock.uptimeMillis();
        touch(down, down, MotionEvent.ACTION_DOWN, x, y);
        SystemClock.sleep(Math.max(0, durationMs));
        touch(down, SystemClock.uptimeMillis(), MotionEvent.ACTION_UP, x, y);
    }

    public void swipe(int x1, int y1, int x2, int y2, int durationMs) {
        List<long[]> points = Gestures.swipePoints(x1, y1, x2, y2, durationMs, STEP_MS);
        long down = SystemClock.uptimeMillis();
        touch(down, down, MotionEvent.ACTION_DOWN, x1, y1);
        for (int i = 1; i < points.size(); i++) {
            long[] p = points.get(i);
            long wait = down + p[0] - SystemClock.uptimeMillis();
            if (wait > 0) {
                SystemClock.sleep(wait);
            }
            touch(down, SystemClock.uptimeMillis(), MotionEvent.ACTION_MOVE, p[1], p[2]);
        }
        long[] last = points.get(points.size() - 1);
        touch(down, SystemClock.uptimeMillis(), MotionEvent.ACTION_UP, last[1], last[2]);
    }

    public void key(int keyCode, int metaState) {
        if (keyCode == KeyEvent.KEYCODE_POWER || keyCode == KeyEvent.KEYCODE_SLEEP || keyCode == KeyEvent.KEYCODE_WAKEUP) {
            // these act on the whole phone, not on one display
            throw new RpcException(RpcException.INVALID_PARAMS, "keyCode: " + KeyEvent.keyCodeToString(keyCode) + " is not allowed");
        }
        for (int action : new int[] {KeyEvent.ACTION_DOWN, KeyEvent.ACTION_UP}) {
            if (!Device.injectKeyEvent(action, keyCode, 0, metaState, displayId, Device.INJECT_MODE_WAIT_FOR_RESULT)) {
                throw new RpcException(RpcException.INTERNAL, "key injection refused on display " + displayId);
            }
        }
    }

    /** Types {@code text} as key events. Returns false when the text needs the set-text fallback. */
    public boolean typeWithKeys(String text) {
        KeyCharacterMap map = KeyCharacterMap.load(KeyCharacterMap.VIRTUAL_KEYBOARD);
        TextPlanner.Plan<KeyEvent> plan = TextPlanner.plan(text, map::getEvents);
        if (plan.useSetText) {
            return false;
        }
        if (plan.events != null) {
            for (KeyEvent event : plan.events) {
                inject(event, Device.INJECT_MODE_WAIT_FOR_RESULT);
            }
        }
        return true;
    }
}
