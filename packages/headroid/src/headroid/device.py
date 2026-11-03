# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""High-level Device and Display objects."""

from __future__ import annotations

import base64
import os
import time
from collections.abc import Callable
from typing import Self

from .adb import Adb
from .jar import resolve_jar
from .rpc import RpcClient, RpcError
from .server import ServerProcess


class Display:
    def __init__(
        self,
        client: RpcClient,
        info: dict,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._c = client
        self.info = info
        self.id: int = info["displayId"]
        self._clock = clock
        self._sleep = sleep

    def launch(
        self,
        package: str,
        activity: str | None = None,
        mute: bool = True,
        mute_notifications: bool = False,
    ) -> None:
        """Starts the app on this display.

        mute: silence its sound and vibration (app-ops, restored when the app is stopped or the session ends).
        mute_notifications: also block its notifications by revoking the notification permission. The app
        can see this and may ask for the permission again, so it is off by default; skipped if the app is
        already running.
        """
        self._c.call(
            "app.launch",
            displayId=self.id,
            package=package,
            activity=activity,
            mute=mute,
            muteNotifications=mute_notifications,
        )

    def tap(self, x: int, y: int) -> None:
        self._c.call("input.tap", displayId=self.id, x=x, y=y)

    def long_press(self, x: int, y: int, duration_ms: int = 600) -> None:
        self._c.call("input.longPress", displayId=self.id, x=x, y=y, durationMs=duration_ms)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._c.call(
            "input.swipe", displayId=self.id, x1=x1, y1=y1, x2=x2, y2=y2, durationMs=duration_ms
        )

    def key(self, code: int, meta_state: int = 0) -> None:
        self._c.call("input.key", displayId=self.id, keyCode=code, metaState=meta_state)

    def type(self, text: str) -> None:
        self._c.call("input.text", displayId=self.id, text=text)

    def screenshot(self, path: str | None = None, format: str = "png") -> bytes:
        res = self._c.call("display.screenshot", displayId=self.id, format=format)
        data = base64.b64decode(res["data"])
        if path:
            with open(path, "wb") as f:
                f.write(data)
        return data

    def tree(self) -> list[dict]:
        return self._c.call("ui.tree", displayId=self.id).get("nodes", [])

    def find(
        self, text: str | None = None, rid: str | None = None, desc: str | None = None
    ) -> dict | None:
        if text is None and rid is None and desc is None:
            return None

        def match(n: dict) -> bool:
            if text is not None and n.get("text") != text:
                return False
            if desc is not None and n.get("desc") != desc:
                return False
            if rid is not None:
                nrid = n.get("rid") or ""
                if nrid != rid and nrid.rsplit("/", 1)[-1] != rid:
                    return False
            return True

        def walk(nodes):
            for n in nodes:
                if match(n):
                    return n
                found = walk(n.get("children") or [])
                if found:
                    return found
            return None

        return walk(self.tree())

    def _on_screen(self, node: dict) -> bool:
        left, top, right, bottom = node["bounds"]
        width, height = self.info["width"], self.info["height"]
        return 0 <= left < right <= width and 0 <= top < bottom <= height

    def wait_for(
        self,
        text: str | None = None,
        rid: str | None = None,
        desc: str | None = None,
        timeout: float = 10.0,
    ) -> dict:
        """Waits until the node is visible, fully on the display and at the same bounds on two reads.

        During an activity transition the tree reports the incoming window's nodes at their animated
        position (shifted by a display width for ~0.8 s), so acting on the first sighting misses.
        """
        deadline = self._clock() + timeout
        last = None
        while self._clock() < deadline:
            node = self.find(text=text, rid=rid, desc=desc)
            if node is not None and node.get("visible", True) and self._on_screen(node):
                if last is not None and node["bounds"] == last:
                    return node
                last = node["bounds"]
            else:
                last = None
            self._sleep(0.2)
        criteria = {k: v for k, v in (("text", text), ("rid", rid), ("desc", desc)) if v is not None}
        raise TimeoutError(f"not found on screen and settled within {timeout}s: {criteria}")

    def click(
        self,
        text: str | None = None,
        rid: str | None = None,
        desc: str | None = None,
        timeout: float = 10.0,
    ) -> dict:
        node = self.wait_for(text=text, rid=rid, desc=desc, timeout=timeout)
        left, top, right, bottom = node["bounds"]
        self.tap((left + right) // 2, (top + bottom) // 2)
        return node

    def fill(
        self,
        value: str,
        text: str | None = None,
        rid: str | None = None,
        desc: str | None = None,
        timeout: float = 10.0,
    ) -> dict:
        node = self.click(text=text, rid=rid, desc=desc, timeout=timeout)
        self.type(value)
        return node

    def release(self) -> None:
        self._c.call("display.release", displayId=self.id)


class Device:
    def __init__(self, client: RpcClient, server: ServerProcess | None = None):
        self.client = client
        self.server = server
        self.displays: list[Display] = []

    @classmethod
    def connect(cls, serial: str | None = None, jar: str | None = None) -> Self:
        jar = resolve_jar(jar)
        adb = Adb(serial, os.environ.get("ADB", "adb"))
        server = ServerProcess(adb, jar)
        return cls(server.start(), server)

    def info(self) -> dict:
        return self.client.call("server.info")

    def create_display(self, width: int = 720, height: int = 1600, dpi: int = 320) -> Display:
        res = self.client.call("display.create", width=width, height=height, dpi=dpi)
        d = Display(self.client, res)
        self.displays.append(d)
        return d

    def close(self) -> None:
        for d in self.displays:
            try:
                d.release()
            except (OSError, RpcError):
                pass
        self.displays.clear()
        if self.server is not None:
            self.server.stop()
        else:
            self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
