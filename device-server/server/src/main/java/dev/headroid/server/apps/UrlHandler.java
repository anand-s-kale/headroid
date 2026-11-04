// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import dev.headroid.server.rpc.RpcException;

import com.genymobile.scrcpy.FakeContext;

import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;

/**
 * Finds the one app that opens a link. headroid launches that app itself (muted, in its own task, stopped at teardown),
 * so it must know the package before the launch; a link several apps claim resolves to the system's "Open with" dialog,
 * which is refused rather than shown.
 */
public final class UrlHandler {

    private UrlHandler() {
        // not instantiable
    }

    /** The activity that opens {@code url} on its own; throws INVALID_PARAMS when there is none or Android would ask. */
    public static ComponentName resolve(String url) {
        String problem = urlProblem(url);
        if (problem != null) {
            throw new RpcException(RpcException.INVALID_PARAMS, problem);
        }
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        PackageManager pm = FakeContext.get().getPackageManager();
        // MATCH_DEFAULT_ONLY: startActivity adds CATEGORY_DEFAULT to an implicit intent, so resolve the same way
        ResolveInfo info = pm.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);
        ActivityInfo activity = info == null ? null : info.activityInfo;
        String pkg = activity == null ? null : singleHandler(activity.packageName, activity.name);
        if (pkg == null) {
            throw new RpcException(RpcException.INVALID_PARAMS, noSingleHandler(url));
        }
        return new ComponentName(pkg, activity.name);
    }

    /** Null when {@code url} may be resolved, else what is wrong with it. */
    static String urlProblem(String url) {
        return url == null || url.trim().isEmpty() ? "url: must not be empty" : null;
    }

    /**
     * The package of the resolved activity, or null when nothing resolved or it is a resolver/chooser dialog (AOSP's
     * {@code com.android.internal.app.ResolverActivity}, the IntentResolver module, or a vendor's own).
     */
    static String singleHandler(String packageName, String className) {
        if (packageName == null || packageName.isEmpty() || className == null) {
            return null;
        }
        if ("android".equals(packageName) || className.endsWith("ResolverActivity") || className.endsWith("ChooserActivity")) {
            return null;
        }
        return packageName;
    }

    static String noSingleHandler(String url) {
        return "url: no single app handles " + url + " (none, or Android would ask which app to use)";
    }
}
