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
import android.content.pm.PackageManager;

/** Starts and stops apps on hidden displays. */
public final class AppLauncher {

    private AppLauncher() {
        // not instantiable
    }

    public static void launch(int displayId, String packageName, String activity, boolean forceStop) {
        if (displayId == 0) {
            throw new IllegalArgumentException("never launch on display 0");
        }
        Intent intent;
        if (activity != null) {
            String className = activity.startsWith(".") ? packageName + activity : activity;
            intent = new Intent(Intent.ACTION_MAIN);
            intent.setComponent(new ComponentName(packageName, className));
        } else {
            PackageManager pm = FakeContext.get().getPackageManager();
            intent = Device.getLaunchIntent(pm, packageName);
            if (intent == null) {
                throw new RpcException(RpcException.INVALID_PARAMS, "package: no launchable activity in " + packageName);
            }
        }
        // MULTIPLE_TASK: start a new task on the hidden display instead of pulling an existing task of this app
        // (possibly the owner's, on display 0) over to it
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_MULTIPLE_TASK);

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
