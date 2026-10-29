# Roadmap

Each milestone ends with something you can run and a written result. Status lives in GitHub issues and milestones.

## M0: Proof of concept (go / no-go)
Goal: prove isolation on a real phone using stock tools before writing framework code.
- [ ] Run `scrcpy --new-display ... --no-window` with an app on a hidden display over wireless ADB
- [ ] Inject taps, swipes and text with `adb shell input -d N` while the owner types in another app
- [ ] Measure focus steal (`dumpsys window | grep mTopFocusedDisplayId`), keyboard interference, audio and dialog leaks
- [ ] Repeat with a one-line scrcpy-server change adding `STEAL_TOP_FOCUS_DISABLED`
- [ ] Record results in the [capability matrix](CAPABILITY-MATRIX.md)

**Go** if the owner's typing is not disturbed and the app keeps running. Otherwise rescope to "dedicated test phone".

## M1: Device server
- [ ] Fork scrcpy-server into `device-server/` with attribution
- [ ] JSON-RPC: create/destroy display, launch app, tap/swipe/key/text, frame capture, UI tree
- [ ] Focus guard, IME `HIDE`, mute, teardown on disconnect
- [ ] Teardown order: remove every task on the display **before** releasing it (otherwise focus can stick to a dead
      display until reboot; see [TECHNIQUES.md](research/TECHNIQUES.md) §3.9)
- [ ] Verify the effect of every injected action (injection can report success and do nothing)
- [ ] Never swap the system default IME or use global accessibility actions such as BACK: both hit the owner's display
- [ ] `headroid doctor`: probe what the connected phone supports

## M2: TypeScript SDK and CLI
- [ ] `Device`, `Page`, `Locator` with auto-wait; screenshots and video
- [ ] `headroid pair` / `connect` for wireless ADB, with reconnect on port change

## M3: Test runner
- [ ] `@headroid/test`: fixtures, `expect`, retries, parallel pages (multiple hidden displays), HTML report, traces

## M4: AI agents
- [ ] `@headroid/mcp` server: launch, observe, act, assert, report_bug
- [ ] Exploratory "find bugs in this app" mode with Markdown bug reports and screenshots

## M5: Frameworks and devices
- [ ] React Native (testID → resource-id), then Flutter (semantics)
- [ ] Capability matrix across Pixel, Samsung, Xiaomi, OnePlus/Oppo, Android 13–16
- [ ] Python client
