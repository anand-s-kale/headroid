# Changelog

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0a1] - 2026-11-03
First alpha on PyPI: `pip install --pre headroid`.
### Added
- Project charter, architecture, roadmap, capability matrix, clean-room policy and research reports.
- M0 proof of concept on a POCO F6 (Android 16): GO. scrcpy-server patch adding `STEAL_TOP_FOCUS_DISABLED`
  (`device-server/patches/`), results and evidence in `docs/m0/`, first verified device in the capability matrix.
- Implementation plan for the full product (`docs/superpowers/plans/`).
- headroid sample app `dev.headroid.sample` (`sample-app/`) built by GitHub Actions with the debug APK as an artifact.
- M1 device server (`device-server/`): fork of scrcpy-server v4.1 (the M0 patch is now in tree) with JSON-RPC,
  hidden displays, per-display input, screenshots, UI tree and teardown. Unit-tested; not yet run on a device.
- Python host skeleton (`packages/headroid`) and an emulator/phone smoke script.
- Verified on a POCO F6 (Android 16): smoke 8/8, owner typing isolation, crash teardown, effects leakage.
- Sound and vibration of the app under test muted by default (app-ops), restored at stop, teardown and after a crash;
  notifications muted on request (`mute_notifications=True`).
- `Display.wait_for` / `click` / `fill` with settle detection; `headroid doctor`, `devices` and `launch` commands.
- The wheel bundles the server jar; a `release` workflow builds it and attaches it to `v*` releases.
- Several sessions can share a phone: unique server socket, content-named jar on the device, per-server mute records.
### Fixed
- Reading the UI every second reconnected UiAutomation each time, which turns accessibility on for every app and
  made the owner's app drop frames (p99 9 to 38 ms); the connection is now kept for 5 s idle (p99 back to 9 ms).
- A wireless adb drop killed the server (it ran as a child of the adb shell) and left the host waiting; the server
  now runs detached, keeps the session for 60 s, and the host reconnects, also when the phone returns under another
  adb serial.
- Teardown force-stopped the app under test everywhere, killing the owner's copy and other sessions' copies; it
  now stops only apps headroid started that nobody else has open.
- UiAutomation was held for the whole session, blocking other sessions and tools (Appium, uiautomator); it is now
  held only while reading the screen.
- Taps on nodes read mid-transition landed off-display; off-display points are now rejected with a clear error.
- The server stayed alive after the grace-period teardown; it now exits.
