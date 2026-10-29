// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

/**
 * Virtual display flags for hidden displays. Values are the public and hidden constants of
 * {@code android.hardware.display.DisplayManager} (AOSP).
 */
public final class DisplayFlags {

    public static final int PUBLIC = 1;
    public static final int PRESENTATION = 1 << 1;
    public static final int OWN_CONTENT_ONLY = 1 << 3;
    public static final int SUPPORTS_TOUCH = 1 << 6;
    public static final int ROTATES_WITH_CONTENT = 1 << 7;
    public static final int DESTROY_CONTENT_ON_REMOVAL = 1 << 8;
    public static final int SHOULD_SHOW_SYSTEM_DECORATIONS = 1 << 9;
    public static final int TRUSTED = 1 << 10;
    public static final int OWN_DISPLAY_GROUP = 1 << 11;
    public static final int ALWAYS_UNLOCKED = 1 << 12;
    public static final int TOUCH_FEEDBACK_DISABLED = 1 << 13;
    public static final int OWN_FOCUS = 1 << 14;
    public static final int DEVICE_DISPLAY_GROUP = 1 << 15;
    public static final int STEAL_TOP_FOCUS_DISABLED = 1 << 16;

    private static final String[] NAMES = {
        "PUBLIC", "PRESENTATION", "SECURE", "OWN_CONTENT_ONLY", "AUTO_MIRROR", "CAN_SHOW_WITH_INSECURE_KEYGUARD", "SUPPORTS_TOUCH",
        "ROTATES_WITH_CONTENT", "DESTROY_CONTENT_ON_REMOVAL", "SHOULD_SHOW_SYSTEM_DECORATIONS", "TRUSTED", "OWN_DISPLAY_GROUP",
        "ALWAYS_UNLOCKED", "TOUCH_FEEDBACK_DISABLED", "OWN_FOCUS", "DEVICE_DISPLAY_GROUP", "STEAL_TOP_FOCUS_DISABLED",
    };

    private DisplayFlags() {
        // not instantiable
    }

    /**
     * Flags for a hidden display on the given API level.
     *
     * <p>DESTROY_CONTENT_ON_REMOVAL matters for isolation: without it, activities left on a released virtual display
     * are moved to the default display, i.e. onto the owner's screen. System decorations are never requested.
     */
    public static int forSdk(int sdk) {
        int flags = PUBLIC | PRESENTATION | OWN_CONTENT_ONLY | SUPPORTS_TOUCH | ROTATES_WITH_CONTENT | DESTROY_CONTENT_ON_REMOVAL;
        if (sdk >= 33) {
            flags |= TRUSTED | OWN_DISPLAY_GROUP | ALWAYS_UNLOCKED | TOUCH_FEEDBACK_DISABLED;
        }
        if (sdk >= 34) {
            flags |= OWN_FOCUS | DEVICE_DISPLAY_GROUP | STEAL_TOP_FOCUS_DISABLED;
        }
        return flags;
    }

    public static String describe(int flags) {
        StringBuilder sb = new StringBuilder();
        for (int bit = 0; bit < NAMES.length; bit++) {
            if ((flags & (1 << bit)) != 0) {
                if (sb.length() > 0) {
                    sb.append('|');
                }
                sb.append(NAMES[bit]);
            }
        }
        return sb.toString();
    }
}
