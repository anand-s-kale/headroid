// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.ui;

/** Read-only view of one UI node, so tree building does not depend on AccessibilityNodeInfo. */
public interface NodeView {

    int CLICKABLE = 1;
    int LONG_CLICKABLE = 1 << 1;
    int ENABLED = 1 << 2;
    int FOCUSED = 1 << 3;
    int FOCUSABLE = 1 << 4;
    int SCROLLABLE = 1 << 5;
    int CHECKABLE = 1 << 6;
    int CHECKED = 1 << 7;
    int EDITABLE = 1 << 8;
    int SELECTED = 1 << 9;
    int VISIBLE = 1 << 10;

    String cls();

    String pkg();

    String text();

    String desc();

    String rid();

    /** Bounds on the display, {@code {left, top, right, bottom}}. */
    int[] bounds();

    /** Bit set of the constants above. */
    int flags();

    int childCount();

    /** The child at {@code index}, or null if it vanished. */
    NodeView child(int index);
}
