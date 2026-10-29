# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared test helpers: a fake JSON-RPC server."""

import base64
import json
import socketserver
import threading

import pytest

PNG = b"\x89PNG\r\n\x1a\nfake"


class FakeServer:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.tree = []
        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                for line in self.rfile:
                    req = json.loads(line)
                    outer.calls.append((req["method"], req.get("params", {})))
                    m = req["method"]
                    if m == "boom":
                        resp = {"error": {"code": -32010, "message": "no focused editable"}}
                    elif m == "ui.tree":
                        resp = {"result": {"displayId": 1, "nodes": outer.tree}}
                    elif m == "display.screenshot":
                        data = base64.b64encode(PNG).decode()
                        resp = {"result": {"width": 1, "height": 1, "format": "png", "data": data}}
                    elif m == "display.create":
                        resp = {"result": {"displayId": 1, "width": 720, "height": 1600}}
                    elif m == "echo":
                        # a notification first, to exercise event stashing
                        note = {"jsonrpc": "2.0", "method": "event", "params": {"type": "x"}}
                        self.wfile.write(json.dumps(note).encode() + b"\n")
                        resp = {"result": req.get("params", {})}
                    else:
                        resp = {"result": {}}
                    resp.update({"jsonrpc": "2.0", "id": req["id"]})
                    self.wfile.write(json.dumps(resp).encode() + b"\n")

        class Srv(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.srv = Srv(("127.0.0.1", 0), Handler)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def fake_server():
    s = FakeServer()
    yield s
    s.close()
