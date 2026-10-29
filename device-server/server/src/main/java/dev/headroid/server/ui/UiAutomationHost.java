// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.ui;

import dev.headroid.server.rpc.RpcException;

import com.genymobile.scrcpy.FakeContext;
import com.genymobile.scrcpy.util.Ln;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.annotation.TargetApi;
import android.app.UiAutomation;
import android.content.Context;
import android.os.Build;
import android.os.Bundle;
import android.os.HandlerThread;
import android.os.Looper;
import android.util.SparseArray;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * A {@link UiAutomation} connected from the shell process, like the {@code uiautomator} tool does, used to read the
 * windows of one display. Only one UiAutomation can be connected on a phone at a time, so it is connected lazily and
 * disconnected on teardown.
 *
 * <p>Built from the public {@code UiAutomation} API plus its hidden constructor and {@code connect(int)} (AOSP).
 */
public final class UiAutomationHost {

    private static final long WAIT_FOR_IDLE_MS = 300;

    private HandlerThread thread;
    private UiAutomation uiAutomation;

    public synchronized UiAutomation get() {
        if (uiAutomation == null) {
            uiAutomation = connect();
        }
        return uiAutomation;
    }

    private UiAutomation connect() {
        if (Build.VERSION.SDK_INT < 30) {
            throw new RpcException(RpcException.UIA_UNAVAILABLE, "per-display UI tree needs Android 11+");
        }
        try {
            thread = new HandlerThread("headroid-uia");
            thread.start();

            Class<?> connectionInterface = Class.forName("android.app.IUiAutomationConnection");
            Object connection = Class.forName("android.app.UiAutomationConnection").getDeclaredConstructor().newInstance();

            UiAutomation automation;
            try {
                Constructor<UiAutomation> ctor = UiAutomation.class.getDeclaredConstructor(Looper.class, connectionInterface);
                ctor.setAccessible(true);
                automation = ctor.newInstance(thread.getLooper(), connection);
            } catch (NoSuchMethodException e) {
                // newer releases take a Context instead of a Looper
                Constructor<UiAutomation> ctor = UiAutomation.class.getDeclaredConstructor(Context.class, connectionInterface);
                ctor.setAccessible(true);
                automation = ctor.newInstance(FakeContext.get(), connection);
            }

            Method connect = UiAutomation.class.getDeclaredMethod("connect", int.class);
            connect.setAccessible(true);
            // do not turn off the owner's accessibility services (TalkBack, password managers, ...)
            connect.invoke(automation, UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES);

            AccessibilityServiceInfo info = automation.getServiceInfo();
            if (info != null) {
                info.flags |= AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                        | AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                        | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS;
                automation.setServiceInfo(info);
            }
            Ln.i("UiAutomation connected");
            return automation;
        } catch (Exception e) {
            if (thread != null) {
                thread.quitSafely();
                thread = null;
            }
            Throwable cause = e.getCause() != null ? e.getCause() : e;
            throw new RpcException(RpcException.UIA_UNAVAILABLE, "UiAutomation unavailable: " + cause, e);
        }
    }

    /** Roots of the windows on {@code displayId}, top-most first. */
    @TargetApi(30) // connect() refuses older releases
    public List<AccessibilityNodeInfo> windowRoots(int displayId) {
        UiAutomation automation = get();
        try {
            automation.waitForIdle(WAIT_FOR_IDLE_MS / 3, WAIT_FOR_IDLE_MS);
        } catch (java.util.concurrent.TimeoutException e) {
            // the app keeps animating: read the tree as it is
        }
        SparseArray<List<AccessibilityWindowInfo>> all = automation.getWindowsOnAllDisplays();
        List<AccessibilityWindowInfo> windows = all.get(displayId, Collections.emptyList());
        List<AccessibilityNodeInfo> roots = new ArrayList<>(windows.size());
        for (AccessibilityWindowInfo window : windows) {
            roots.add(window.getRoot());
        }
        return roots;
    }

    @TargetApi(30) // connect() refuses older releases
    public List<NodeView> windowRootViews(int displayId) {
        List<NodeView> views = new ArrayList<>();
        for (AccessibilityNodeInfo root : windowRoots(displayId)) {
            views.add(AccessibilityNodeView.wrap(root));
        }
        return views;
    }

    /** Appends {@code text} to the focused editable node on {@code displayId} with ACTION_SET_TEXT. */
    @TargetApi(30) // connect() refuses older releases
    public void appendToFocused(int displayId, String text) {
        AccessibilityNodeInfo focused = null;
        for (AccessibilityNodeInfo root : windowRoots(displayId)) {
            if (root != null) {
                AccessibilityNodeInfo candidate = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
                if (candidate != null && candidate.isEditable()) {
                    focused = candidate;
                    break;
                }
            }
        }
        if (focused == null) {
            throw new RpcException(RpcException.NO_FOCUSED_EDITABLE, "no focused editable field on display " + displayId);
        }
        CharSequence current = focused.isShowingHintText() ? null : focused.getText();
        String value = (current == null ? "" : current.toString()) + text;
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value);
        if (!focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) {
            throw new RpcException(RpcException.INTERNAL, "ACTION_SET_TEXT refused");
        }
    }

    public synchronized void disconnect() {
        if (uiAutomation != null) {
            try {
                Method disconnect = UiAutomation.class.getDeclaredMethod("disconnect");
                disconnect.setAccessible(true);
                disconnect.invoke(uiAutomation);
            } catch (Exception e) {
                Ln.w("UiAutomation disconnect failed: " + e);
            }
            uiAutomation = null;
        }
        if (thread != null) {
            thread.quitSafely();
            thread = null;
        }
    }
}
