# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""`headroid doctor`: ordered environment checks, each with a one-line fix."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from .adb import Adb, AdbError, list_devices
from .device import Device
from .jar import BUILD_HINT, resolve_jar
from .rpc import RpcError

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
MIN_API = 30
VERIFIED_API = range(34, 37)  # Android 14-16
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
NO_FRAME = -32011


@dataclass
class Check:
    status: str
    name: str
    detail: str = ""
    fix: str = ""

    def line(self) -> str:
        s = f"[{self.status}] {self.name}"
        if self.detail:
            s += f": {self.detail}"
        if self.fix:
            s += f"  -> {self.fix}"
        return s


def run_doctor(
    serial: str | None = None,
    jar: str | None = None,
    adb_path: str | None = None,
    connect: Callable[..., Device] = Device.connect,
    report: Callable[[Check], None] = lambda c: None,
) -> list[Check]:
    """Runs the checks in order, stopping at a FAIL that makes later checks meaningless."""
    adb_path = adb_path or os.environ.get("ADB", "adb")
    checks: list[Check] = []

    def add(status: str, name: str, detail: str = "", fix: str = "") -> Check:
        c = Check(status, name, detail, fix)
        checks.append(c)
        report(c)
        return c

    # 1. adb on PATH
    try:
        proc = subprocess.run(
            [adb_path, "version"], capture_output=True, text=True, timeout=30, check=False
        )
        first = (proc.stdout or "").splitlines()[0] if proc.stdout else "version unknown"
        add(PASS, "adb on PATH", first)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        add(
            FAIL,
            "adb on PATH",
            "not found",
            "install Android platform-tools and add it to PATH (or set ADB=/path/to/adb)",
        )
        return checks

    # 2. device selection
    try:
        devices = list_devices(adb_path)
    except AdbError as e:
        add(FAIL, "adb devices", str(e), "run `adb start-server` and retry")
        return checks
    listing = ", ".join(f"{d['serial']} ({d['state']})" for d in devices)
    if serial is None:
        if not devices:
            add(
                FAIL,
                "device attached",
                "none",
                "connect the phone with USB debugging on, then run `adb devices`",
            )
            return checks
        if len(devices) > 1:
            add(
                FAIL,
                "device attached",
                f"{len(devices)} devices: {listing}",
                "pass --serial <serial>",
            )
            return checks
        serial = devices[0]["serial"]
    match = next((d for d in devices if d["serial"] == serial), None)
    if match is None:
        add(
            FAIL,
            "device attached",
            f"{serial} not listed (attached: {listing or 'none'})",
            "check the serial with `headroid devices`",
        )
        return checks
    add(PASS, "device attached", f"{serial} {match['model']}".strip())

    # 3. device state
    state = match["state"]
    if state == "unauthorized":
        add(FAIL, "device state", state, "accept the USB debugging prompt on the phone")
        return checks
    if state == "offline":
        add(FAIL, "device state", state, "unplug and reconnect the cable, or run `adb reconnect`")
        return checks
    if state != "device":
        add(FAIL, "device state", state, "make sure the phone shows as `device` in `adb devices`")
        return checks
    add(PASS, "device state", state)

    # 4. Android version and manufacturer
    adb = Adb(serial, adb_path)
    try:
        api = int(adb.shell("getprop ro.build.version.sdk").strip())
        maker = adb.shell("getprop ro.product.manufacturer").strip()
    except (AdbError, ValueError) as e:
        add(FAIL, "Android API level", str(e), "check `adb -s <serial> shell getprop`")
        return checks
    if api < MIN_API:
        add(FAIL, "Android API level", f"{api}", "the server needs Android 11 (API 30) or newer")
        return checks
    if api not in VERIFIED_API:
        add(WARN, "Android API level", f"{api}", "only Android 14-16 (API 34-36) are verified")
    else:
        add(PASS, "Android API level", f"{api}")
    if maker.lower() in ("xiaomi", "redmi", "poco"):
        add(
            WARN,
            "manufacturer",
            maker,
            "Developer options: enable 'USB debugging (Security settings)' for input "
            "and 'Install via USB' for installs",
        )

    # 5. jar
    try:
        jar_path = resolve_jar(jar)
    except FileNotFoundError:
        add(FAIL, "server jar", "not found", BUILD_HINT)
        return checks
    if not os.path.isfile(jar_path):
        add(FAIL, "server jar", f"{jar_path} does not exist", BUILD_HINT)
        return checks
    add(PASS, "server jar", jar_path)

    # 6. server starts and answers, 7. hidden display screenshot
    try:
        dev = connect(serial=serial, jar=jar_path)
    except Exception as e:  # noqa: BLE001 - report any startup failure as a check result
        add(FAIL, "server starts", str(e), "keep the phone unlocked and retry")
        return checks
    try:
        try:
            info = dev.info()
            add(
                PASS,
                "server.info",
                f"sdk={info.get('sdk')} model={info.get('model')} "
                f"capabilities={info.get('capabilities')}",
            )
        except Exception as e:  # noqa: BLE001
            add(FAIL, "server.info", str(e), "the server started but does not answer")
            return checks
        try:
            display = dev.create_display()
        except Exception as e:  # noqa: BLE001
            add(FAIL, "hidden display", str(e), "report this with `adb logcat -s scrcpy`")
            return checks
        add(PASS, "hidden display", f"id {display.id}")
        try:
            png = display.screenshot()
            if png[:8] == PNG_MAGIC:
                add(PASS, "hidden display screenshot", f"{len(png)} bytes PNG")
            else:
                add(FAIL, "hidden display screenshot", "not a PNG", "report this with adb logcat")
        except RpcError as e:
            if e.code == NO_FRAME:
                # an empty display draws nothing, so there is no frame until an app is launched on it
                add(PASS, "hidden display screenshot", "empty display, no frame until an app draws")
            else:
                add(FAIL, "hidden display screenshot", str(e), "report this with adb logcat")
        except Exception as e:  # noqa: BLE001
            add(FAIL, "hidden display screenshot", str(e), "report this with adb logcat")
    finally:
        dev.close()  # releases the display
    return checks


def ok(checks: list[Check]) -> bool:
    return not any(c.status == FAIL for c in checks)
