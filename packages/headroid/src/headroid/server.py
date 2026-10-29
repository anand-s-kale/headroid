# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Pushes, starts and stops the headroid device server on the phone."""

from __future__ import annotations

import subprocess
import time

from .adb import Adb, AdbError
from .rpc import RpcClient, RpcError

REMOTE_JAR = "/data/local/tmp/headroid-server.jar"
MAIN_CLASS = "dev.headroid.server.HeadroidServer"


class ServerProcess:
    def __init__(self, adb: Adb, jar_path: str, socket: str = "headroid"):
        self.adb = adb
        self.jar_path = jar_path
        self.socket = socket
        self.proc = None
        self.port: int | None = None
        self.client: RpcClient | None = None

    def start(self, connect_timeout: float = 10) -> RpcClient:
        self.adb.push(self.jar_path, REMOTE_JAR)
        cmd = f"CLASSPATH={REMOTE_JAR} app_process / {MAIN_CLASS} socket={self.socket}"
        self.proc = self.adb.popen_shell(cmd)
        self.port = self.adb.forward(f"localabstract:{self.socket}")
        deadline = time.monotonic() + connect_timeout
        last: Exception | None = None
        while time.monotonic() < deadline:
            client = None
            try:
                # adb accepts the forwarded connection even before the server listens,
                # so confirm with a real call.
                client = RpcClient("127.0.0.1", self.port)
                client.call("server.info")
                self.client = client
                return client
            except (OSError, RpcError, ValueError) as e:
                last = e
                if client is not None:
                    try:
                        client.close()
                    except OSError:
                        pass
                time.sleep(0.25)
        self.stop()
        raise TimeoutError(f"headroid server did not come up in {connect_timeout}s: {last}")

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
        if self.proc is not None:
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
