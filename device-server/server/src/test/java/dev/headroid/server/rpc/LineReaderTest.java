// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server.rpc;

import org.junit.Assert;
import org.junit.Test;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public class LineReaderTest {

    private static LineReader reader(String text, int max) {
        return new LineReader(new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8)), max);
    }

    @Test
    public void readsUtf8Lines() throws IOException {
        LineReader r = reader("a\né😀\r\nlast", 100);
        Assert.assertEquals("a", r.readLine());
        Assert.assertEquals("é😀", r.readLine());
        Assert.assertEquals("last", r.readLine()); // final line without newline
        Assert.assertNull(r.readLine());
    }

    @Test
    public void tooLongLineIsSkippedAndReaderRecovers() throws IOException {
        LineReader r = reader("0123456789\nok\n", 5);
        try {
            r.readLine();
            Assert.fail();
        } catch (LineReader.LineTooLongException e) {
            // expected
        }
        Assert.assertEquals("ok", r.readLine());
    }

    @Test
    public void emptyStreamIsEof() throws IOException {
        Assert.assertNull(reader("", 10).readLine());
    }
}
