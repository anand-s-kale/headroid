# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Locator: a lazy description of elements on a Page, re-resolved against the UI tree on every action."""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from .device import Settle
from .errors import TimeoutError
from .rpc import RpcError

if TYPE_CHECKING:
    from .page import Page

POLL_SECONDS = 0.2
NO_FOCUSED_EDITABLE = -32010


def _norm(s: str) -> str:
    return " ".join(s.split()).casefold()


def _walk(nodes: list[dict]):
    for n in nodes:
        yield n
        yield from _walk(n.get("children") or [])


def _short_rid(rid: str) -> str:
    return rid.rsplit("/", 1)[-1]


class Locator:
    """Finds elements by text, resource id (a React Native testID is one) or content description.

    Nothing is looked up when the locator is made: every action reads the tree again. Actions (click, fill,
    text) wait until the element exists, is visible, lies fully on the display and has the same bounds on
    two reads in a row, up to the timeout (the page's default unless given), then raise
    headroid.TimeoutError naming the locator and the closest texts on screen. With several matches, actions
    use the first in tree order unless nth() picks another.
    """

    def __init__(
        self,
        page: Page,
        *,
        text: str | None = None,
        rid: str | None = None,
        desc: str | None = None,
        exact: bool = True,
        index: int = 0,
        name: str | None = None,
    ):
        if text is None and rid is None and desc is None:
            raise ValueError("a locator needs text=, rid= or desc=")
        self._page = page
        self._text = text
        self._rid = rid
        self._desc = desc
        self._exact = exact
        self._index = index
        self._name = name or self._default_name()

    def _default_name(self) -> str:
        parts = [
            f"{k}={v!r}"
            for k, v in (("text", self._text), ("rid", self._rid), ("desc", self._desc))
            if v is not None
        ]
        if not self._exact:
            parts.append("exact=False")
        return f"locator({', '.join(parts)})"

    def __repr__(self) -> str:
        return self._name

    # --- narrowing ---

    def nth(self, index: int) -> Locator:
        """The index-th match in tree order (0-based; -1 is the last)."""
        return Locator(
            self._page,
            text=self._text,
            rid=self._rid,
            desc=self._desc,
            exact=self._exact,
            index=index,
            name=f"{self._name}.nth({index})",
        )

    @property
    def first(self) -> Locator:
        return self.nth(0)

    @property
    def last(self) -> Locator:
        return self.nth(-1)

    # --- matching ---

    def _matches_node(self, n: dict) -> bool:
        if self._text is not None:
            t = n.get("text") or ""
            if self._exact and t != self._text:
                return False
            if not self._exact and _norm(self._text) not in _norm(t):
                return False
        if self._desc is not None:
            d = n.get("desc") or ""
            if self._exact and d != self._desc:
                return False
            if not self._exact and _norm(self._desc) not in _norm(d):
                return False
        if self._rid is not None:
            r = n.get("rid") or ""
            if r != self._rid and _short_rid(r) != self._rid:
                return False
        return True

    def _all(self, nodes: list[dict]) -> list[dict]:
        return [n for n in _walk(nodes) if self._matches_node(n)]

    def _pick(self, nodes: list[dict]) -> dict | None:
        found = self._all(nodes)
        try:
            return found[self._index]
        except IndexError:
            return None

    def _settle(self) -> Settle:
        info = self._page.display.info
        return Settle(info["width"], info["height"])

    def _timeout(self, timeout: float | None) -> float:
        return self._page.default_timeout if timeout is None else timeout

    # --- immediate queries (one tree read, no waiting) ---

    def count(self) -> int:
        """Number of matching elements on the current screen (any visibility)."""
        return len(self._all(self._page.display.tree()))

    def is_visible(self) -> bool:
        """True when the element exists, is visible and lies fully on the display right now."""
        node = self._pick(self._page.display.tree())
        return node is not None and self._settle().ready(node)

    # --- auto-waiting actions ---

    def _wait(self, timeout: float | None, settled: bool) -> dict:
        timeout = self._timeout(timeout)
        page = self._page
        deadline = page._clock() + timeout
        settle = self._settle()
        nodes: list[dict] = []
        node = None
        while True:
            nodes = page.display.tree()
            node = self._pick(nodes)
            done = settle.observe(node) if settled else node is not None
            if done:
                return node
            if page._clock() >= deadline:
                break
            page._sleep(POLL_SECONDS)
        want = "visible, on screen and settled" if settled else "present"
        raise TimeoutError(
            f"{self._name}: not {want} within {timeout}s (last read: {self._state(nodes, node, settle)})."
            f"{self._closest(nodes)}"
        )

    def _state(self, nodes: list[dict], node: dict | None, settle: Settle) -> str:
        if node is None:
            n = len(self._all(nodes))
            if n and self._index:
                return f"{n} match(es), none at index {self._index}"
            return "not found"
        if not node.get("visible", True):
            return "found but not visible"
        if not settle.ready(node):
            return f"found off screen at {node['bounds']}"
        return f"still moving, at {node['bounds']}"

    def _closest(self, nodes: list[dict]) -> str:
        if self._text is not None or self._desc is not None:
            target = self._text if self._text is not None else self._desc
            seen = [v for n in _walk(nodes) for v in (n.get("text"), n.get("desc")) if v]
        else:
            target = _short_rid(self._rid or "")
            seen = [_short_rid(n["rid"]) for n in _walk(nodes) if n.get("rid")]
        seen = list(dict.fromkeys(seen))
        if not seen:
            return " The screen has no texts."
        close = difflib.get_close_matches(target, seen, n=3, cutoff=0.4)
        if close:
            return " Closest on screen: " + ", ".join(repr(s) for s in close) + "."
        return (
            " On screen: "
            + ", ".join(repr(s) for s in seen[:5])
            + ("..." if len(seen) > 5 else "")
            + "."
        )

    def click(self, timeout: float | None = None) -> None:
        """Waits until the element has settled, then taps its centre."""
        node = self._wait(timeout, settled=True)
        left, top, right, bottom = node["bounds"]
        self._page.display.tap((left + right) // 2, (top + bottom) // 2)

    def fill(self, value: str, timeout: float | None = None) -> None:
        """Taps the field, empties it and types value."""
        timeout = self._timeout(timeout)
        page = self._page
        self.click(timeout)
        deadline = page._clock() + timeout
        while True:  # the tap's focus can land a moment after the tap
            try:
                page.display.clear_text()
                break
            except RpcError as e:
                if e.code != NO_FOCUSED_EDITABLE or page._clock() >= deadline:
                    raise
                page._sleep(POLL_SECONDS)
        if value:
            page.display.type(value)

    def text(self, timeout: float | None = None) -> str:
        """The element's text, once it exists (it need not be on screen)."""
        return self._wait(timeout, settled=False).get("text") or ""
