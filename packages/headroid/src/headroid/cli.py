# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Smoke-test command line: headroid info|screenshot|tree."""

from __future__ import annotations

import argparse
import json
import sys

from .device import Device


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="headroid")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("info", "screenshot", "tree"):
        s = sub.add_parser(name)
        s.add_argument("--serial", default=None)
        s.add_argument("--jar", default=None)
        if name == "screenshot":
            s.add_argument("-o", "--output", default="screenshot.png")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    dev = Device.connect(serial=args.serial, jar=args.jar)
    try:
        if args.cmd == "info":
            print(json.dumps(dev.info(), indent=2))
        else:
            display = dev.create_display()
            if args.cmd == "screenshot":
                data = display.screenshot(args.output)
                print(f"wrote {args.output} ({len(data)} bytes)")
            else:
                print(json.dumps(display.tree(), indent=2))
    finally:
        dev.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
