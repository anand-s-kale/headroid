// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

import com.genymobile.scrcpy.util.Ln;
import com.genymobile.scrcpy.wrappers.ServiceManager;
import com.genymobile.scrcpy.wrappers.WindowManager;

import android.graphics.PixelFormat;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;

/**
 * A virtual display nobody sees: its only consumer is an {@link ImageReader} that is always drained, keeping the
 * latest frame for screenshots. No encoder runs.
 */
public final class HiddenDisplay implements ManagedDisplay {

    private static final int MAX_IMAGES = 3;

    private final VirtualDisplay virtualDisplay;
    private final ImageReader reader;
    private final HandlerThread thread;
    private final FrameStore<Image> frames;
    private final int width;
    private final int height;
    private final int dpi;
    private final int flags;

    private HiddenDisplay(VirtualDisplay virtualDisplay, ImageReader reader, HandlerThread thread, FrameStore<Image> frames, int width,
            int height, int dpi, int flags) {
        this.virtualDisplay = virtualDisplay;
        this.reader = reader;
        this.thread = thread;
        this.frames = frames;
        this.width = width;
        this.height = height;
        this.dpi = dpi;
        this.flags = flags;
    }

    public static HiddenDisplay create(int width, int height, int dpi) throws Exception {
        if (width <= 0 || height <= 0 || dpi <= 0 || width > 4096 || height > 4096) {
            throw new IllegalArgumentException("Invalid display size " + width + "x" + height + "/" + dpi);
        }

        HandlerThread thread = new HandlerThread("headroid-frames");
        thread.start();
        Handler handler = new Handler(thread.getLooper());

        ImageReader reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, MAX_IMAGES);
        FrameStore<Image> frames = new FrameStore<>(Image::close);
        reader.setOnImageAvailableListener(r -> {
            try {
                frames.offer(r.acquireLatestImage());
            } catch (IllegalStateException e) {
                // all buffers held: the next callback catches up
                Ln.w("Frame dropped: " + e.getMessage());
            }
        }, handler);

        int flags = DisplayFlags.forSdk(Build.VERSION.SDK_INT);
        VirtualDisplay vd;
        try {
            vd = ServiceManager.getDisplayManager().createNewVirtualDisplay("headroid", width, height, dpi, reader.getSurface(), flags);
        } catch (Exception e) {
            reader.close();
            thread.quitSafely();
            throw e;
        }

        int displayId = vd.getDisplay().getDisplayId();
        if (Build.VERSION.SDK_INT >= 29) {
            // never show a keyboard on the hidden display, and never move it to the owner's display
            ServiceManager.getWindowManager().setDisplayImePolicy(displayId, WindowManager.DISPLAY_IME_POLICY_HIDE);
        }
        Ln.i("Hidden display " + displayId + ": " + width + "x" + height + "/" + dpi + " flags=" + DisplayFlags.describe(flags));
        return new HiddenDisplay(vd, reader, thread, frames, width, height, dpi, flags);
    }

    @Override
    public int id() {
        return virtualDisplay.getDisplay().getDisplayId();
    }

    public int width() {
        return width;
    }

    public int height() {
        return height;
    }

    public int dpi() {
        return dpi;
    }

    public int flags() {
        return flags;
    }

    public FrameStore<Image> frames() {
        return frames;
    }

    @Override
    public void release() {
        int id = id();
        // DESTROY_CONTENT_ON_REMOVAL: activities still on the display are destroyed, not moved to display 0
        virtualDisplay.release();
        frames.close();
        reader.close();
        thread.quitSafely();
        Ln.i("Hidden display " + id + " released");
    }
}
