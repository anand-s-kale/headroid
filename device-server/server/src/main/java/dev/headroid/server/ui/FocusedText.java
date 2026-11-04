// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.ui;

/** The value to set on the focused editable field: its text with {@code text} appended, or {@code text} alone. */
public final class FocusedText {

    private FocusedText() {
        // not instantiable
    }

    /**
     * @param current the field's text, or null
     * @param showingHint true when {@code current} is the field's hint, not its content
     * @param replace true to drop the current content (an empty {@code text} then clears the field)
     */
    public static String value(CharSequence current, boolean showingHint, String text, boolean replace) {
        if (replace || current == null || showingHint) {
            return text;
        }
        return current + text;
    }
}
