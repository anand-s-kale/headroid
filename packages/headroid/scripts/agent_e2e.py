# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""End-to-end test of the agent path: an MCP client drives `headroid mcp` on a hidden display.

Starts `headroid mcp --serial S` over stdio, then does what an AI agent would: launch the sample app,
observe, log in by element index, observe the post-login screen, end the session. Checks the user's
foreground (display 0) never changed and that nothing is left behind on the device.

    python scripts/agent_e2e.py --serial emulator-5554 [--out agent-e2e-out]

Needs Python 3.12+ with `headroid[artemis]` installed. Refuses serials that are not emulators unless
--allow-device is given: never point it at someone's daily phone without their consent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time

from headroid.adb import Adb

PKG = "dev.headroid.sample"
EMAIL, PASSWORD = "demo@headroid.dev", "headroid"  # LoginActivity.kt's test credentials
TOOLS = {"mobile_observe", "mobile_act", "mobile_session_end"}
VIRTUAL_DISPLAY = "virtual:com.android.shell,2000,headroid"
SERVER_PROCESS = "dev.headroid.server"
TEARDOWN_WAIT_S = 70  # the device server exits after a grace period once the display is released

_ELEMENT = re.compile(r"^\[(\d+)\]\s+(?:OCR Text|Text|Hint):\s+'(.*?)'\s+\|\s+Bounds:", re.MULTILINE)


def parse_elements(elements_text: str | None) -> list[tuple[int, str]]:
    """(index, label) for each numbered line of mobile_observe's elements_text."""
    return [(int(i), label) for i, label in _ELEMENT.findall(elements_text or "")]


def find_index(elements_text: str | None, label: str) -> int | None:
    """Index of the first element whose label equals `label` (case-insensitive), else None."""
    want = label.strip().lower()
    for idx, text in parse_elements(elements_text):
        if text.strip().lower() == want:
            return idx
    return None


def top_focused_display(adb: Adb) -> int | None:
    out = adb.shell("dumpsys window | grep mTopFocusedDisplayId")
    m = re.search(r"mTopFocusedDisplayId=(-?\d+)", out)
    return int(m.group(1)) if m else None


def leftovers(adb: Adb) -> tuple[bool, bool]:
    """(headroid virtual display present, device server process present)."""
    display = adb.shell(f"dumpsys display | grep -c '{VIRTUAL_DISPLAY}' || true").strip()
    # The [d] keeps this shell's own command line from matching itself.
    proc = adb.shell(f"ps -A -o ARGS | grep -c '[d]{SERVER_PROCESS[1:]}' || true").strip()
    return display not in ("", "0"), proc not in ("", "0")


def payload(result) -> dict:
    """The JSON text block of a tool result (screenshots come as separate image blocks)."""
    for block in result.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    return {}


async def run(args: argparse.Namespace, adb: Adb, results: dict, checks: dict) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "headroid.cli", "mcp", "--serial", args.serial],
        env=dict(os.environ),
    )
    focus: dict[str, int | None] = {}
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        names = {t.name for t in (await session.list_tools()).tools}
        results["tools"] = sorted(names)
        checks["tools_are_the_three"] = names == TOOLS

        async def observe() -> dict:
            return payload(await session.call_tool("mobile_observe", {}))

        async def act(action: str, **a) -> dict:
            return payload(await session.call_tool("mobile_act", {"action": action, "args": a}))

        async def tap(label: str, view: dict) -> dict:
            idx = find_index(view.get("elements_text"), label)
            if idx is None:
                raise RuntimeError(f"no '{label}' element in:\n{view.get('elements_text')}")
            return await act("click", target=idx)

        focus["before"] = top_focused_display(adb)

        launch = await act("manage_app", action="launch", app_name=PKG)
        results["launch"] = launch.get("message")
        checks["launched"] = launch.get("status") == "success"
        focus["after_launch"] = top_focused_display(adb)

        home = await observe()
        checks["home_observed"] = (
            home.get("status") == "success" and find_index(home.get("elements_text"), "Login") is not None
        )
        await tap("Login", home)

        view = await observe()
        for label, value in (("Email", EMAIL), ("Password", PASSWORD)):
            idx = find_index(view.get("elements_text"), label)
            if idx is None:
                raise RuntimeError(f"no '{label}' field in:\n{view.get('elements_text')}")
            await act("input_text", text=value, target=idx)
            view = await observe()
        await tap("Sign in", view)
        focus["after_login"] = top_focused_display(adb)

        after = await observe()
        results["post_login_elements"] = after.get("elements_text")
        # FormActivity is where a successful login lands; the login screen has no Submit button.
        checks["post_login_observed"] = find_index(after.get("elements_text"), "Submit") is not None

        end = payload(await session.call_tool("mobile_session_end", {}))
        checks["session_ended"] = end.get("status") == "success"
        focus["after_end"] = top_focused_display(adb)

        deadline = time.monotonic() + TEARDOWN_WAIT_S
        display_left, proc_left = leftovers(adb)
        while (display_left or proc_left) and time.monotonic() < deadline:
            await asyncio.sleep(3)
            display_left, proc_left = leftovers(adb)
        checks["no_headroid_display_left"] = not display_left
        checks["no_server_process_left"] = not proc_left

    results["top_focused_display"] = focus
    checks["focus_stayed_on_display_0"] = len(focus) == 4 and all(v == 0 for v in focus.values())


REQUIRED_CHECKS = {
    "tools_are_the_three", "launched", "home_observed", "post_login_observed", "session_ended",
    "no_headroid_display_left", "no_server_process_left", "focus_stayed_on_display_0",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Drive `headroid mcp` like an AI agent and check it stays hidden.")
    ap.add_argument("--serial", required=True)
    ap.add_argument("--out", default="agent-e2e-out")
    ap.add_argument("--allow-device", action="store_true")
    args = ap.parse_args(argv)

    if not args.serial.startswith("emulator-") and not args.allow_device:
        print("refusing: not an emulator serial (use --allow-device only with the owner's consent)", file=sys.stderr)
        return 2

    os.makedirs(args.out, exist_ok=True)
    adb = Adb(args.serial)
    results: dict[str, object] = {"serial": args.serial}
    checks: dict[str, bool] = {}
    results["checks"] = checks
    try:
        asyncio.run(run(args, adb, results, checks))
    except Exception as e:  # noqa: BLE001 - report it with whatever was checked so far
        results["error"] = f"{type(e).__name__}: {e}"

    print(json.dumps(results, indent=2, ensure_ascii=False))
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    ok = "error" not in results and REQUIRED_CHECKS <= checks.keys() and all(checks.values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
