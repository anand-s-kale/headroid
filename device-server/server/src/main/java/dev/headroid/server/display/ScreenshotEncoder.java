// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.display;

import dev.headroid.server.rpc.RpcException;

import android.graphics.Bitmap;
import android.media.Image;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.LinkedHashMap;
import java.util.Map;

/** Turns an RGBA_8888 {@link Image} into a base64 PNG or JPEG. */
public final class ScreenshotEncoder {

    private ScreenshotEncoder() {
        // not instantiable
    }

    public static Map<String, Object> encode(Image image, String format, int quality, int maxSize) {
        Bitmap.CompressFormat compressFormat;
        if ("png".equals(format)) {
            compressFormat = Bitmap.CompressFormat.PNG;
        } else if ("jpeg".equals(format) || "jpg".equals(format)) {
            compressFormat = Bitmap.CompressFormat.JPEG;
        } else {
            throw new RpcException(RpcException.INVALID_PARAMS, "format: expected png or jpeg");
        }
        if (quality < 0 || quality > 100) {
            throw new RpcException(RpcException.INVALID_PARAMS, "quality: expected 0..100");
        }

        Bitmap bitmap = toBitmap(image);
        try {
            int max = Math.max(bitmap.getWidth(), bitmap.getHeight());
            if (maxSize > 0 && max > maxSize) {
                float scale = (float) maxSize / max;
                Bitmap scaled = Bitmap.createScaledBitmap(bitmap, Math.max(1, Math.round(bitmap.getWidth() * scale)),
                        Math.max(1, Math.round(bitmap.getHeight() * scale)), true);
                bitmap.recycle();
                bitmap = scaled;
            }

            ByteArrayOutputStream out = new ByteArrayOutputStream();
            bitmap.compress(compressFormat, quality, out);

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("width", bitmap.getWidth());
            result.put("height", bitmap.getHeight());
            result.put("format", compressFormat == Bitmap.CompressFormat.PNG ? "png" : "jpeg");
            result.put("data", Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP));
            return result;
        } finally {
            bitmap.recycle();
        }
    }

    private static Bitmap toBitmap(Image image) {
        Image.Plane plane = image.getPlanes()[0];
        int width = image.getWidth();
        int height = image.getHeight();
        int pixelStride = plane.getPixelStride();
        int rowStride = plane.getRowStride();
        ByteBuffer buffer = plane.getBuffer().duplicate();
        buffer.rewind();

        // rows may be padded: decode the padded width, then crop
        int paddedWidth = rowStride / pixelStride;
        Bitmap padded = Bitmap.createBitmap(paddedWidth, height, Bitmap.Config.ARGB_8888);
        padded.copyPixelsFromBuffer(buffer);
        if (paddedWidth == width) {
            return padded;
        }
        Bitmap cropped = Bitmap.createBitmap(padded, 0, 0, width, height);
        padded.recycle();
        return cropped;
    }
}
