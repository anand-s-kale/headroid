# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Pushes, starts and stops the headroid device server on the phone."""

from __future__ import annotations

import hashlib
import secrets
import time

from .adb import Adb, AdbError
from .rpc import RpcClient, RpcError

REMOTE_DIR = "/data/local/tmp"
MAIN_CLASS = "dev.headroid.server.HeadroidServer"
# How long the server keeps the session (displays, apps, mutes) without a host. Long enough for a wireless adb
# reconnect or a short laptop sleep; after it the server tears everything down and exits.
GRACE_S = 60

# Calls that read state only: safe to resend after a reconnect. Actions are not resent, since they may have run.
SAFE_TO_RETRY = {"server.info", "display.list", "display.screenshot", "ui.tree"}


def remote_jar_path(jar_path: str) -> str:
    """Where the jar goes on the phone, named by its content so a push never overwrites a jar that another
    running server (another session, another headroid version) still has open."""
    with open(jar_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()[:12]
    return f"{REMOTE_DIR}/headroid-server-{digest}.jar"


class ReconnectingClient:
    """An RpcClient that survives a dropped connection (wireless adb reconnect, laptop sleep).

    On a connection error it reconnects to the same server, which kept the session. Read-only calls are then
    resent; for actions it raises ConnectionError saying the action may or may not have run.
    """

    def __init__(self, server: ServerProcess, client: RpcClient):
        self._server = server
        self._client = client

    @property
    def events(self) -> list[dict]:
        return self._client.events

    def call(self, method: str, **params) -> dict:
        try:
            return self._client.call(method, **params)
        except (ConnectionError, OSError) as first:
            if method == "server.shutdown":
                raise
            self._client = self._server.reconnect()
            if method in SAFE_TO_RETRY:
                return self._client.call(method, **params)
            raise ConnectionError(
                f"connection to the phone dropped during {method} and was restored; "
                "the action may or may not have run"
            ) from first

    def close(self) -> None:
        self._client.close()


class ServerProcess:
    def __init__(
        self, adb: Adb, jar_path: str, socket: str | None = None, grace_s: float = GRACE_S
    ):
        self.adb = adb
        self.jar_path = jar_path
        self.socket = socket or f"headroid-{secrets.token_hex(4)}"
        self.grace_s = grace_s
        self.port: int | None = None
        self.client: ReconnectingClient | None = None
        self.hardware_serial = ""  # ro.serialno, to find the phone again under a new adb serial

    def start(self, connect_timeout: float = 10) -> ReconnectingClient:
        remote = remote_jar_path(self.jar_path)
        self.hardware_serial = self.adb.shell("getprop ro.serialno").strip()
        self.adb.push(self.jar_path, remote)
        # setsid and closed stdio: the server must outlive this adb shell, so a dropped wireless connection
        # does not kill it (it would take the session with it); its own watchdog ends it when no host returns.
        cmd = (
            f"CLASSPATH={remote} setsid app_process / {MAIN_CLASS} socket={self.socket} "
            f"grace_ms={int(self.grace_s * 1000)} </dev/null >/dev/null 2>&1 &"
        )
        self.adb.shell(cmd)
        try:
            client = self._connect(connect_timeout)
        except TimeoutError as e:
            self.stop()
            raise TimeoutError(f"headroid server did not come up in {connect_timeout}s: {e}") from e
        self.client = ReconnectingClient(self, client)
        return self.client

    def _connect(self, timeout: float) -> RpcClient:
        deadline = time.monotonic() + timeout
        last: Exception | None = None
        while time.monotonic() < deadline:
            client = None
            try:
                if self.port is None:
                    if self.hardware_serial and not self.adb.relocate(self.hardware_serial):
                        raise AdbError("the phone is not attached (yet)")
                    self.port = self.adb.forward(f"localabstract:{self.socket}")
                # adb accepts the forwarded connection even before the server listens,
                # so confirm with a real call.
                client = RpcClient("127.0.0.1", self.port)
                client.call("server.info")
                return client
            except (OSError, RpcError, ValueError, AdbError) as e:
                last = e
                if client is not None:
                    try:
                        client.close()
                    except OSError:
                        pass
                time.sleep(0.25)
        raise TimeoutError(str(last))

    def reconnect(self) -> RpcClient:
        """Connects again to the same server, for up to the grace period. A new adb transport needs a new
        port forward, so the old one is dropped first."""
        if self.port is not None:
            try:
                self.adb.remove_forward(self.port)
            except AdbError:
                pass
            self.port = None
        try:
            return self._connect(self.grace_s)
        except TimeoutError as e:
            raise ConnectionError(
                f"lost the phone and could not reconnect within {self.grace_s:.0f}s; "
                f"the server has torn the session down: {e}"
            ) from e

    def stop(self) -> None:
        if self.client is not None:
            try:
                self.client.call("server.shutdown")
            except (OSError, RpcError):
                pass
            try:
                self.client.close()
            except OSError:
                pass
            self.client = None
        if self.port is not None:
            try:
                self.adb.remove_forward(self.port)
            except AdbError:
                pass
            self.port = None
