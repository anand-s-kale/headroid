// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import dev.headroid.server.rpc.RpcException;

import com.genymobile.scrcpy.FakeContext;

import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Finds the one app that opens a link. headroid launches that app itself (muted, in its own task, stopped at teardown),
 * so it must know the package before the launch; a link several apps claim resolves to the system's "Open with" dialog,
 * which is refused rather than shown.
 */
public final class UrlHandler {

    /**
     * Schemes headroid does not open. intent and android-app name an arbitrary component and flags; file, content and
     * data read local data; javascript and about are not links to an app; tel, sms, mms, mailto, voicemail, geo and
     * market reach other people, cost money or leave the app under test.
     */
    static final Set<String> REFUSED_SCHEMES = new HashSet<>(Arrays.asList("intent", "android-app", "file", "content",
            "data", "javascript", "about", "tel", "sms", "smsto", "mms", "mmsto", "mailto", "voicemail", "geo", "market"));

    private static final Pattern SCHEME = Pattern.compile("^([A-Za-z][A-Za-z0-9+.-]*):");

    private UrlHandler() {
        // not instantiable
    }

    /** The activity that opens {@code url} on its own; throws INVALID_PARAMS when there is none or Android would ask. */
    public static ActivityInfo resolve(String url) {
        String problem = urlProblem(url);
        if (problem != null) {
            throw new RpcException(RpcException.INVALID_PARAMS, problem);
        }
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        PackageManager pm = FakeContext.get().getPackageManager();
        // MATCH_DEFAULT_ONLY: startActivity adds CATEGORY_DEFAULT to an implicit intent, so resolve the same way
        ResolveInfo info = pm.resolveActivity(intent, PackageManager.MATCH_DEFAULT_ONLY);
        ActivityInfo activity = info == null ? null : info.activityInfo;
        List<String> handlers = new ArrayList<>();
        List<ResolveInfo> candidates = pm.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY);
        if (candidates != null) {
            for (ResolveInfo candidate : candidates) {
                if (candidate.activityInfo != null) {
                    handlers.add(key(candidate.activityInfo.packageName, candidate.activityInfo.name));
                }
            }
        }
        if (activity == null || !isSingleHandler(activity.packageName, activity.name, handlers)) {
            throw new RpcException(RpcException.INVALID_PARAMS, noSingleHandler(url));
        }
        return activity;
    }

    /** Null when {@code url} may be resolved, else what is wrong with it (empty, no scheme, or a refused scheme). */
    static String urlProblem(String url) {
        if (url == null || url.trim().isEmpty()) {
            return "url: must not be empty";
        }
        Matcher m = SCHEME.matcher(url.trim());
        if (!m.find()) {
            return "url: needs a scheme, such as https://";
        }
        String scheme = m.group(1).toLowerCase(Locale.ROOT);
        if (REFUSED_SCHEMES.contains(scheme)) {
            return "url: headroid does not open " + scheme + ": links";
        }
        return null;
    }

    /**
     * Whether the resolved activity is a real handler: one of the activities that match the link. A resolver or chooser
     * dialog never is (whatever a vendor calls it); the {@code android} package is refused in any case.
     */
    static boolean isSingleHandler(String packageName, String className, Collection<String> handlers) {
        if (packageName == null || packageName.isEmpty() || className == null || "android".equals(packageName)) {
            return false;
        }
        return handlers.contains(key(packageName, className));
    }

    static String key(String packageName, String className) {
        return packageName + "/" + className;
    }

    static String noSingleHandler(String url) {
        return "url: no single app handles " + url + " (none, or Android would ask which app to use)";
    }
}
