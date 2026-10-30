// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.session;

import dev.headroid.server.apps.AppLauncher;
import dev.headroid.server.display.DisplayFlags;
import dev.headroid.server.display.DisplayRegistry;
import dev.headroid.server.display.HiddenDisplay;
import dev.headroid.server.display.ScreenshotEncoder;
import dev.headroid.server.input.Gestures;
import dev.headroid.server.input.InputInjector;
import dev.headroid.server.rpc.Params;
import dev.headroid.server.rpc.RpcDispatcher;
import dev.headroid.server.rpc.RpcException;
import dev.headroid.server.ui.TreeBuilder;
import dev.headroid.server.ui.UiAutomationHost;

import com.genymobile.scrcpy.BuildConfig;
import com.genymobile.scrcpy.util.Ln;

import android.os.Build;
import android.system.Os;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * State shared by all connections of one server process: owned displays, apps launched on them, the UiAutomation
 * connection. It survives a host reconnect within the watchdog grace period.
 */
public final class Session {

    public static final int PROTOCOL = 1;
    private static final int TREE_MAX_DEPTH = 80;

    private final DisplayRegistry<HiddenDisplay> displays = new DisplayRegistry<>();
    private final Set<String> launchedPackages = Collections.synchronizedSet(new LinkedHashSet<>());
    private final UiAutomationHost uiAutomation = new UiAutomationHost();
    private volatile boolean shutdownRequested;

    public boolean isShutdownRequested() {
        return shutdownRequested;
    }

    public void register(RpcDispatcher d) {
        d.register("server.info", p -> info());
        d.register("server.shutdown", p -> {
            shutdownRequested = true;
            return null;
        });

        d.register("display.create", p -> {
            HiddenDisplay display = HiddenDisplay.create(p.optInt("width", 720), p.optInt("height", 1600), p.optInt("dpi", 320));
            displays.add(display);
            Map<String, Object> result = describe(display);
            result.put("flags", DisplayFlags.describe(display.flags()));
            return result;
        });
        d.register("display.list", p -> {
            List<Object> list = new ArrayList<>();
            for (HiddenDisplay display : displays.all()) {
                list.add(describe(display));
            }
            return Collections.singletonMap("displays", list);
        });
        d.register("display.release", p -> {
            displays.release(p.getInt("displayId"));
            return null;
        });
        d.register("display.screenshot", p -> {
            HiddenDisplay display = displays.require(p.getInt("displayId"));
            String format = p.optString("format", "png");
            int quality = p.optInt("quality", 80);
            int maxSize = p.optInt("maxSize", 0);
            return display.frames().withLatest(image -> ScreenshotEncoder.encode(image, format, quality, maxSize));
        });

        d.register("app.launch", p -> {
            int displayId = displays.require(p.getInt("displayId")).id();
            String pkg = p.getString("package");
            AppLauncher.launch(displayId, pkg, p.optString("activity", null), p.optBool("forceStop", false));
            launchedPackages.add(pkg);
            return null;
        });
        d.register("app.stop", p -> {
            AppLauncher.stop(p.getString("package"));
            return null;
        });

        d.register("input.tap", p -> {
            injector(p, p.getInt("x"), p.getInt("y")).tap(p.getInt("x"), p.getInt("y"));
            return null;
        });
        d.register("input.longPress", p -> {
            injector(p, p.getInt("x"), p.getInt("y")).longPress(p.getInt("x"), p.getInt("y"), p.optInt("durationMs", 600));
            return null;
        });
        d.register("input.swipe", p -> {
            injector(p, p.getInt("x1"), p.getInt("y1"), p.getInt("x2"), p.getInt("y2"))
                    .swipe(p.getInt("x1"), p.getInt("y1"), p.getInt("x2"), p.getInt("y2"), p.optInt("durationMs", 300));
            return null;
        });
        d.register("input.key", p -> {
            injector(p).key(p.getInt("keyCode"), p.optInt("metaState", 0));
            return null;
        });
        d.register("input.text", p -> {
            int displayId = displays.require(p.getInt("displayId")).id();
            String text = p.getString("text");
            String method = "keys";
            if (!new InputInjector(displayId).typeWithKeys(text)) {
                uiAutomation.appendToFocused(displayId, text);
                method = "setText";
            }
            return Collections.singletonMap("method", method);
        });

        d.register("ui.tree", p -> {
            int displayId = displays.require(p.getInt("displayId")).id();
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("displayId", displayId);
            result.put("nodes", TreeBuilder.build(uiAutomation.windowRootViews(displayId), TREE_MAX_DEPTH));
            return result;
        });
    }

    private InputInjector injector(Params p) {
        return new InputInjector(displays.require(p.getInt("displayId")).id());
    }

    /** As {@link #injector(Params)}, first rejecting touch points outside the display. */
    private InputInjector injector(Params p, int... xy) {
        HiddenDisplay display = displays.require(p.getInt("displayId"));
        String outside = Gestures.outsidePoint(display.width(), display.height(), xy);
        if (outside != null) {
            throw new RpcException(RpcException.INVALID_PARAMS, outside);
        }
        return new InputInjector(display.id());
    }

    private static Map<String, Object> describe(HiddenDisplay display) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("displayId", display.id());
        map.put("width", display.width());
        map.put("height", display.height());
        map.put("dpi", display.dpi());
        return map;
    }

    private static Map<String, Object> info() {
        int sdk = Build.VERSION.SDK_INT;
        Map<String, Object> capabilities = new LinkedHashMap<>();
        capabilities.put("fullIsolation", sdk >= 34);
        capabilities.put("perDisplayInput", sdk >= 29);
        capabilities.put("uiTree", sdk >= 30);
        capabilities.put("displayFlags", DisplayFlags.describe(DisplayFlags.forSdk(sdk)));

        Map<String, Object> info = new LinkedHashMap<>();
        info.put("protocol", PROTOCOL);
        info.put("version", BuildConfig.VERSION_NAME);
        info.put("sdk", sdk);
        info.put("release", Build.VERSION.RELEASE);
        info.put("manufacturer", Build.MANUFACTURER);
        info.put("model", Build.MODEL);
        info.put("uid", Os.getuid());
        info.put("capabilities", capabilities);
        return info;
    }

    /**
     * Teardown order: stop the apps launched on hidden displays, then release the displays (their remaining content is
     * destroyed, never moved to display 0), then give up the UiAutomation connection.
     */
    public void teardown() {
        Ln.i("Teardown");
        List<String> packages;
        synchronized (launchedPackages) {
            packages = new ArrayList<>(launchedPackages);
            launchedPackages.clear();
        }
        for (String pkg : packages) {
            try {
                AppLauncher.stop(pkg);
            } catch (RuntimeException e) {
                Ln.e("Could not stop " + pkg, e);
            }
        }
        displays.releaseAll();
        uiAutomation.disconnect();
    }
}
