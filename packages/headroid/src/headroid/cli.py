# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Command line: headroid devices|doctor|launch|mcp|info|screenshot|tree."""

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
    s = sub.add_parser("mcp", help="start the ARTEMIS MCP server (manual mode) on a hidden display")
    s.add_argument("--serial", default=None)
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


def mcp_env(serial: str | None) -> dict[str, str]:
    """Environment that puts the ARTEMIS fork into headroid manual mode."""
    if serial is None:
        try:
            devices = [d for d in list_devices(os.environ.get("ADB", "adb")) if d["state"] == "device"]
        except AdbError as e:
            raise SystemExit(f"error: {e}") from e
        if len(devices) != 1:
            listing = "\n".join(f"  {d['serial']}	{d['model']}" for d in devices) or "  (none)"
            raise SystemExit(
                f"error: expected exactly one attached device, found {len(devices)}; "
                f"pass --serial.\n{listing}"
            )
        serial = devices[0]["serial"]
    return {
        "ARTEMIS_DRIVER": "headroid",
        "ARTEMIS_MCP_TOOLS": "mobile_observe,mobile_act,mobile_session_end",
        "ARTEMIS_MCP_INLINE_SCREENSHOT": "1",
        # ARTEMIS's awake service would set "stay on while plugged in" and wake the phone's own screen.
        "ARTEMIS_KEEP_DEVICE_AWAKE": "0",
        # ARTEMIS prefers ARTEMIS_DEVICE_ID over ADB_DEVICE_SERIAL: set both, so neither can name another phone.
        "ARTEMIS_DEVICE_ID": serial,
        "ADB_DEVICE_SERIAL": serial,
    }


def _mcp(args) -> int:
    # stdout belongs to the MCP protocol on stdio: print only to stderr here.
    env = mcp_env(args.serial)
    os.environ.update(env)  # must precede the import: the fork reads some of it at import time
    try:
        from mcp_server.server import main as serve
    except ImportError as e:
        hint = 'pip install "headroid[artemis]"'
        if sys.version_info < (3, 12):
            hint += f" (needs Python 3.12 or newer; this is Python {sys.version_info[0]}.{sys.version_info[1]})"
        print(f"error: the ARTEMIS MCP server is not installed ({e}).\nInstall it with: {hint}",
              file=sys.stderr)
        return 2
    # Importing ARTEMIS loads .env files, and a project's .env may override the environment. Put the values
    # back; ARTEMIS_MCP_INLINE_SCREENSHOT is read during the import itself, so a change to it cannot be undone.
    changed = sorted(k for k, v in env.items() if os.environ.get(k) != v)
    if "ARTEMIS_MCP_INLINE_SCREENSHOT" in changed:
        print("error: a .env file loaded by ARTEMIS changed ARTEMIS_MCP_INLINE_SCREENSHOT, which headroid mcp"
              " needs set to 1; remove it from the .env in the current directory or in ARTEMIS's config"
              " directory.", file=sys.stderr)
        return 1
    os.environ.update(env)
    if changed:
        print(f"headroid mcp: a .env file changed {', '.join(changed)}; restored headroid's values",
              file=sys.stderr)
    try:
        serve()
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "devices":
        return _devices()
    if args.cmd == "doctor":
        return _doctor(args)
    if args.cmd == "mcp":
        return _mcp(args)
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
