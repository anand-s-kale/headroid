# headroid: product design

Status: draft for owner approval, 2026-10-30. Author: Claude (lead), from conversations with the owner.
Anything marked **[Claude's call]** was decided by the author, not the owner, and can be overruled.

## 1. Intent

The owner builds Android apps (React Native / Expo and native). Testing them today means an AI
agent or a script takes over the phone's real screen, so the owner must hand the phone to the PC and stop using it.

headroid is **headless Chrome for a real Android phone**: AI agents and test scripts drive apps on a hidden virtual
display inside the owner's own phone, over Wi-Fi, for as long as needed, while the owner keeps using the phone
normally: music, reels, typing, calls, or the phone locked in a pocket.

It is a full product, not an MVP. It is open source (Apache-2.0), built for the owner's own use first and published
for other developers. It is not a commercial product and does not need to attract clients. Once complete it will be
shown publicly (LinkedIn post, demo video).

### Why this is possible (proven so far)
- M0 (2026-10-30, `docs/m0/RESULTS.md`): on a POCO F6 (Android 16, HyperOS 3, no root), a scrcpy-server patch adding
  `VIRTUAL_DISPLAY_FLAG_STEAL_TOP_FOCUS_DISABLED` keeps the owner's focus, keyboard and keystrokes on their screen
  while an app on a hidden display is driven.
- Pocket spike (same night): over wireless ADB with the screen off, one of the owner's React Native apps ran, scrolled and rendered for 5 minutes
  (27/27 distinct frames) without waking the phone.

## 2. Goals

1. **Isolation.** Nothing the automation does is seen, heard or felt by the owner: no focus or keyboard theft, no
   sound, no vibration, no pop-ups on the owner's screen, and no leaked keystrokes in either direction.
2. **Smoothness.** The owner's phone stays smooth (no keyboard lag, no reel stutter, no audio glitches) while tests run.
   This is measured, not assumed.
3. **Long, unattended runs.** Tests run for hours over Wi-Fi with the screen on or off, survive Wi-Fi blips and adb
   reconnects, and recover or report cleanly when something breaks.
4. **AI-native.** AI agents (ARTEMIS, mobile-use, any MCP client such as Claude Code) can drive the hidden display as
   easily as they drive a normal phone: observe (screenshot plus element list), act, verify, report.
5. **Developer-friendly testing.** A Playwright-style Python API and a test runner with auto-waiting locators,
   assertions, traces, video and an HTML report.
6. **Honest about each phone.** `headroid doctor` probes what the connected phone supports and explains limits; a
   public capability matrix grows from device reports.
7. **Easy to start.** `pip install headroid`, `headroid pair`, `headroid doctor`, run. No root, no app install on the phone.

## 3. Non-goals

- iOS.
- Emulators or cloud device farms as a target (they already work with existing tools; headroid may run on them but
  is not designed for them).
- Root-only features. Root may unlock extras later but nothing core depends on it.
- Replacing ARTEMIS or mobile-use. headroid is the hands and eyes on the hidden display; agents stay the brains.
- Recording or inspecting the owner's own screen or apps.

## 4. Anti-goals (failure even if it "works")

- The owner notices the tests: lag, a sound, a vibration, a closed keyboard, a dialog on their screen, a stolen focus.
- Any capture of the owner's display (display 0) or personal apps, or personal data in published artifacts.
- The phone left in a bad state after a crash: focus stuck on a dead display, a display left behind, an IME or system
  setting changed and not restored.
- Code copied from unlicensed or non-commercial projects (see `docs/CLEAN-ROOM.md`).
- Battery drain or heat that makes the owner want to stop using it.

## 5. Constraints

- Non-rooted phones; Android 14+ is the supported floor for full isolation. Android 13 is "works with caveats",
  Android 10–12 is "best effort" and `doctor` says so.
- Everything on the phone runs as the adb shell user (uid 2000) through `app_process`, like scrcpy.
- Licence Apache-2.0. scrcpy, ARTEMIS and mobile-use code may be adapted with headers and NOTICE entries. Mua,
  PhoneAgent and android-virtual-screen: ideas only, per `docs/CLEAN-ROOM.md`.
- adb itself is not bundled (not open source); users install platform-tools.
- The owner's phone is their daily phone: tests on it are scheduled with the owner, and only the hidden display is
  ever captured.

## 6. Architecture

```
 PC (host)                                               Phone
 ┌────────────────────────────────────────┐   adb (Wi-Fi)   ┌──────────────────────────────────────────┐
 │ AI agents: ARTEMIS · mobile-use · MCP  │                 │ headroid device server (app_process,     │
 │ Test runner (pytest plugin) · CLI      │  JSON-RPC over  │ shell uid, derived from scrcpy-server)   │
 │ headroid Python SDK                    │◄──────────────► │  ├ display manager (hidden displays)     │
 │   Device · Display · Page · Locator    │  adb-forwarded  │  ├ input injector (per display)          │
 │ Connection manager (pair, reconnect)   │  local socket   │  ├ frame capture (on demand / stream)    │
 │ Reports, traces, video                 │                 │  ├ UI tree (UiAutomation, per display)   │
 └────────────────────────────────────────┘                 │  ├ isolation guard (focus, IME, audio)   │
                                                            │  ├ resource governor (thermal, battery)  │
                                                            │  └ watchdog / teardown                   │
                                                            │ Display 0: the owner's screen (untouched)│
                                                            │ Display N: app under test (hidden)       │
                                                            └──────────────────────────────────────────┘
```

### 6.1 Device server (Java, on the phone)
Derived from scrcpy-server v4.1 (Apache-2.0) **[Claude's call: Java, because scrcpy-server is Java and its
reflection wrappers for hidden Android APIs are the most valuable reusable part]**. One long-lived process per phone,
started by the host over adb, serving one JSON-RPC connection over an adb-forwarded `localabstract` socket, plus a
separate binary channel for frames.

Responsibilities:
- **Displays.** Create, resize and destroy hidden virtual displays with the M0 flag set (TRUSTED, OWN_DISPLAY_GROUP,
  ALWAYS_UNLOCKED, OWN_FOCUS, STEAL_TOP_FOCUS_DISABLED, TOUCH_FEEDBACK_DISABLED, no system decorations), IME policy
  HIDE, backed by an `ImageReader` nobody shows. Several displays at once (parallel tests), capped by the governor.
- **Apps.** Launch an app or activity on a display, stop it, clear its data, install/uninstall (via the host), read
  its state.
- **Input.** Tap, long press, swipe, multi-touch, key events and text injected **in-process** with the target
  display id (no `adb shell input`, no new JVM per action). Text without a keyboard (set-text on the focused node,
  falling back to key events), including Unicode.
- **Observation.** Screenshot on demand from the display's own `ImageReader` (PNG/JPEG/raw, optional downscale), an
  optional low-fps video stream for recording, and the UI tree of that display only (UiAutomation windows on all
  displays, filtered by display id), with stable node ids per observation.
- **Effect checks.** Every action can return whether the screen changed (frame hash, tree diff), because injection
  can report success and do nothing.
- **Isolation guard.** Keeps focus on display 0 at all times; mutes the app under test (audio and vibration
  app-ops, restored on teardown); watches for anything from the test app reaching display 0 (dialogs, permission
  prompts, activities, toasts) and moves or reports it; never swaps the system IME; never uses global BACK/HOME.
- **Resource governor.** Watches thermal status, battery level/charging, CPU load and the owner's foreground
  activity; lowers frame rate, pauses or stops tests by policy (e.g. pause above "moderate" thermal, stop below 15 %
  battery when not charging) **[Claude's call on default thresholds]**.
- **Watchdog and teardown.** On disconnect, crash or stop: remove every task on the display, then release the
  display, restore app-ops and settings. Teardown also runs if the host disappears (server notices the socket close).
- **Keep-alive.** Holds what is needed for long locked runs (the shell is already exempt from Doze; the app under
  test may need a Doze/standby exemption, applied only with the owner's consent and restored after).

### 6.2 Host library (Python 3.11+)
**[Claude's call: Python, per ADR 0003, because ARTEMIS, mobile-use, uiautomator2 and adbutils are Python.]**
Package `headroid` on PyPI; bundles the device-server jar.

- `connect()` / `pair()`: wireless ADB pairing and connection (mDNS discovery), automatic reconnect when the phone's
  port or IP changes, starting and upgrading the device server.
- `Device`: capabilities from `doctor`, list/create displays, governor status.
- `Display` / `Page`: one hidden display with one app; `screenshot()`, `tree()`, `tap()`, `type()`, `swipe()`,
  `press()`, `launch()`, `wait_for_idle()`, `record_video()`.
- `Locator`: find by text, resource-id / React Native `testID`, content description, role, Flutter semantics label,
  XPath, or image; auto-wait for visible and stable; actions and assertions on locators (`expect(locator).to_have_text()`).
- Async-first API with a sync wrapper.

### 6.3 Test runner
- `pytest` plugin `headroid.test`: fixtures (`device`, `page`, `app`), `expect` assertions with auto-wait, retries,
  parallel tests on several hidden displays of one phone and across phones, per-test traces (actions, screenshots
  before/after, UI trees, logcat of the app), video, and an HTML report.
- Crash and ANR detection for the app under test, attached to the failing test.
- **[Claude's call]** Results go to an HTML report plus a console summary; an optional notification (desktop
  toast, and later a phone notification shown only on the owner's request) when a long run finishes or finds a bug.

### 6.4 AI agents
- **MCP server** (`headroid mcp`): tools to open a hidden display with an app, observe (screenshot plus element
  list), act (tap/type/swipe/press by element or coordinates), assert, record, report a bug, close. Any MCP client
  (Claude Code, Codex, Gemini) can test apps on the hidden display.
- **ARTEMIS driver**: `HeadroidDriver(BaseDeviceDriver)` implementing ARTEMIS's driver contract (connect, screen
  data with screenshot and UI XML, tap, long press, swipe, text, keys, launch/stop app, current package, shell,
  video), plus the factory hook to select it. Offered upstream to google/artemis; kept in `integrations/artemis` meanwhile.
- **mobile-use controller** with the same role, in `integrations/mobile-use`, offered upstream.
- **Exploratory mode**: "test this app and find bugs" for a set duration, using an agent, producing a bug report
  with steps, screenshots and video.

### 6.5 Doctor and capability matrix
`headroid doctor` probes the connected phone: Android version and OEM skin, shell permissions, display flags
accepted, focus isolation, IME policy, frame capture path, UI tree per display, screen-off behaviour, thermal API,
and prints what will and won't work with fixes. Results can be submitted as a device report to grow
`docs/CAPABILITY-MATRIX.md`.

### 6.6 Frameworks
Native Android views and React Native first (`testID` mapped to resource-id; the headroid sample apps are the reference), then
Flutter (semantics tree), then Jetpack Compose specifics (test tags), WebViews (via accessibility, Chrome DevTools
later).

### 6.7 Sample apps
**headroid sample app** (`dev.headroid.sample`, in `sample-app/`): a small native Android app (Kotlin) that headroid
uses as its own test target and its demo. Screens exercise everything isolation and testing must handle: login and
form with text fields (keyboard), lists and scrolling, a checkout-like multi-step flow, a button that plays a sound, a
button that vibrates, a permission request, a dialog, a toast, a notification, a deliberate crash and an ANR trigger,
a `FLAG_SECURE` screen, and a long-running timer (for screen-off liveness). Every control has a resource-id and
content description. Built by Gradle locally and by GitHub Actions on every push, which attaches the APK as a build
artifact and to releases **[Claude's call: GitHub Actions instead of Google Cloud Build, which the owner offered,
because Actions is free for public repos and needs no cloud credentials]**. A React Native sample (same screens,
`testID`s) follows in M2 for React Native locators.

## 7. Delivery order

Full product, built in this order so each stage is usable and verified on the owner's phone before the next:

| Stage | Delivers | Done when |
|---|---|---|
| M1 Device server | 6.1 complete | The sample app driven on a hidden display over Wi-Fi for 60 min, screen on and off, owner using music and reels with no felt lag; measured frame times and battery; clean teardown after kill -9 of host and server |
| M2 SDK and CLI | 6.2, `pair`, `doctor`, `screenshot`, `run` | A Python script completes the sample app's login and form flows with locators (resource-id, text, and `testID` on the React Native sample) |
| M3 Agents | 6.4: MCP server, ARTEMIS driver, mobile-use controller | ARTEMIS Flash and Pro and Claude Code (via MCP) each complete the sample app's checkout flow on the hidden display while the owner uses the phone |
| M4 Test runner | 6.3 | The sample test suite runs in parallel on 2 hidden displays (two sample apps or two instances) with an HTML report |
| M5 Frameworks and devices | 6.5, 6.6 | Flutter sample app passes; capability matrix covers at least 3 OEMs (owner's POCO plus devices the owner can borrow or community reports) |
| Launch | Docs site, PyPI release, demo video, LinkedIn post | Release tagged; README quick start works from scratch on a clean PC |

Cross-cutting from the start: unit tests on host and server, an on-device integration suite (run on the owner's
phone by appointment), CI on GitHub Actions (builds, unit tests, lint, licence/NOTICE check), changelog, ADRs for
significant decisions, clean-room review on every PR.

## 8. Testing and safety on the owner's phone

- Test apps: the **headroid sample app** (built in this repo, see 6.7), Android Settings, and later a React Native
  sample. The owner's client apps are not used as test targets.
- Never capture display 0. Screenshots of the hidden display only; personal data (Wi-Fi name, other apps' data) is
  never published.
- Anything that changes a phone setting (Doze exemption, app-ops) is announced, consented to and restored.
- Long runs are scheduled with the owner.

## 9. Left to the builder

Wire format details, class layout, thread model in the server, frame encoding choices, reconnect back-off, report
styling, CLI flag names, exact governor thresholds (subject to measurement), and the order of tasks inside a stage.

## 10. Decisions from the builder check

Answered from the project:
- **ARTEMIS source** is the owner's fork at `~/artemis` (Apache-2.0); the driver contract is
  `artemis/drivers/base.py` `BaseDeviceDriver` (connect/disconnect, `get_screen_data` returning `ScreenData` with
  screenshot bytes/base64, UI XML and parsed elements, tap, long press, swipe, swipe_direction, input_text,
  press_key, launch/stop app, current package, execute_shell, start/stop video). Drivers are chosen in
  `artemis/drivers/factory.py`. M3 pins the fork's commit at the time of integration. ARTEMIS Pro needs its LLM key
  configured on the owner's PC (already in use for the owner's other projects).

**[Claude's call]** settled without the owner:
- **Smoothness bar (goal 2).** Numeric plus owner sign-off. Measured on the owner's foreground app with
  `dumpsys gfxinfo <pkg> framestats` (no root): janky-frame share and p95 frame time with headroid running may be at
  most 2 percentage points / 10 % worse than the same scenario without it; keyboard: no dropped keys in a scripted
  typing check; audio: no audible glitch in owner's music (owner judgement). The M0 lag gets a root-cause
  investigation in M1 (dumpsys polling vs per-action JVM vs encoding), each measured separately.
- **Frames.** Screenshots come from the display's `ImageReader` (always drained, latest-image only). Video recording
  is opt-in, H.264 via MediaCodec reusing scrcpy's encoder path, default 720p at 10 fps, and must work screen-off.
  No encoder runs when nobody is recording.
- **Android coverage before M5.** The POCO F6 is the real-device target; an emulator CI lane (Android 14, 15, 16
  AVDs) runs the device-server API-surface tests so code stays version-gated, not HyperOS-specific.
- **Muting.** Per-app app-ops (`PLAY_AUDIO`, `VIBRATE`, `TOAST_WINDOW` where allowed) applied only while the app is
  under test and restored after. If an OEM ignores them, `doctor` reports it as a documented limitation, not a
  blocker. The app under test is single-instance: while it runs on a hidden display the owner can't also open it on
  display 0 (the guard detects this and pauses the test).
- Java server, Python 3.11+ async-first host, HTML report plus optional desktop notification, governor defaults
  (pause above "moderate" thermal, stop below 15 % battery when not charging) stand as decided.

## 11. Open questions for the owner

Answered by the owner on 2026-10-30:
- **Test targets:** do not use the owner's client apps; headroid builds its own sample app (6.7).
- **Phone testing:** only when the owner is available and agrees. Code work may continue unattended (e.g.
  overnight); every on-device acceptance check is batched for a session with the owner.
- **Cloud build:** owner offered Google Cloud Build; GitHub Actions is used instead (see 6.7). Cloud Build stays an
  option if Actions falls short.
- **Approval:** the owner asked for the build to proceed with this design.
