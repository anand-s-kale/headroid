# Roadmap

Each milestone ends with something you can run and a written result. Status lives in GitHub issues and milestones.

## M0: Proof of concept (go / no-go)
Goal: prove isolation on a real phone using stock tools before writing framework code.
- [x] Run `scrcpy --new-display ... --no-window` with an app on a hidden display (over USB; wireless ADB moved to M1)
- [x] Inject taps, swipes and text with `adb shell input -d N` while the owner types in another app
- [x] Measure focus steal (`dumpsys window | grep mTopFocusedDisplayId`) and keyboard interference
      (audio and dialog leaks moved to M1)
- [x] Repeat with a one-line scrcpy-server change adding `STEAL_TOP_FOCUS_DISABLED`
- [x] Record results in the [capability matrix](CAPABILITY-MATRIX.md)

**Go** if the owner's typing is not disturbed and the app keeps running. Otherwise rescope to "dedicated test phone".

**Result (2026-10-30): GO.** See [M0 results](m0/RESULTS.md).

## M1: Device server
- [ ] Fork scrcpy-server into `device-server/` with attribution
- [ ] JSON-RPC: create/destroy display, launch app, tap/swipe/key/text, frame capture, UI tree
- [ ] Focus guard, IME `HIDE`, mute, teardown on disconnect
- [ ] Teardown order: remove every task on the display **before** releasing it (otherwise focus can stick to a dead
      display until reboot; see [TECHNIQUES.md](research/TECHNIQUES.md) §3.9)
- [ ] Verify the effect of every injected action (injection can report success and do nothing)
- [ ] Never swap the system default IME or use global accessibility actions such as BACK: both hit the owner's display
- [ ] `headroid doctor`: probe what the connected phone supports
- [ ] Owner-side smoothness: find and remove the keyboard lag seen in M0 (inject over the server socket instead of
      `adb shell input`, no `dumpsys` polling, encode frames only on demand or at low fps); measure owner frame times
- [ ] Carried over from M0: wireless ADB, screen off / locked, audio and notification leaks, dialogs from the hidden
      app, `FLAG_SECURE` apps, sessions longer than 10 minutes

## M2: Python SDK and CLI
- [ ] `Device`, `Page`, `Locator` with auto-wait; screenshots and video (on `adbutils`)
- [ ] `headroid pair` / `connect` for wireless ADB, with reconnect on port change
- [ ] Adapt useful ARTEMIS / mobile-use host modules with attribution (hierarchy parsing, device lock, diagnosis)

## M3: Agents on the hidden display
- [ ] `integrations/artemis`: `HeadroidDriver(BaseDeviceDriver)`; run an ARTEMIS Flash task on display N; offer upstream
- [ ] `integrations/mobile-use`: same for mobile-use's controller; offer upstream
- [ ] `headroid.mcp` server: launch, observe, act, assert, report_bug

## M4: Test runner
- [ ] `headroid.test` pytest plugin: fixtures, `expect`, retries, parallel pages (multiple hidden displays), HTML report, traces
- [ ] Exploratory "find bugs in this app" mode (ARTEMIS Pro + headroid) with bug reports and screenshots

## M5: Frameworks and devices
- [ ] React Native (testID → resource-id), then Flutter (semantics)
- [ ] Capability matrix across Pixel, Samsung, Xiaomi, OnePlus/Oppo, Android 13–16
- [ ] TypeScript client
