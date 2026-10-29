# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""End-to-end smoke test of the device server on an emulator.

Drives the headroid sample app on a hidden display: launch, tree, screenshot, tap, type (ASCII and Unicode),
login flow, then checks focus stayed on display 0 and that teardown left nothing behind.

    python scripts/emulator_smoke.py --serial emulator-5554 --jar ../../device-server/server/build/headroid/headroid-server.jar \
        --apk ../../sample-app/app/build/outputs/apk/debug/app-debug.apk --out smoke-out

Refuses serials that are not emulators unless --allow-device is given: never point it at someone's daily phone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

from headroid import Device
from headroid.adb import Adb

PKG = "dev.headroid.sample"


def wait_for(display, timeout=20.0, **criteria):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        node = display.find(**criteria)
        if node is not None and node.get("visible", True):
            return node
        time.sleep(0.3)
    raise AssertionError(f"not found within {timeout}s: {criteria}")


def center(node):
    left, top, right, bottom = node["bounds"]
    return (left + right) // 2, (top + bottom) // 2


def tap_node(display, **criteria):
    node = wait_for(display, **criteria)
    display.tap(*center(node))
    return node


def top_focused_display(adb: Adb) -> int | None:
    out = adb.shell("dumpsys window | grep mTopFocusedDisplayId")
    m = re.search(r"mTopFocusedDisplayId=(-?\d+)", out)
    return int(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True)
    ap.add_argument("--jar", required=True)
    ap.add_argument("--apk")
    ap.add_argument("--out", default="smoke-out")
    ap.add_argument("--allow-device", action="store_true")
    args = ap.parse_args()

    if not args.serial.startswith("emulator-") and not args.allow_device:
        print("refusing: not an emulator serial (use --allow-device only with the owner's consent)", file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)
    adb = Adb(args.serial)
    results: dict[str, object] = {"serial": args.serial}
    checks: dict[str, bool] = {}

    if args.apk:
        subprocess.run(["adb", "-s", args.serial, "install", "-r", args.apk], check=True, capture_output=True)

    device = Device.connect(serial=args.serial, jar=args.jar)
    try:
        info = device.info()
        results["info"] = info
        display = device.create_display(720, 1600, 320)
        results["display"] = display.info

        display.launch(PKG)
        wait_for(display, rid="nav_login")
        checks["launch_and_tree"] = True
        png = display.screenshot(os.path.join(args.out, "01-home.png"))
        checks["screenshot_png"] = png[:8] == b"\x89PNG\r\n\x1a\n"

        focus_before = top_focused_display(adb)
        tap_node(display, rid="nav_login")
        tap_node(display, rid="login_email")
        display.type("demo@headroid.dev")
        tap_node(display, rid="login_password")
        display.type("headroid")
        display.screenshot(os.path.join(args.out, "02-login.png"))
        tap_node(display, rid="login_submit")
        wait_for(display, rid="form_name")
        checks["login_flow"] = True

        tap_node(display, rid="form_name")
        method = display._c.call("input.text", displayId=display.id, text="héllo \U0001f600")["method"]
        results["unicode_text_method"] = method
        field = wait_for(display, rid="form_name")
        checks["unicode_text"] = field.get("text") == "héllo \U0001f600"
        display.screenshot(os.path.join(args.out, "03-form.png"))

        display.swipe(360, 1200, 360, 400, 300)
        display.key(4)  # KEYCODE_BACK on the hidden display only
        focus_after = top_focused_display(adb)
        results["top_focused_display"] = {"before": focus_before, "after": focus_after}
        checks["focus_stayed_on_display_0"] = focus_before == 0 and focus_after == 0

        try:
            display._c.call("input.tap", displayId=0, x=1, y=1)
            checks["display_0_rejected"] = False
        except Exception as e:  # noqa: BLE001 - any refusal is fine, it must not succeed
            checks["display_0_rejected"] = "-32602" in str(e)
        display_id = display.id
    finally:
        device.close()

    time.sleep(1.0)
    displays = adb.shell("dumpsys display | grep -c 'headroid' || true").strip()
    activities = adb.shell(f"dumpsys activity activities | grep -c '{PKG}' || true").strip()
    results["after_teardown"] = {"dumpsys_display_headroid_lines": displays, "sample_activity_lines": activities}
    checks["teardown_display_gone"] = displays in ("", "0")
    checks["teardown_app_gone"] = activities in ("", "0")
    results["released_display_id"] = display_id
    results["checks"] = checks

    print(json.dumps(results, indent=2, ensure_ascii=False))
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
