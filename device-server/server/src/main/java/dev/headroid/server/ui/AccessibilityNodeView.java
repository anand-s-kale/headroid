// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.ui;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;

/** {@link NodeView} over an {@link AccessibilityNodeInfo}. */
public final class AccessibilityNodeView implements NodeView {

    private final AccessibilityNodeInfo node;

    public AccessibilityNodeView(AccessibilityNodeInfo node) {
        this.node = node;
    }

    public static AccessibilityNodeView wrap(AccessibilityNodeInfo node) {
        return node == null ? null : new AccessibilityNodeView(node);
    }

    private static String str(CharSequence value) {
        return value == null ? null : value.toString();
    }

    @Override
    public String cls() {
        return str(node.getClassName());
    }

    @Override
    public String pkg() {
        return str(node.getPackageName());
    }

    @Override
    public String text() {
        if (node.isShowingHintText()) {
            return null; // the hint is not text the user typed
        }
        return str(node.getText());
    }

    @Override
    public String desc() {
        return str(node.getContentDescription());
    }

    @Override
    public String rid() {
        return node.getViewIdResourceName();
    }

    @Override
    public int[] bounds() {
        Rect rect = new Rect();
        // for a window on a virtual display, "screen" is that display
        node.getBoundsInScreen(rect);
        return new int[] {rect.left, rect.top, rect.right, rect.bottom};
    }

    @Override
    @SuppressWarnings("deprecation") // isChecked(): getChecked() only exists on API 36+
    public int flags() {
        int flags = 0;
        flags |= node.isClickable() ? CLICKABLE : 0;
        flags |= node.isLongClickable() ? LONG_CLICKABLE : 0;
        flags |= node.isEnabled() ? ENABLED : 0;
        flags |= node.isFocused() ? FOCUSED : 0;
        flags |= node.isFocusable() ? FOCUSABLE : 0;
        flags |= node.isScrollable() ? SCROLLABLE : 0;
        flags |= node.isCheckable() ? CHECKABLE : 0;
        flags |= node.isChecked() ? CHECKED : 0;
        flags |= node.isEditable() ? EDITABLE : 0;
        flags |= node.isSelected() ? SELECTED : 0;
        flags |= node.isVisibleToUser() ? VISIBLE : 0;
        return flags;
    }

    @Override
    public int childCount() {
        return node.getChildCount();
    }

    @Override
    public NodeView child(int index) {
        return wrap(node.getChild(index));
    }
}
