# Architecture

```
┌──────────────────────── Host (your computer) ────────────────────────┐
│  Test files / AI agent                                               │
│     │                                                                │
│  @headroid/test (runner, expect, traces)   @headroid/mcp (agent tools)│
│     └──────────────┬───────────────────────────┘                     │
│              headroid (TypeScript SDK: Device, Page, Locator)        │
│                     │  JSON-RPC over an adb-forwarded socket         │
└─────────────────────┼────────────────────────────────────────────────┘
                      │  wireless ADB (adb pair / adb connect)
┌─────────────────────┼──────────── Phone (no root) ───────────────────┐
│  headroid-server.jar  (app_process, uid 2000 "shell")                │
│   ├─ DisplayService   create / resize / destroy hidden displays      │
│   ├─ AppService       am start --display N, force-stop, permissions  │
│   ├─ InputService     touch / key / text injected with displayId=N   │
│   ├─ CaptureService   ImageReader frames → PNG / H.264               │
│   ├─ TreeService      UiAutomation windows on display N → JSON tree  │
│   └─ Guard            focus, IME policy, mute, teardown on disconnect│
│                                                                      │
│  Display 0 (physical): the owner's apps, untouched                   │
│  Display N (virtual, hidden): the app under test                     │
└──────────────────────────────────────────────────────────────────────┘
```

## Device server

- Pushed to `/data/local/tmp` and started with `app_process`, the same way scrcpy-server is. It runs as the shell user,
  so no root and no app install are needed.
- **Display:** a virtual display through the hidden `DisplayManager` API with `PUBLIC | OWN_CONTENT_ONLY | SUPPORTS_TOUCH`.
  On Android 13+ it adds `TRUSTED | OWN_DISPLAY_GROUP | ALWAYS_UNLOCKED`, and on 14+ `OWN_FOCUS | STEAL_TOP_FOCUS_DISABLED`.
  Its surface is our own `ImageReader`, so nothing is shown on the physical screen.
- **Input:** `InputManager.injectInputEvent` with the event's display id set to the virtual display. Text goes in as key
  events or the accessibility set-text action, with the display IME policy set to `HIDE`.
- **Observation:** frames come from the `ImageReader`, never from `screencap -d`, which is unreliable on virtual displays.
  The UI tree comes from `UiAutomation` windows filtered by display id (Android 11+).
- **Guard:** mutes the app under test (`appops` PLAY_AUDIO / VIBRATE), and tears the display down when the host
  disconnects so no stray tasks are left behind.

## Host

- **SDK** (`headroid`): `Device` → `Page` (one hidden display + app) → `Locator` (text, resource-id, content-desc, hint,
  role) with auto-wait.
- **Test runner** (`@headroid/test`): fixtures, retries, HTML report, trace viewer (frames + tree + actions).
- **MCP server** (`@headroid/mcp`): `launch`, `observe` (screenshot + tree), `act`, `assert`, `report_bug`, `close`.
- **CLI** (`headroid`): `pair`, `doctor` (capability probe), `run`, `record`.

Decisions are recorded in [adr/](adr/). Known limits and their evidence are in [research/SUMMARY.md](research/SUMMARY.md).
