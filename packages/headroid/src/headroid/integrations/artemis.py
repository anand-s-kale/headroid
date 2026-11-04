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
import posixpath
import re
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

_DISPLAY_0_TAIL = (
    " headroid's ARTEMIS driver never reads from or acts on display 0 (the phone's own screen); use mobile_observe"
    " and mobile_act, which work on the hidden display."
)
_UNCHECKABLE = (
    "cannot be checked (nested shell, substitution or variable), so it might reach display 0."
)

# Programs that read or drive display 0 whatever their arguments.
_REFUSED_PROGRAMS = {
    "screencap": "captures display 0.",
    "screenrecord": "records display 0.",
    "uiautomator": "dumps or drives display 0's UI.",
    "input": "injects input into display 0.",
    "monkey": "starts apps and sends events on display 0.",
    "sendevent": "injects raw touches into display 0.",
    "getevent": "reads the owner's touches on display 0.",
    "wm": "reads or changes display 0's size and density.",
}
# Programs that run other commands headroid cannot see into.
_UNCHECKABLE_PROGRAMS = {
    "sh",
    "bash",
    "mksh",
    "ash",
    "zsh",
    "dash",
    "eval",
    "source",
    ".",
    "su",
    "xargs",
    "run-as",
    "app_process",
    "dalvikvm",
    "service",
    "nsenter",
    "chroot",
    "strace",
    "setsid",
    "logwrapper",
    "stdbuf",
    "ionice",
    "chrt",
    "taskset",
    "watch",
    "flock",
}
# Refused wherever they appear in a command, not only as its program (they are not ordinary words).
_REFUSED_ANYWHERE = {"screencap", "screenrecord", "uiautomator", "monkey", "sendevent", "getevent"}
_WRAPPERS = {
    "exec",
    "command",
    "builtin",
    "nohup",
    "time",
    "toybox",
    "busybox",
    "{",
    "}",
    "!",
    "if",
    "then",
    "else",
    "elif",
    "do",
    "while",
    "until",
    "done",
    "fi",
}
_AM_REFUSED = {
    "instrument": "runs instrumentation on display 0.",
    "switch-user": "switches the whole phone to another user.",
    "stack": "moves tasks between displays.",
    "task": "moves tasks between displays.",
    "display": "changes displays.",
}
_AM_STOPS = {"force-stop", "kill", "kill-all", "stop-app"}
_DUMPSYS_REFUSED = {
    "window",
    "activity",
    "surfaceflinger",
    "accessibility",
    "display",
    "input",
    "statusbar",
}
_CMD_REFUSED = {"input", "window", "statusbar", "display", "accessibility"}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def shell_refusal(command: str, hidden_display_id: int) -> str | None:
    """Why `command` must not run on the phone, or None. A best-effort backstop: ARTEMIS's manual-mode actions
    do not shell out on the headroid driver; this catches any path that still would."""
    if "$(" in command or "`" in command or "<(" in command or ">(" in command:
        return f"`{command}` {_UNCHECKABLE}"
    lexer = shlex.shlex(
        command.replace("\r", "\n").replace("\n", " ; "), posix=True, punctuation_chars=True
    )
    lexer.whitespace_split = True
    lexer.commenters = ""  # check what a comment would hide too
    try:
        tokens = list(lexer)
    except ValueError as e:
        return f"`{command}` cannot be parsed ({e}), so it might reach display 0."
    for words in _segments(tokens):
        why = _segment_refusal(words, hidden_display_id)
        if why:
            return why
    return None


def _segments(tokens: list[str]) -> list[list[str]]:
    """Splits shell tokens into simple commands, dropping redirections."""
    segments: list[list[str]] = [[]]
    skip_next = False
    for i, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token and set(token) <= set("();<>|&"):
            # the lexer joins adjacent operators (";>", "&>", ">&"), so a token can both end a command and
            # start a redirection
            redirect = bool(set(token) & set("<>"))
            if set(token) & set(";|()") or ("&" in token and not redirect):
                segments.append([])
            skip_next = redirect  # drop the redirection's target
            continue
        if token.isdigit() and i + 1 < len(tokens) and tokens[i + 1].startswith(("<", ">")):
            continue  # the fd of "2>file"
        segments[-1].append(token)
    return [s for s in segments if s]


def _unwrap(words: list[str]) -> list[str]:
    """Drops variable assignments and wrappers (exec, nohup, toybox, env, nice, timeout, ...)."""
    while words:
        first = posixpath.basename(words[0])
        if _ASSIGNMENT.match(words[0]) or first in _WRAPPERS:
            words = words[1:]
        elif first == "env":
            words = words[1:]
            while words and (words[0].startswith("-") or _ASSIGNMENT.match(words[0])):
                words = words[2:] if words[0] in ("-u", "-C") else words[1:]
        elif first == "nice":
            words = words[1:]
            if words[:1] == ["-n"]:
                words = words[2:]
            elif words and re.fullmatch(r"-\d+", words[0]):
                words = words[1:]
        elif first == "timeout":
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[2:] if words[0] in ("-s", "-k") else words[1:]
            words = words[1:]  # the duration
        else:
            break
    return words


def _segment_refusal(words: list[str], hidden_display_id: int) -> str | None:
    words = _unwrap(words)
    if not words:
        return None
    program = posixpath.basename(words[0])
    args = words[1:]
    shown = " ".join(words)
    if "$" in program or set(program) & set("*?[{"):
        return f"`{shown}` {_UNCHECKABLE}"
    for word in words:
        name = posixpath.basename(word)
        if name in _REFUSED_ANYWHERE:
            return f"refused `{shown}`: `{name}` {_REFUSED_PROGRAMS[name]}{_DISPLAY_0_TAIL}"
    if program in _UNCHECKABLE_PROGRAMS:
        return f"`{shown}` runs another command that {_UNCHECKABLE}"
    if program == "find" and set(args) & {"-exec", "-execdir", "-ok", "-okdir"}:
        return f"`{shown}` runs another command that {_UNCHECKABLE}"
    if program in _REFUSED_PROGRAMS:
        return f"refused `{shown}`: `{program}` {_REFUSED_PROGRAMS[program]}{_DISPLAY_0_TAIL}"
    if program == "am":
        return _am_refusal(args, shown, hidden_display_id)
    if program == "cmd" and args:
        service = args[0].lower()
        if service == "activity":
            return _am_refusal(args[1:], shown, hidden_display_id)
        if service in _CMD_REFUSED:
            return (
                f"refused `{shown}`: `cmd {service}` reads or acts on display 0.{_DISPLAY_0_TAIL}"
            )
    if program == "dumpsys":
        services = [a for a in args if not a.startswith("-") and not a.isdigit()]
        if not services or services[0].lower() in _DUMPSYS_REFUSED:
            return f"refused `{shown}`: it reports what display 0 shows.{_DISPLAY_0_TAIL}"
    return None


def _am_refusal(args: list[str], shown: str, hidden_display_id: int) -> str | None:
    sub = args[0] if args else ""
    if sub in ("start", "start-activity"):
        if "--display" in args:
            i = args.index("--display")
            if i + 1 < len(args) and args[i + 1] == str(hidden_display_id):
                return None
        return (
            f"refused `{shown}`: `am {sub}` must name this session's hidden display (--display "
            f"{hidden_display_id}); without it Android starts the activity on display 0.{_DISPLAY_0_TAIL}"
        )
    if sub in _AM_REFUSED:
        return f"refused `{shown}`: `am {sub}` {_AM_REFUSED[sub]}{_DISPLAY_0_TAIL}"
    if sub in _AM_STOPS:
        return (
            f"refused `{shown}`: it could stop an app the owner is using on display 0; use manage_app stop, which"
            " stops an app only when nobody else has it open."
        )
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
        quoted = "'" + url.replace("'", "'\\''") + "'"
        cmd = f"am start --display {display.id} -f {_OPEN_URL_FLAGS} -a android.intent.action.VIEW -d {quoted}"
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
