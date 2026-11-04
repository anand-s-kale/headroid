// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import dev.headroid.server.rpc.RpcException;

import com.genymobile.scrcpy.FakeContext;
import com.genymobile.scrcpy.device.Device;
import com.genymobile.scrcpy.wrappers.ActivityManager;
import com.genymobile.scrcpy.wrappers.ServiceManager;

import android.app.ActivityOptions;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;

/** Starts and stops apps on hidden displays. */
public final class AppLauncher {

    /**
     * MULTIPLE_TASK: start a new task on the hidden display instead of pulling an existing task of this app (possibly
     * the owner's, on display 0) over to it. EXCLUDE_FROM_RECENTS: keep the task out of the owner's Recents; a
     * released display destroys the activities but leaves the task listed, and opening it from Recents starts the app
     * under test on display 0.
     */
    static final int LAUNCH_FLAGS = Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_MULTIPLE_TASK
            | Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS;

    private AppLauncher() {
        // not instantiable
    }

    /** The intent app.launch starts: the explicit {@code activity} when given, else the package's launcher activity. */
    public static Intent launchIntent(String packageName, String activity) {
        if (activity != null) {
            String className = activity.startsWith(".") ? packageName + activity : activity;
            Intent intent = new Intent(Intent.ACTION_MAIN);
            intent.setComponent(new ComponentName(packageName, className));
            return intent;
        }
        PackageManager pm = FakeContext.get().getPackageManager();
        Intent intent = Device.getLaunchIntent(pm, packageName);
        if (intent == null) {
            throw new RpcException(RpcException.INVALID_PARAMS, "package: no launchable activity in " + packageName);
        }
        return intent;
    }

    /** The launch mode of the activity {@code intent} starts (ActivityInfo.LAUNCH_*), standard when it does not resolve. */
    public static int launchMode(Intent intent) {
        ResolveInfo info = FakeContext.get().getPackageManager().resolveActivity(intent, 0);
        return info == null || info.activityInfo == null ? ActivityInfo.LAUNCH_MULTIPLE : info.activityInfo.launchMode;
    }

    /** Starts {@code intent} (from {@link #launchIntent}) of {@code packageName} on the display. */
    public static void launch(int displayId, Intent intent, String packageName, boolean forceStop) {
        if (displayId == 0) {
            throw new IllegalArgumentException("never launch on display 0");
        }
        start(displayId, intent, packageName, forceStop);
    }

    /** Opens {@code url} with exactly {@code handler} (from {@link UrlHandler#resolve}), so no chooser can appear. */
    public static void openUrl(int displayId, ActivityInfo handler, String url) {
        if (displayId == 0) {
            throw new IllegalArgumentException("never launch on display 0");
        }
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        intent.setComponent(new ComponentName(handler.packageName, handler.name));
        start(displayId, intent, handler.packageName, false);
    }

    private static void start(int displayId, Intent intent, String packageName, boolean forceStop) {
        intent.addFlags(LAUNCH_FLAGS);

        ActivityOptions options = ActivityOptions.makeBasic();
        options.setLaunchDisplayId(displayId);

        ActivityManager am = ServiceManager.getActivityManager();
        if (forceStop) {
            am.forceStopPackage(packageName);
        }
        int result = am.startActivity(intent, options.toBundle());
        if (result < 0) {
            throw new RpcException(RpcException.INTERNAL, "startActivity failed with code " + result);
        }
    }

    public static void stop(String packageName) {
        ServiceManager.getActivityManager().forceStopPackage(packageName);
    }
}
