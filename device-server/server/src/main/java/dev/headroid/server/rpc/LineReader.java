// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/** Reads UTF-8 lines with a size cap, so one huge request cannot exhaust the server's memory. */
public final class LineReader {

    public static final class LineTooLongException extends IOException {
        LineTooLongException(int max) {
            super("line longer than " + max + " bytes");
        }
    }

    private final InputStream in;
    private final int maxBytes;
    private final ByteArrayOutputStream buffer = new ByteArrayOutputStream();

    public LineReader(InputStream in, int maxBytes) {
        this.in = new BufferedInputStream(in);
        this.maxBytes = maxBytes;
    }

    /** The next line without its terminator, or null at end of stream. Throws after skipping a line over the cap. */
    public String readLine() throws IOException {
        buffer.reset();
        boolean tooLong = false;
        boolean any = false;
        int b;
        while ((b = in.read()) != -1) {
            any = true;
            if (b == '\n') {
                if (tooLong) {
                    throw new LineTooLongException(maxBytes);
                }
                return decode();
            }
            if (!tooLong) {
                if (buffer.size() >= maxBytes) {
                    tooLong = true;
                    buffer.reset();
                } else {
                    buffer.write(b);
                }
            }
        }
        if (tooLong) {
            throw new LineTooLongException(maxBytes);
        }
        return any ? decode() : null;
    }

    private String decode() {
        String line = new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        if (line.endsWith("\r")) {
            line = line.substring(0, line.length() - 1);
        }
        return line;
    }
}
