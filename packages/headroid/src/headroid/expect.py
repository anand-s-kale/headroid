# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""expect(locator): assertions that retry until they hold or the timeout passes."""

from __future__ import annotations

from collections.abc import Callable

from .locator import POLL_SECONDS, Locator

Check = Callable[[list[dict]], tuple[bool, str]]


class LocatorAssertions:
    def __init__(self, locator: Locator, timeout: float | None = None):
        self._loc = locator
        self._timeout = timeout

    def _retry(self, check: Check, call: str, expected: str, timeout: float | None) -> None:
        loc = self._loc
        page = loc._page
        if timeout is None:
            timeout = self._timeout if self._timeout is not None else page.default_timeout
        deadline = page._clock() + timeout
        while True:
            ok, actual = check(page.display.tree())
            if ok:
                return
            if page._clock() >= deadline:
                raise AssertionError(
                    f"expect({loc!r}).{call} failed after {timeout}s\n"
                    f"  expected: {expected}\n"
                    f"  actual:   {actual}"
                )
            page._sleep(POLL_SECONDS)

    def _visible(self, nodes: list[dict]) -> tuple[bool, str]:
        node = self._loc._pick(nodes)
        if node is None:
            return False, "not found"
        if not node.get("visible", True):
            return False, "present but not visible"
        if not self._loc._settle().ready(node):
            return False, f"off screen at {node['bounds']}"
        return True, "visible"

    def _text_check(self, test: Callable[[str], bool]) -> Check:
        def check(nodes):
            node = self._loc._pick(nodes)
            if node is None:
                return False, "not found"
            text = node.get("text") or ""
            return test(text), repr(text)

        return check

    def to_be_visible(self, timeout: float | None = None) -> None:
        """The element exists, is visible and lies fully on the display."""
        self._retry(self._visible, "to_be_visible()", "visible", timeout)

    def to_be_hidden(self, timeout: float | None = None) -> None:
        """The element is absent, invisible or off the display."""

        def check(nodes):
            ok, actual = self._visible(nodes)
            return not ok, actual

        self._retry(check, "to_be_hidden()", "hidden", timeout)

    def to_have_text(self, text: str, timeout: float | None = None) -> None:
        """The element's text equals text."""
        check = self._text_check(lambda t: t == text)
        self._retry(check, f"to_have_text({text!r})", repr(text), timeout)

    def to_contain_text(self, text: str, timeout: float | None = None) -> None:
        """The element's text contains text."""
        check = self._text_check(lambda t: text in t)
        self._retry(check, f"to_contain_text({text!r})", f"text containing {text!r}", timeout)

    def to_have_count(self, count: int, timeout: float | None = None) -> None:
        """Exactly count elements match (any visibility)."""

        def check(nodes):
            n = len(self._loc._all(nodes))
            return n == count, f"{n} element(s)"

        self._retry(check, f"to_have_count({count})", f"{count} element(s)", timeout)


def expect(locator: Locator, timeout: float | None = None) -> LocatorAssertions:
    """Assertions on a locator. Each retries every 0.2 s until it holds or the timeout passes (per call,
    else the one given here, else the page's default), then raises AssertionError with expected and actual."""
    if not isinstance(locator, Locator):
        raise TypeError(f"expect() takes a Locator, got {type(locator).__name__}")
    return LocatorAssertions(locator, timeout)
