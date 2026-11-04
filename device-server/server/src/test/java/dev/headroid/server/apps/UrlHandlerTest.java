// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.apps;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.List;

public class UrlHandlerTest {

    private static final String CHROME = "com.android.chrome";
    private static final String DISPATCHER = "com.google.android.apps.chrome.IntentDispatcher";
    private static final List<String> HANDLERS = List.of(UrlHandler.key(CHROME, DISPATCHER),
            UrlHandler.key("org.mozilla.firefox", "org.mozilla.fenix.IntentReceiverActivity"));

    @Test
    public void resolvedActivityAmongTheMatchesIsTheHandler() {
        assertTrue(UrlHandler.isSingleHandler(CHROME, DISPATCHER, HANDLERS));
    }

    @Test
    public void nothingResolves() {
        assertFalse(UrlHandler.isSingleHandler(null, null, HANDLERS));
        assertFalse(UrlHandler.isSingleHandler("", "x.Y", HANDLERS));
        assertFalse(UrlHandler.isSingleHandler(CHROME, DISPATCHER, List.of()));
    }

    @Test
    public void resolverOrChooserIsNeverAMatch() {
        // several apps handle the link and none is the default: Android resolves to its "Open with" dialog, which is
        // not among the matching activities, whatever it is called
        assertFalse(UrlHandler.isSingleHandler("com.miui.securitycore", "com.miui.resolver.Picker", HANDLERS));
        assertFalse(UrlHandler.isSingleHandler("com.android.intentresolver", "com.android.intentresolver.ChooserActivity", HANDLERS));
    }

    @Test
    public void androidPackageIsRefusedEvenWhenListed() {
        String resolver = "com.android.internal.app.ResolverActivity";
        assertFalse(UrlHandler.isSingleHandler("android", resolver, List.of(UrlHandler.key("android", resolver))));
    }

    @Test
    public void anActivityNamedLikeAResolverIsStillAHandler() {
        // the old name rule refused real handlers called *ResolverActivity
        String cls = "com.example.links.LinkResolverActivity";
        assertTrue(UrlHandler.isSingleHandler("com.example", cls, List.of(UrlHandler.key("com.example", cls))));
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
    }

    @Test
    public void urlWithoutSchemeIsRejected() {
        assertTrue(UrlHandler.urlProblem("example.com/a").startsWith("url: needs a scheme"));
        assertTrue(UrlHandler.urlProblem("/sdcard/a.html").startsWith("url: needs a scheme"));
        assertTrue(UrlHandler.urlProblem("://x").startsWith("url: needs a scheme"));
    }

    @Test
    public void webAndAppLinksAreAllowed() {
        assertNull(UrlHandler.urlProblem("https://example.com/"));
        assertNull(UrlHandler.urlProblem("http://example.com/a?b=1"));
        assertNull(UrlHandler.urlProblem("HTTPS://EXAMPLE.COM/"));
        assertNull(UrlHandler.urlProblem("headroid-sample://login"));
    }

    @Test
    public void eachRefusedSchemeIsRejected() {
        String[] urls = {
            "intent://scan/#Intent;scheme=zxing;package=com.x;end",
            "android-app://com.x/https/example.com",
            "file:///sdcard/a.html",
            "content://com.x.provider/a",
            "data:text/html,<b>x</b>",
            "javascript:alert(1)",
            "about:blank",
            "tel:+15551234567",
            "sms:+15551234567",
            "smsto:+15551234567",
            "mms:+15551234567",
            "mmsto:+15551234567",
            "mailto:a@example.com",
            "voicemail:123",
            "geo:0,0?q=x",
            "market://details?id=com.x",
        };
        assertEquals(UrlHandler.REFUSED_SCHEMES.size(), urls.length);
        for (String url : urls) {
            String scheme = url.substring(0, url.indexOf(':'));
            assertEquals(url, "url: headroid does not open " + scheme + ": links", UrlHandler.urlProblem(url));
        }
    }

    @Test
    public void refusedSchemesIgnoreCase() {
        assertEquals("url: headroid does not open intent: links", UrlHandler.urlProblem("INTENT://x#Intent;end"));
        assertEquals("url: headroid does not open tel: links", UrlHandler.urlProblem("  Tel:123"));
    }
}
