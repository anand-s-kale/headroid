# ADR 0003: Build headroid by composing the open-source Android stack

Date: 2026-10-29 · Status: accepted · Supersedes the host-language part of [ADR 0002](0002-device-server-from-scrcpy.md)

## Context
Most of what headroid needs already exists under licences compatible with Apache-2.0:

| Project | Licence | Language | What it already does |
|---|---|---|---|
| [scrcpy](https://github.com/Genymobile/scrcpy) (server) | Apache-2.0 | Java | Hidden virtual display, app launch, input injection, as shell uid |
| [google/artemis](https://github.com/google/artemis) | Apache-2.0 | Python | Agent "brain": Flash/Pro modes, planner, checker, safety net, reports, MCP server, device locks, diagnosis |
| [minitap-ai/mobile-use](https://github.com/minitap-ai/mobile-use) | Apache-2.0 | Python | AI agent for Android and iOS. ARTEMIS is partly derived from it, with credit |
| [openatx/uiautomator2](https://github.com/openatx/uiautomator2) | MIT | Python | UI hierarchy, selectors, device actions |
| [openatx/adbutils](https://github.com/openatx/adbutils) | MIT | Python | Pure-Python ADB client |
| [appium-uiautomator2-driver](https://github.com/appium/appium-uiautomator2-driver) | Apache-2.0 | Java/JS | `currentDisplayId` multi-display hierarchy |
| [Shizuku](https://github.com/RikkaApps/Shizuku) | Apache-2.0 | Java | Shell-privileged services from an on-phone app |
| [Playwright](https://github.com/microsoft/playwright) | Apache-2.0 | TS/Python | API design: locators, auto-wait, expect, traces |

Rewriting any of these would waste months. Both agents (ARTEMIS and mobile-use) and the main helper libraries are
Python, and ARTEMIS already exposes a clean device seam (`BaseDeviceDriver`: connect, screen data, tap, swipe,
input_text, press_key, launch_app, recording).

## Decision
headroid is the **headless layer** that the whole stack is missing: it puts any of these tools onto a hidden display.
We mix the projects in three ways:

1. **Adapt (code copied into this repo, with attribution).** These are small, core pieces we need to change:
   - scrcpy-server → `device-server/` (virtual display, injection, IME policy), plus our focus guard, capture and tree.
   - Selected ARTEMIS / mobile-use modules where they fit the host SDK: hierarchy parsing, display-aware input
     helpers, device lock/queue, diagnosis checks, recorder.
2. **Depend (installed as packages, not copied).** Libraries we use as-is: `adbutils`, `uiautomator2`, `mcp`, and
   optionally Appium. Android platform-tools (`adb`) are **not** redistributed: users install them, because they are
   under the Android SDK terms rather than an open-source licence.
3. **Integrate (plug-ins that make other tools headless).** The agents are large and fast-moving, so we connect to
   them instead of forking them, and their upstream improvements keep flowing to us:
   - `integrations/artemis/`: a `HeadroidDriver(BaseDeviceDriver)` that runs every ARTEMIS task on display N.
     Offered upstream to google/artemis.
   - `integrations/mobile-use/`: the same for mobile-use's controller layer. Offered upstream to minitap-ai.

**Host language: Python-first** (SDK, test runner, CLI, MCP), because everything we mix in is Python.
A TypeScript client follows later; the device-server protocol (JSON-RPC) is language-neutral.

## Attribution rules
- Every adapted file keeps the original copyright and licence header and adds a line saying it was modified for
  headroid. This is the same format ARTEMIS uses for code derived from mobile-use:
  `# Portions of this file are derived from <project> (<url>)` / `# Copyright <years> <owner>. Licensed under the Apache License 2.0.`
- Each source project gets an entry in [NOTICE](../../NOTICE) and in [PRIOR-ART.md](../PRIOR-ART.md).
- Projects with no licence or a non-commercial licence are never mixed in; see [CLEAN-ROOM.md](../CLEAN-ROOM.md).
- Do not adopt behaviour that disturbs the phone owner, even from a permissive project. For example, never switch the
  system default keyboard (IME). Typing uses accessibility set-text on display N instead.

## Consequences
- headroid stays small: device server + Python SDK + integrations. The agent "brain" comes from ARTEMIS / mobile-use.
- We must track upstream changes in scrcpy-server and in ARTEMIS's driver interface.
- The licence check is per file and per dependency; the PR template enforces it.
