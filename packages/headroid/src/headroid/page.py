# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Page: one hidden display running one app, with Playwright-style locators."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Self

from .errors import TimeoutError
from .keys import press_code
from .locator import Locator
from .rpc import RpcError

if TYPE_CHECKING:
    from .device import Device, Display

DEFAULT_TIMEOUT = 10.0
IDLE_INTERVAL = 0.5


class Page:
    """Made by Device.new_page(app). Closing it stops the app (unless someone else uses it) and releases the
    hidden display."""

    def __init__(
        self,
        display: Display,
        app: str,
        *,
        device: Device | None = None,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        self.display = display
        self.app = app
        self.device = device
        self._clock = clock or display._clock
        self._sleep = sleep or display._sleep
        self.default_timeout = DEFAULT_TIMEOUT
        self.closed = False

    def set_default_timeout(self, seconds: float) -> None:
        """Timeout for locator actions and expect() on this page when none is given (default 10 s)."""
        self.default_timeout = float(seconds)

    # --- locators ---

    def locator(
        self,
        *,
        text: str | None = None,
        rid: str | None = None,
        desc: str | None = None,
        exact: bool = True,
    ) -> Locator:
        """Elements matching every criterion given."""
        return Locator(self, text=text, rid=rid, desc=desc, exact=exact)

    def get_by_text(self, text: str, exact: bool = False) -> Locator:
        """Like Playwright: a case-insensitive substring by default (Android often shows button labels in capitals);
        exact=True matches the whole text, case-sensitively."""
        suffix = ", exact=True" if exact else ""
        return Locator(self, text=text, exact=exact, name=f"get_by_text({text!r}{suffix})")

    def get_by_id(self, rid: str) -> Locator:
        """Full ("pkg:id/login_email") or short ("login_email") resource id; a React Native testID is one."""
        return Locator(self, rid=rid, name=f"get_by_id({rid!r})")

    def get_by_desc(self, desc: str, exact: bool = False) -> Locator:
        """Content description (accessibilityLabel in React Native); matched like get_by_text."""
        suffix = ", exact=True" if exact else ""
        return Locator(self, desc=desc, exact=exact, name=f"get_by_desc({desc!r}{suffix})")

    # --- page actions ---

    def screenshot(self, path: str | None = None) -> bytes:
        return self.display.screenshot(path)

    def tree(self) -> list[dict]:
        return self.display.tree()

    def press(self, key: str | int) -> None:
        """Presses a key on the hidden display: "BACK", "ENTER", "TAB", "DEL", "ESCAPE", DPAD keys, letters,
        digits. Keys that act on the whole phone (HOME, POWER, volume, Recents, ...) raise PermissionError."""
        self.display.key(press_code(key))

    def wait_for_idle(self, timeout: float | None = None) -> None:
        """Waits until the UI tree is the same on two reads 0.5 s apart."""
        timeout = self.default_timeout if timeout is None else timeout
        deadline = self._clock() + timeout
        previous = self.display.tree()
        while True:
            self._sleep(IDLE_INTERVAL)
            current = self.display.tree()
            if current == previous:
                return
            if self._clock() >= deadline:
                raise TimeoutError(f"{self.app}: the screen kept changing for {timeout}s")
            previous = current

    def close(self) -> None:
        """Stops the app unless someone else uses it, then releases the hidden display. Safe to call twice."""
        if self.closed:
            return
        self.closed = True
        try:
            self.display.stop(self.app)
        except (OSError, RpcError):
            pass
        if self.device is not None:
            self.device._forget(self.display)
        else:
            try:
                self.display.release()
            except (OSError, RpcError):
                pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<Page app={self.app!r} display={self.display.id}>"
