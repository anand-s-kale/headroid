# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Command line: headroid devices|doctor|launch|info|screenshot|tree."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .adb import AdbError, list_devices
from .device import Device
from .doctor import ok, run_doctor


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="headroid")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices", help="list adb devices")
    s = sub.add_parser("doctor", help="check that this machine and phone are ready")
    s.add_argument("--serial", default=None)
    s.add_argument("--jar", default=None)
    s = sub.add_parser("launch", help="launch an app on a hidden display and screenshot it")
    s.add_argument("package")
    s.add_argument("--activity", default=None)
    s.add_argument("--screenshot", default=None, metavar="OUT.png")
    s.add_argument("--wait", type=float, default=3.0, metavar="SECONDS")
    s.add_argument("--serial", default=None)
    s.add_argument("--jar", default=None)
    for name in ("info", "screenshot", "tree"):
        s = sub.add_parser(name)
        s.add_argument("--serial", default=None)
        s.add_argument("--jar", default=None)
        if name == "screenshot":
            s.add_argument("-o", "--output", default="screenshot.png")
    return p


def _devices() -> int:
    try:
        devices = list_devices(os.environ.get("ADB", "adb"))
    except AdbError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not devices:
        print("no devices attached")
    for d in devices:
        print(f"{d['serial']}\t{d['state']}\t{d['model']}")
    return 0


def _doctor(args) -> int:
    checks = run_doctor(args.serial, args.jar, report=lambda c: print(c.line()))
    return 0 if ok(checks) else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "devices":
        return _devices()
    if args.cmd == "doctor":
        return _doctor(args)
    dev = Device.connect(serial=args.serial, jar=args.jar)
    try:
        if args.cmd == "info":
            print(json.dumps(dev.info(), indent=2))
        else:
            display = dev.create_display()
            if args.cmd == "launch":
                display.launch(args.package, args.activity)
                time.sleep(args.wait)
                out = args.screenshot or "launch.png"
                data = display.screenshot(out)
                print(f"wrote {out} ({len(data)} bytes)")
            elif args.cmd == "screenshot":
                data = display.screenshot(args.output)
                print(f"wrote {args.output} ({len(data)} bytes)")
            else:
                print(json.dumps(display.tree(), indent=2))
    finally:
        dev.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
