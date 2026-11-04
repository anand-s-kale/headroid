# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""ARTEMIS device driver that works on a headroid hidden display.

ARTEMIS selects it with ARTEMIS_DRIVER=headroid. Each driver owns one headroid Device connection and one hidden
display: connect() creates the display, disconnect() releases it and ends the headroid session (which stops the apps
it launched unless someone else uses them, and restores their muting).

Nothing here reads from or acts on display 0, the phone's own screen: screenshots, the UI tree and input go to the
hidden display through the headroid server, and execute_shell refuses commands that would reach display 0.
"""

from __future__ import annotations

import asyncio
import base64
import functools
import logging
import os
import shlex
import struct
import zlib
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from artemis.drivers.base import BaseDeviceDriver, KeyCode, ScreenData, SwipeDirection

from ..adb import Adb, AdbError
from ..device import Device
from ..rpc import RpcError

logger = logging.getLogger(__name__)

DISPLAY_WIDTH = 720
DISPLAY_HEIGHT = 1600
DISPLAY_DPI = 320

NO_FRAME = -32011  # the display has not drawn anything yet (no app on it)

# FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_MULTIPLE_TASK | FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS, as headroid's launches
_OPEN_URL_FLAGS = "0x18800000"

_KEY_CODES = {
    KeyCode.HOME.value: 3,
    KeyCode.BACK.value: 4,
    KeyCode.ENTER.value: 66,
    KeyCode.DELETE.value: 67,
    KeyCode.POWER.value: 26,
    KeyCode.APP_SWITCH.value: 187,
    KeyCode.VOLUME_UP.value: 24,
    KeyCode.VOLUME_DOWN.value: 25,
    "del": 67,
    "forward_del": 112,
    "tab": 61,
    "space": 62,
    "escape": 111,
    "move_home": 122,
    "move_end": 123,
    "dpad_up": 19,
    "dpad_down": 20,
    "dpad_left": 21,
    "dpad_right": 22,
    "dpad_center": 23,
    "menu": 82,
    "search": 84,
}

# Keys Android handles for the whole phone or on its main screen, whatever display the event names.
_REFUSED_KEYS = {
    3: "HOME",  # also closes system dialogs and wakes dreams on the main screen
    24: "VOLUME_UP",
    25: "VOLUME_DOWN",
    26: "POWER",
    83: "NOTIFICATION",
    120: "SYSRQ",  # a screenshot of the main screen
    164: "VOLUME_MUTE",
    187: "APP_SWITCH",  # Recents opens on display 0
    219: "ASSIST",
    220: "BRIGHTNESS_DOWN",
    221: "BRIGHTNESS_UP",
    223: "SLEEP",
    224: "WAKEUP",
    231: "VOICE_ASSIST",
    276: "SOFT_SLEEP",
    280: "SYSTEM_NAVIGATION_UP",
    281: "SYSTEM_NAVIGATION_DOWN",
    282: "SYSTEM_NAVIGATION_LEFT",
    283: "SYSTEM_NAVIGATION_RIGHT",
}


def tree_to_elements(nodes: list[dict]) -> list[dict]:
    """Flattens a headroid UI tree into ARTEMIS's element dicts.

    Same keys, values and filter as ARTEMIS's XML parser (artemis/drivers/android/hierarchy.py): every node with
    a non-zero area that has text, a content description, a resource id or is clickable, in document order. Nodes
    headroid reports as not visible are skipped, as uiautomator leaves them out of its dump.
    """
    elements: list[dict] = []

    def walk(items: list[dict]) -> None:
        for node in items:
            if node.get("visible", True):
                _append_element(elements, node)
            walk(node.get("children") or [])

    walk(nodes)
    return elements


def _append_element(elements: list[dict], node: dict) -> None:
    bounds = node.get("bounds")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return
    x1, y1, x2, y2 = (int(v) for v in bounds)
    if x1 >= x2 or y1 >= y2:
        return
    text = node.get("text") or node.get("desc") or ""
    resource_id = node.get("rid") or ""
    clickable = bool(node.get("clickable"))
    if text or clickable or resource_id:
        elements.append(
            {
                "text": text,
                "resource_id": resource_id,
                "class": node.get("cls") or "",
                "clickable": clickable,
                "bounds": [x1, y1, x2, y2],
                "center": [(x1 + x2) // 2, (y1 + y2) // 2],
            }
        )


@functools.lru_cache(maxsize=4)
def _blank_png(width: int, height: int) -> bytes:
    """A black grayscale PNG, shown while the hidden display has no frame."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    rows = (b"\x00" * (width + 1)) * height  # filter byte 0 + one gray byte per pixel
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )


# --- execute_shell policy --------------------------------------------------------------------------------------

# Shell syntax that could chain, substitute, redirect or hide a command. Quotes and backslashes too: an allowed
# command never needs them, so nothing can be smuggled past the tokenizer.
_SHELL_SYNTAX = set(";&|^`$()<>\n\r\\'\"{}*?[]~!#")

_ALLOWED_SUMMARY = (
    "execute_shell under headroid only allows read-only package and property queries (getprop [name], pm list"
    " packages [options], pm path <package>) and launches on the hidden display (am start / am start-activity"
    " --display {id} -f 0x18800000 -n ...); nothing may read from or act on display 0 (the phone's own screen)."
)


def shell_refusal(command: str, hidden_display_id: int) -> str | None:
    """Why `command` must not run on the phone, or None. A strict allow-list: ARTEMIS's manual-mode actions do
    not shell out on the headroid driver, so this backstop only lets through what cannot reach display 0."""
    refused = f"refused `{command}`: " + _ALLOWED_SUMMARY.format(id=hidden_display_id)
    if set(command) & _SHELL_SYNTAX:
        return (
            refused
            + " Shell syntax (; & | ^ ` $ ( ) < > quotes, backslashes, newlines) is not allowed."
        )
    words = shlex.split(command, posix=True)
    if not words:
        return refused
    program, args = words[0], words[1:]
    if program == "getprop" and len(args) <= 1:
        return None
    if program == "pm" and args[:2] == ["list", "packages"]:
        return None
    if program == "pm" and len(args) == 2 and args[0] == "path":
        return None
    if program == "am" and args[:1] in (["start"], ["start-activity"]):
        why = _am_start_problem(args[1:], hidden_display_id)
        if why is None:
            return None
        return (
            f"refused `{command}`: {why} execute_shell under headroid only starts activities the way headroid"
            f" launches apps: `am {args[0]} --display {hidden_display_id} -f 0x18800000` (a new task of its own,"
            " excluded from Recents) with only -n, -a, -d, -c or -t besides; anything else could reach display 0"
            " (the phone's own screen) or an app the owner is using there."
        )
    return refused


# Options of `am start` that only describe the intent; each takes one value.
_AM_START_INTENT_OPTIONS = {"-n", "-a", "-d", "-c", "-t"}
# NEW_TASK | MULTIPLE_TASK | EXCLUDE_FROM_RECENTS: a fresh task of its own, as headroid's launches
_AM_START_REQUIRED_FLAGS = 0x10000000 | 0x08000000 | 0x00800000


def _am_start_problem(args: list[str], hidden_display_id: int) -> str | None:
    """What is wrong with these `am start` options, or None when they launch on the hidden display only.

    Every --display must be the hidden display (am takes the last one) and every -f must carry NEW_TASK,
    MULTIPLE_TASK and EXCLUDE_FROM_RECENTS (am takes the last one), so the activity cannot join or move an
    existing task, possibly on display 0. Any other option (-S force-stops the app first, --task, --user, extras,
    ...) is refused."""
    displays: list[str] = []
    flags: list[str] = []
    i = 0
    while i < len(args):
        option = args[i]
        if i + 1 >= len(args):
            return f"`{option}` needs a value."
        value = args[i + 1]
        if option == "--display":
            displays.append(value)
        elif option == "-f":
            flags.append(value)
        elif option not in _AM_START_INTENT_OPTIONS:
            return f"`{option}` is not allowed."
        i += 2
    if not displays:
        return f"--display {hidden_display_id} is missing, so Android would start the activity on display 0."
    wrong = [d for d in displays if d != str(hidden_display_id)]
    if wrong:
        return (
            f"--display {wrong[0]} is not this session's hidden display ({hidden_display_id});"
            " every --display must name it."
        )
    if not flags:
        return "-f is missing."
    for value in flags:
        try:
            bits = int(value, 0)
        except ValueError:
            return f"-f {value} is not a number."
        if bits & _AM_START_REQUIRED_FLAGS != _AM_START_REQUIRED_FLAGS:
            return f"-f {value} lacks NEW_TASK | MULTIPLE_TASK | EXCLUDE_FROM_RECENTS (0x18800000)."
    return None


# --- the driver -------------------------------------------------------------------------------------------------


class HeadroidDriver(BaseDeviceDriver):
    """BaseDeviceDriver on one headroid hidden display of the phone `device_id`."""

    def __init__(self, device_id: str, *, connect: Callable[[str], Device] = Device.connect):
        self._device_id = device_id
        self._connect = connect
        self._device: Device | None = None
        self._display = None
        self._size: tuple[int, int] | None = None

    # --- connection ---

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def screen_size(self) -> tuple[int, int]:
        if self._size is None:
            raise RuntimeError("HeadroidDriver is not connected: call connect() first")
        return self._size

    async def connect(self) -> None:
        """Starts the headroid server and creates the hidden display. Holds no event-loop state, so it may run
        on a different loop from the calls that follow."""
        if self._display is not None:
            return
        device = await asyncio.to_thread(self._connect, self._device_id)
        display = None
        try:
            display = await asyncio.to_thread(
                device.create_display, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, dpi=DISPLAY_DPI
            )
            size = (int(display.info["width"]), int(display.info["height"]))
        except BaseException:
            await asyncio.to_thread(self._close, device, display)
            raise
        self._device, self._display, self._size = device, display, size
        logger.info(
            f"headroid hidden display {display.id} ({size[0]}x{size[1]}) on {self._device_id}"
        )

    async def disconnect(self) -> None:
        """Releases the hidden display and ends the headroid session. Safe to call when not connected."""
        device, display = self._device, self._display
        self._device = self._display = self._size = None
        if device is not None:
            await asyncio.to_thread(self._close, device, display)

    @staticmethod
    def _close(device: Device, display) -> None:
        if display is not None:
            try:
                display.release()
            except (OSError, RpcError) as e:
                logger.warning(f"releasing hidden display {display.id} failed: {e}")
        try:
            device.close()
        except (OSError, RpcError, AdbError) as e:
            logger.warning(f"closing the headroid session failed: {e}")

    def _require_display(self):
        if self._display is None:
            raise RuntimeError("HeadroidDriver is not connected: call connect() first")
        return self._display

    async def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(getattr(self._require_display(), method), *args, **kwargs)

    # --- observation ---

    async def get_screen_data(self, skip_settling: bool = False) -> ScreenData:
        """Screenshot and elements of the hidden display. headroid's errors (a HyperOS freeze, UiAutomation held
        by another tool) are raised with their message. An empty display gives a black placeholder image."""
        width, height = self.screen_size
        nodes = await self._call("tree")
        try:
            png = await self._call("screenshot")
        except RpcError as e:
            if e.code != NO_FRAME:
                raise
            png = _blank_png(width, height)
        return ScreenData(
            screenshot_bytes=png,
            screenshot_base64=base64.b64encode(png).decode("ascii"),
            ui_hierarchy_xml=None,
            ui_elements=tree_to_elements(nodes),
            width=width,
            height=height,
            platform="android",
        )

    async def get_current_package(self) -> str | None:
        """Package of the top window on the hidden display (never display 0's), or None when it is empty."""
        nodes = await self._call("tree")
        return (nodes[0].get("pkg") or None) if nodes else None

    # --- input ---

    async def tap(
        self, x: int, y: int, duration_ms: int = 100, times: int = 1, delay_ms: int = 100
    ) -> bool:
        if duration_ms >= 500:
            return await self.long_press(x, y, duration_ms=duration_ms)
        for i in range(max(1, times)):
            if i:
                await asyncio.sleep(max(0, delay_ms) / 1000.0)
            await self._call("tap", x, y)
        return True

    async def long_press(self, x: int, y: int, duration_ms: int = 1000) -> bool:
        await self._call("long_press", x, y, duration_ms=duration_ms)
        return True

    async def swipe(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 800
    ) -> bool:
        await self._call("swipe", start_x, start_y, end_x, end_y, duration_ms=duration_ms)
        return True

    async def swipe_direction(
        self, direction: SwipeDirection | str, duration_ms: int = 800
    ) -> bool:
        """Same gesture geometry as ARTEMIS's adb driver ("up" drags bottom to top, scrolling down)."""
        width, height = self.screen_size
        name = (direction.value if isinstance(direction, Enum) else str(direction)).lower()
        mid_x, mid_y = int(width * 0.6), height // 2
        gestures = {
            "up": (mid_x, int(height * 0.7), mid_x, int(height * 0.3)),
            "down": (mid_x, int(height * 0.3), mid_x, int(height * 0.7)),
            "left": (int(width * 0.75), mid_y, int(width * 0.25), mid_y),
            "right": (int(width * 0.25), mid_y, int(width * 0.75), mid_y),
        }
        if name not in gestures:
            raise ValueError(f"unknown swipe direction {direction!r}: use up, down, left or right")
        return await self.swipe(*gestures[name], duration_ms=duration_ms)

    async def input_text(self, text: str, clear_existing: bool = True) -> bool:
        """Types into the focused field; with clear_existing it empties the field first, so
        input_text("", clear_existing=True) clears it."""
        if clear_existing:
            await self._call("clear_text")
        if text:
            await self._call("type", text)
        return True

    async def press_key(self, key: KeyCode | str | int) -> bool:
        code = _key_code(key)
        if code in _REFUSED_KEYS:
            raise PermissionError(
                f"KEYCODE_{_REFUSED_KEYS[code]} acts on the whole phone or its main screen (display 0), not on "
                "the hidden display; headroid does not send it. Use back, or manage_app to switch apps."
            )
        await self._call("key", code)
        return True

    # --- apps ---

    async def launch_app(self, package_name: str) -> bool:
        """Starts the app on the hidden display (own task, excluded from Recents, muted)."""
        await self._call("launch", package_name)
        return True

    async def stop_app(self, package_name: str) -> bool:
        """Force-stops the app unless someone else uses it; raises with headroid's reason when it does not."""
        result = await self._call("stop", package_name)
        if not result.get("stopped", False):
            raise RuntimeError(f"not stopping {package_name}: {result.get('reason', 'refused')}")
        return True

    async def open_url(self, url: str) -> bool:
        """Opens the link on the hidden display (never display 0)."""
        display = self._require_display()
        options = [
            "--display",
            str(display.id),
            "-f",
            _OPEN_URL_FLAGS,
            "-a",
            "android.intent.action.VIEW",
        ]
        options += ["-d", url]
        why = _am_start_problem(
            options, display.id
        )  # the same launch rules as execute_shell's am start
        if why:
            raise PermissionError(f"open_url refused: {why}")
        # one shell line for adb; the URL is a single single-quoted argument the device shell does not interpret
        quoted = "'" + url.replace("'", "'\\''") + "'"
        cmd = " ".join(["am", "start", *options[:-1], quoted])
        out = await asyncio.to_thread(self._adb().run, "shell", cmd)
        if "Error" in out:
            logger.warning(f"open_url failed: {out.strip()}")
            return False
        return True

    # --- shell ---

    def _adb(self) -> Adb:
        """The adb of the headroid session (it follows the phone across wireless reconnects)."""
        server = getattr(self._device, "server", None)
        adb = getattr(server, "adb", None)
        return adb if adb is not None else Adb(self._device_id, os.environ.get("ADB", "adb"))

    async def execute_shell(self, command: str, timeout_seconds: float = 15.0) -> str:
        """Runs `command` with adb shell, unless it would read from or act on display 0 (PermissionError)."""
        hidden_id = self._require_display().id
        why = shell_refusal(command, hidden_id)
        if why:
            raise PermissionError(why)
        try:
            return await asyncio.to_thread(
                self._adb().run, "shell", command, timeout=timeout_seconds
            )
        except AdbError as e:
            return f"Error: {e}"

    # --- video ---

    async def start_video_recording(self, output_dir: Path | None = None) -> None:
        raise NotImplementedError(
            "video recording is not supported on a headroid hidden display (scrcpy would record display 0)"
        )

    async def stop_video_recording(self) -> str | None:
        return None  # nothing is ever recorded


def _key_code(key: KeyCode | str | int) -> int:
    if isinstance(key, Enum):
        key = key.value
    if isinstance(key, int):
        return key
    name = str(key).strip().lower()
    name = name.removeprefix("keycode_")
    if name.isdigit():
        return int(name)
    if name in _KEY_CODES:
        return _KEY_CODES[name]
    raise ValueError(
        f"unknown key {key!r}: use a KEYCODE_* number or one of {', '.join(sorted(_KEY_CODES))}"
    )
