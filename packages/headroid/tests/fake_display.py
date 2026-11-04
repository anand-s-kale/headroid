# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""A fake Display that plays back a scripted sequence of UI trees, on a fake clock."""

from headroid.page import Page
from headroid.rpc import RpcError


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class FakeDisplay:
    """tree() returns reads[0], reads[1], ... and then keeps returning the last one."""

    def __init__(self, *reads, width=720, height=1600, unfocused_clears=0):
        self.reads = list(reads) or [[]]
        self.tree_calls = 0
        self.calls: list[tuple] = []
        self.info = {"displayId": 7, "width": width, "height": height}
        self.id = 7
        self.clock = Clock()
        self._clock = self.clock.now
        self._sleep = self.clock.sleep
        self.unfocused_clears = unfocused_clears

    def tree(self):
        i = min(self.tree_calls, len(self.reads) - 1)
        self.tree_calls += 1
        return self.reads[i]

    def tap(self, x, y):
        self.calls.append(("tap", x, y))

    def type(self, text):
        self.calls.append(("type", text))

    def clear_text(self):
        if self.unfocused_clears:
            self.unfocused_clears -= 1
            self.calls.append(("clear_text_failed",))
            raise RpcError(-32010, "no focused editable")
        self.calls.append(("clear_text",))

    def key(self, code, meta_state=0):
        self.calls.append(("key", code))

    def screenshot(self, path=None, format="png"):
        data = b"\x89PNG\r\n\x1a\nfake"
        if path:
            with open(path, "wb") as f:
                f.write(data)
        return data

    def stop(self, package):
        self.calls.append(("stop", package))
        return {"stopped": True}

    def release(self):
        self.calls.append(("release",))


def node(text="", rid="", desc="", bounds=(100, 100, 300, 200), visible=True, children=()):
    return {
        "text": text,
        "rid": rid,
        "desc": desc,
        "bounds": list(bounds),
        "visible": visible,
        "children": list(children),
    }


def page_with(*reads, **kw) -> tuple[Page, FakeDisplay]:
    d = FakeDisplay(*reads, **kw)
    return Page(d, "dev.headroid.sample"), d
