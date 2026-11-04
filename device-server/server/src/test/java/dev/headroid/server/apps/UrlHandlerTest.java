// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class UrlHandlerTest {

    @Test
    public void singleAppHandlesTheLink() {
        assertEquals("com.android.chrome", UrlHandler.singleHandler("com.android.chrome", "com.google.android.apps.chrome.IntentDispatcher"));
    }

    @Test
    public void nothingResolves() {
        assertNull(UrlHandler.singleHandler(null, null));
        assertNull(UrlHandler.singleHandler("", "x.Y"));
    }

    @Test
    public void aospResolverIsNotAnApp() {
        // several apps handle the link and none is the default: Android resolves to its "Open with" dialog
        assertNull(UrlHandler.singleHandler("android", "com.android.internal.app.ResolverActivity"));
        assertNull(UrlHandler.singleHandler("android", "com.android.internal.app.ChooserActivity"));
    }

    @Test
    public void vendorResolverIsNotAnApp() {
        // OEM builds ship their own resolver outside the "android" package
        assertNull(UrlHandler.singleHandler("com.miui.securitycore", "com.miui.resolver.ResolverActivity"));
        assertNull(UrlHandler.singleHandler("com.android.intentresolver", "com.android.intentresolver.ChooserActivity"));
    }

    @Test
    public void refusalNamesTheUrl() {
        assertTrue(UrlHandler.noSingleHandler("https://example.com/").contains("no single app handles https://example.com/"));
    }

    @Test
    public void blankUrlIsRejected() {
        assertEquals("url: must not be empty", UrlHandler.urlProblem(""));
        assertEquals("url: must not be empty", UrlHandler.urlProblem("  "));
        assertEquals("url: must not be empty", UrlHandler.urlProblem(null));
        assertNull(UrlHandler.urlProblem("https://example.com/"));
    }
}
