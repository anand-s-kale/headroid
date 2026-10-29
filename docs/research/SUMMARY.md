# Headless Android testing on a real phone: research summary (2026-10-29)

Reports in this folder: FEASIBILITY-claude.md (Claude Opus), VIABILITY-codex.md (Codex),
PRIOR-ART-claude.md (Claude Sonnet), REVIEW-gemini.md (Gemini reviewer).

## Verdict: viable, but only as a test-framework layer, and with known leaks
- Do not build the runtime. scrcpy (Apache-2.0) already creates a virtual display without root, launches apps on it and injects input into it.
  Several small projects already run AI agents on a Shizuku virtual display (Mua, PhoneAgent, android-virtual-screen, ClosePaw, Ruto-GLM, lamda).
- What nobody has built: a Playwright-style test framework on top of this (locators, auto-wait, assertions, runner, traces/video, bug reports),
  driven from the PC over wireless ADB, with a per-display UI tree, plus a tested capability matrix per Android version and phone brand.
- Android 14+ is the practical floor (on 10–12 the trusted display is not available to the shell; 13 leaks focus).
- The "owner keeps using the phone with zero interference" promise is only partly achievable without root:
  - A one-flag scrcpy-server change (STEAL_TOP_FOCUS_DISABLED) stops focus being stolen by taps.
  - It does not cover activity launches or dialogs, the shared keyboard service, audio/vibration/notifications, or FLAG_SECURE apps (black screenshots).
  - Must be measured on a real phone.

## Where the reviewer was right
- PRIOR-ART said Appium has no displayId support. That is wrong: the UiAutomator2 driver has `currentDisplayId` (Android 11+).
- STEAL_TOP_FOCUS_DISABLED is ignored unless OWN_FOCUS + TRUSTED are set (confirmed in VirtualDisplayAdapter.java:625-632), and it only covers tap-to-focus.
- `screencap -d` on a virtual display is unreliable; capture frames from our own ImageReader in the server instead.
- Android 15 QPR builds have rejected trusted-display creation (scrcpy issue #5523), so shell permissions can shrink in new releases.
- Licensing: Mua and PhoneAgent have no licence; android-virtual-screen is noncommercial. Learn from them, copy nothing.
- Missed prior art: Maestro, Airtest, Google's VirtualDeviceManager samples, Taskbar.

## Where the reviewer was wrong (checked)
- "scrcpy --no-window --no-audio exits with 'nothing to do'": false. cli.c:3050-3055 keeps control enabled without a window, so the PoC command is valid.
- Smaller errors: sndcpy is by Romain Vimont, not "Romain Thomas". The Airtest star count and the "VDM will replace this in Android 17" claim are unverified.

## Cheapest next step (1 day, before creating a repo)
On the owner's phone (Android 14+), with wireless ADB:
1. `scrcpy --new-display=1080x2400/420 --start-app=<pkg> --no-vd-system-decorations --display-ime-policy=hide --no-audio --no-window`
2. While using WhatsApp by hand, run `adb shell input -d N tap/swipe/text ...` and watch `dumpsys window | grep mTopFocusedDisplayId`.
3. Read the UI tree via Appium (`currentDisplayId=N`), and frames via scrcpy `--record`.
4. Repeat with a scrcpy-server fork that adds flag 1<<16. Record what leaks: keyboard, focus, audio, dialogs, screen-off behaviour.
Go if typing in WhatsApp is not disturbed and the app keeps running. Kill or rescope (dedicated test phone) if it is.
