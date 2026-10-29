// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.input;

import java.util.function.Function;

/**
 * Decides how to enter text without a keyboard: as key events when the virtual key map can type every character,
 * otherwise by setting the text of the focused editable node (emoji, accents, non-Latin scripts).
 */
public final class TextPlanner {

    public static final class Plan<E> {
        public final boolean useSetText;
        /** Key events to inject, or null when there is nothing to inject. */
        public final E[] events;

        Plan(boolean useSetText, E[] events) {
            this.useSetText = useSetText;
            this.events = events;
        }
    }

    private TextPlanner() {
        // not instantiable
    }

    /** {@code keyMap} behaves like {@code KeyCharacterMap.getEvents(char[])}: null when a char cannot be typed. */
    public static <E> Plan<E> plan(String text, Function<char[], E[]> keyMap) {
        if (text.isEmpty()) {
            return new Plan<>(false, null);
        }
        E[] events = keyMap.apply(text.toCharArray());
        if (events == null) {
            return new Plan<>(true, null);
        }
        return new Plan<>(false, events);
    }
}
