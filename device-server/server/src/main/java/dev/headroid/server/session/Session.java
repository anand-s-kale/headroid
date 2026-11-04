// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.session;

import dev.headroid.server.apps.AppLauncher;
import dev.headroid.server.apps.AppMuter;
import dev.headroid.server.apps.AppPresence;
import dev.headroid.server.apps.HyperOsFreezer;
import dev.headroid.server.apps.LaunchGuard;
import dev.headroid.server.apps.UrlHandler;
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

import android.content.Intent;
import android.content.pm.ActivityInfo;
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
    private final AppMuter muter = AppMuter.recover();
    // every display this session created, released or not: their activities are destroyed asynchronously after a release
    private final Set<Integer> ownedDisplayIds = Collections.synchronizedSet(new LinkedHashSet<>());
    private final Map<String, Boolean> runningBeforeLaunch = Collections.synchronizedMap(new LinkedHashMap<>());
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
            ownedDisplayIds.add(display.id());
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
            // remembered at the first launch: a process that already exists belongs to the owner or another session
            runningBeforeLaunch.putIfAbsent(pkg, AppPresence.isRunning(pkg));
            boolean forceStop = p.optBool("forceStop", false);
            if (forceStop) {
                String why = whyNotStop(pkg);
                if (why != null) {
                    throw new RpcException(RpcException.INVALID_PARAMS, "forceStop: not stopping " + pkg + ": " + why);
                }
            }
            Intent intent = AppLauncher.launchIntent(pkg, p.optString("activity", null));
            // a singleTask/singleInstance activity would join the owner's task on display 0 despite MULTIPLE_TASK
            int launchMode = AppLauncher.launchMode(intent);
            if (LaunchGuard.reusesTask(launchMode)) { // only then is where the app is open worth a dumpsys
                String refused = LaunchGuard.whyNotLaunch(pkg, launchMode, whereOpen(pkg), ownDisplays());
                if (refused != null) {
                    throw new RpcException(RpcException.INVALID_PARAMS, refused);
                }
            }
            if (p.optBool("mute", true)) {
                // before the launch, so even the first sound is silenced
                muter.mute(pkg, p.optBool("muteNotifications", false));
            }
            AppLauncher.launch(displayId, intent, pkg, forceStop);
            launchedPackages.add(pkg);
            return null;
        });
        d.register("app.openUrl", p -> {
            int displayId = displays.require(p.getInt("displayId")).id();
            String url = p.getString("url").trim();
            // the handling app must be known before the launch, for the same muting and teardown as app.launch
            ActivityInfo handler = UrlHandler.resolve(url);
            String pkg = handler.packageName;
            // the handler may pass the link on into the app's existing task (a trampoline, or a singleTask activity):
            // never while the app has activities on a display this session does not own, such as the owner's display 0
            String refused = LaunchGuard.whyNotOpenUrl(pkg, whereOpen(pkg), ownDisplays());
            if (refused != null) {
                throw new RpcException(RpcException.INVALID_PARAMS, refused);
            }
            runningBeforeLaunch.putIfAbsent(pkg, AppPresence.isRunning(pkg));
            if (p.optBool("mute", true)) {
                muter.mute(pkg, false);
            }
            AppLauncher.openUrl(displayId, handler, url);
            launchedPackages.add(pkg);
            return Collections.singletonMap("package", pkg);
        });
        d.register("app.stop", p -> {
            String pkg = p.getString("package");
            String why = whyNotStop(pkg);
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("stopped", why == null);
            if (why == null) {
                AppLauncher.stop(pkg);
                launchedPackages.remove(pkg);
                muter.restore(pkg);
            } else {
                result.put("reason", why);
            }
            return result;
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
                uiAutomation.lease(() -> {
                    uiAutomation.setFocusedText(displayId, text, false);
                    return null;
                });
                method = "setText";
            }
            return Collections.singletonMap("method", method);
        });
        d.register("input.clearText", p -> {
            int displayId = displays.require(p.getInt("displayId")).id();
            uiAutomation.lease(() -> {
                uiAutomation.setFocusedText(displayId, "", true);
                return null;
            });
            return null;
        });

        d.register("ui.tree", p -> {
            int displayId = displays.require(p.getInt("displayId")).id();
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("displayId", displayId);
            // the nodes read their children through the connection, so build the whole tree inside the lease
            List<Map<String, Object>> nodes = uiAutomation.lease(() -> TreeBuilder.build(uiAutomation.windowRootViews(displayId), TREE_MAX_DEPTH));
            if (nodes.isEmpty()) {
                // an empty tree with an app launched: on HyperOS the app may be frozen, say so instead of "nothing here"
                String frozen = HyperOsFreezer.frozenPackage(new ArrayList<>(launchedPackages));
                if (frozen != null) {
                    throw new RpcException(RpcException.APP_FROZEN, HyperOsFreezer.frozenMessage(frozen));
                }
            }
            result.put("nodes", nodes);
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
        capabilities.put("muting", true);
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
     * Teardown order: release the displays (their content is destroyed, never moved to display 0), then force-stop the
     * launched apps that headroid started and nobody else has open, then give up the UiAutomation connection, then
     * unmute the apps.
     */
    public void teardown() {
        Ln.i("Teardown");
        List<String> packages;
        synchronized (launchedPackages) {
            packages = new ArrayList<>(launchedPackages);
            launchedPackages.clear();
        }
        // releasing a display destroys the activities on it, without killing the app's process
        displays.releaseAll();
        for (String pkg : packages) {
            try {
                String why = whyNotStop(pkg);
                if (why == null) {
                    AppLauncher.stop(pkg);
                } else {
                    Ln.i("Not stopping " + pkg + ": " + why);
                }
            } catch (RuntimeException e) {
                Ln.e("Could not stop " + pkg, e);
            }
        }
        runningBeforeLaunch.clear();
        uiAutomation.disconnect();
        muter.restoreAll();
    }

    /** Null when {@code pkg} may be force-stopped without hurting the owner or another session, else why not. */
    private String whyNotStop(String pkg) {
        Set<Integer> present;
        try {
            present = AppPresence.displaysWithActivities(pkg);
        } catch (java.io.IOException e) {
            return "could not check where it runs: " + e.getMessage();
        }
        return AppPresence.whyNotStop(runningBeforeLaunch.getOrDefault(pkg, AppPresence.isRunning(pkg)), present, ownDisplays());
    }

    /** The displays with activities of {@code pkg}; when that cannot be checked, the call fails rather than guess. */
    private static Set<Integer> whereOpen(String pkg) {
        try {
            return AppPresence.displaysWithActivities(pkg);
        } catch (java.io.IOException e) {
            throw new RpcException(RpcException.INTERNAL, "could not check where " + pkg + " runs: " + e.getMessage());
        }
    }

    private List<Integer> ownDisplays() {
        synchronized (ownedDisplayIds) {
            return new ArrayList<>(ownedDisplayIds);
        }
    }
}
