// Copyright 2026 Anand S Kale and the headroid contributors
// SPDX-License-Identifier: Apache-2.0
package dev.headroid.server;

import dev.headroid.server.rpc.LineReader;
import dev.headroid.server.rpc.RpcDispatcher;
import dev.headroid.server.rpc.RpcException;
import dev.headroid.server.session.Session;
import dev.headroid.server.session.Watchdog;

import com.genymobile.scrcpy.Workarounds;
import com.genymobile.scrcpy.util.Ln;

import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Looper;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * headroid device server entry point:
 * {@code CLASSPATH=/data/local/tmp/headroid-server.jar app_process / dev.headroid.server.HeadroidServer [socket=headroid]
 * [grace_ms=15000] [log=info]}.
 *
 * <p>Serves newline-delimited JSON-RPC 2.0 on a {@code localabstract} socket, one host connection at a time.
 */
public final class HeadroidServer {

    private static final int MAX_LINE_CHARS = 16 * 1024 * 1024;

    private final String socketName;
    private final Session session = new Session();
    private final RpcDispatcher dispatcher = new RpcDispatcher();
    private final Watchdog watchdog;

    private HeadroidServer(String socketName, long graceMs, ScheduledExecutorService scheduler) {
        this.socketName = socketName;
        this.watchdog = new Watchdog((task, delayMs) -> {
            ScheduledFuture<?> future = scheduler.schedule(task, delayMs, TimeUnit.MILLISECONDS);
            return () -> future.cancel(false);
        }, graceMs, session::teardown);
        session.register(dispatcher);
        dispatcher.setObserver((method, durationMs, errorCode) -> {
            if (Ln.isEnabled(Ln.Level.DEBUG)) {
                Ln.d(method + " " + durationMs + " ms" + (errorCode != null ? " error " + errorCode : ""));
            }
        });
    }

    public static void main(String... args) {
        int status = 0;
        try {
            run(args);
        } catch (Throwable t) {
            Ln.e("headroid server failed", t);
            status = 1;
        } finally {
            // the Android runtime may leave non-daemon threads behind
            System.exit(status);
        }
    }

    @SuppressWarnings("deprecation")
    private static void run(String... args) throws Exception {
        String socketName = "headroid";
        long graceMs = 15000;
        Ln.Level level = Ln.Level.INFO;
        for (String arg : args) {
            int eq = arg.indexOf('=');
            if (eq <= 0) {
                throw new IllegalArgumentException("Expected key=value, got " + arg);
            }
            String key = arg.substring(0, eq);
            String value = arg.substring(eq + 1);
            switch (key) {
                case "socket":
                    socketName = value;
                    break;
                case "grace_ms":
                    graceMs = Long.parseLong(value);
                    break;
                case "log":
                    level = Ln.Level.valueOf(value.toUpperCase(Locale.ENGLISH));
                    break;
                default:
                    throw new IllegalArgumentException("Unknown argument " + key);
            }
        }
        Ln.initLogLevel(level);

        Looper.prepareMainLooper();
        Workarounds.apply();

        ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();
        HeadroidServer server = new HeadroidServer(socketName, graceMs, scheduler);
        Runtime.getRuntime().addShutdownHook(new Thread(server.watchdog::teardownNow, "headroid-teardown"));

        Thread acceptThread = new Thread(() -> {
            try {
                server.acceptLoop();
            } catch (IOException e) {
                Ln.e("Socket failed", e);
            } finally {
                server.watchdog.teardownNow();
                System.exit(0);
            }
        }, "headroid-rpc");
        acceptThread.start();

        // UiAutomation and the display manager deliver callbacks on the main looper
        Looper.loop();
    }

    private void acceptLoop() throws IOException {
        try (LocalServerSocket serverSocket = new LocalServerSocket(socketName)) {
            // the host waits for this line before connecting
            System.out.println("headroid: listening on localabstract:" + socketName);
            System.out.flush();
            while (!session.isShutdownRequested()) {
                try (LocalSocket socket = serverSocket.accept()) {
                    watchdog.onConnect();
                    Ln.i("Host connected");
                    serve(socket);
                } catch (IOException e) {
                    Ln.w("Connection error: " + e.getMessage());
                } finally {
                    Ln.i("Host disconnected");
                    if (!session.isShutdownRequested()) {
                        watchdog.onDisconnect();
                    }
                }
            }
        }
    }

    private void serve(LocalSocket socket) throws IOException {
        InputStream in = socket.getInputStream();
        OutputStream out = socket.getOutputStream();
        LineReader reader = new LineReader(in, MAX_LINE_CHARS);
        while (true) {
            String line;
            try {
                line = reader.readLine();
            } catch (LineReader.LineTooLongException e) {
                write(out, "{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{\"code\":" + RpcException.INVALID_REQUEST
                        + ",\"message\":\"Request line too long\"}}");
                continue;
            }
            if (line == null) {
                return; // host closed the connection
            }
            String response = dispatcher.handleLine(line);
            if (response != null) {
                write(out, response);
            }
            if (session.isShutdownRequested()) {
                Ln.i("Shutdown requested");
                watchdog.teardownNow();
                return;
            }
        }
    }

    private static void write(OutputStream out, String line) throws IOException {
        synchronized (out) {
            out.write((line + "\n").getBytes(StandardCharsets.UTF_8));
            out.flush();
        }
    }
}
