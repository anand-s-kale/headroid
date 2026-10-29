# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Newline-delimited JSON-RPC 2.0 client."""

from __future__ import annotations

import json
import socket
import threading


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class RpcClient:
    def __init__(self, host: str, port: int, timeout: float = 30):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self._file = self.sock.makefile("rb")
        self._lock = threading.Lock()
        self._next_id = 0
        self.events: list[dict] = []

    def call(self, method: str, **params) -> dict:
        with self._lock:
            self._next_id += 1
            rid = self._next_id
            req = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
            self.sock.sendall(json.dumps(req).encode("utf-8") + b"\n")
            while True:
                line = self._file.readline()
                if not line:
                    raise ConnectionError("connection closed by server")
                msg = json.loads(line)
                if msg.get("method") == "event" and "id" not in msg:
                    self.events.append(msg.get("params", {}))
                    continue
                if msg.get("id") != rid:
                    continue
                if msg.get("error") is not None:
                    err = msg["error"]
                    raise RpcError(err.get("code", -32000), err.get("message", ""))
                return msg.get("result") or {}

    def close(self) -> None:
        try:
            self._file.close()
        finally:
            self.sock.close()
