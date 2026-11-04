# Capability matrix

What actually works, per device, **without root**. Entries move from *expected* to *verified* only with a device report.
Add yours with the [device report issue form](../../../issues/new?template=device_report.yml).

Legend: ✅ works · ⚠️ works with caveats · ❌ does not work · ❔ untested

## Expected (from research, not yet verified)

| Capability | A10–12 | A13 | A14–16 | Source |
|---|---|---|---|---|
| Create hidden virtual display (shell uid) | ✅ | ✅ | ✅ | scrcpy `--new-display` |
| Trusted display (`ADD_TRUSTED_DISPLAY`) | ❌ | ✅ | ⚠️ (A15 QPR regression reported) | AOSP shell manifest; scrcpy #5523 |
| Launch any exported activity on it | ✅ | ✅ | ✅ | `am start --display N` |
| Input only on the hidden display | ✅ | ✅ | ✅ | `input -d N` |
| User keeps focus while agent taps | ❌ | ❌ | ⚠️ | `STEAL_TOP_FOCUS_DISABLED` |
| Hide keyboard on test display | ❌ | ✅ | ✅ | display IME policy |
| Frame capture | ✅ | ✅ | ✅ | own ImageReader |
| Per-display UI tree | ⚠️ (A11+) | ✅ | ✅ | UiAutomation windows on all displays |
| `FLAG_SECURE` content | ❌ | ❌ | ❌ | secure displays need root |
| Isolated audio / notifications | ❌ | ❌ | ❌ | shared system services |
| Runs with screen off / locked | ❔ | ❔ | ❔ | to test |
| AI agent via ARTEMIS manual mode (`headroid mcp`) | ❔ | ❔ | ✅ | e2e login flow passed on POCO F6 (Android 16) 2026-11-04; Xiaomi needs Battery saver "No restrictions" |

## Verified devices

| Device | Android / skin | Date | Reporter | Results |
|---|---|---|---|---|
| Xiaomi POCO F6 (24069PC21I) | Android 16 / HyperOS 3.0 | 2026-10-30 | owner | [M0](m0/RESULTS.md): see below |

### Xiaomi POCO F6, Android 16, HyperOS 3.0 (USB adb)

| Capability | Result | Notes |
|---|---|---|
| Create hidden virtual display (shell uid) | ✅ | scrcpy 4.1 `--new-display` |
| Trusted display (`ADD_TRUSTED_DISPLAY`) | ✅ | permission granted to shell; `FLAG_TRUSTED` set |
| Launch app on it | ✅ | `--start-app`; owner's display untouched |
| Input only on the hidden display | ✅ | `input -d N` tap / swipe / keyevent / text |
| User keeps focus while agent taps | ⚠️ stock ❌ / patched ✅ | stock steals focus and closes the owner's keyboard; with `STEAL_TOP_FOCUS_DISABLED` focus stayed on display 0 in 26/26 samples |
| Hide keyboard on test display | ✅ | `--display-ime-policy=hide`; `input text` still types |
| Owner's keys leak into hidden app | ✅ none (patched) | |
| Frame capture | ✅ | `screencap -d <SurfaceFlinger id>` (logical id rejected) |
| Per-display UI tree | ✅ | `uiautomator dump --display N` |
| Clean teardown on scrcpy exit | ✅ | focus back on display 0 |
| Owner's phone stays smooth | ⚠️ | slight keyboard lag while the session ran (M1 item) |
| Wireless ADB, screen off / locked, audio, `FLAG_SECURE` | ❔ | not tested yet |

### Xiaomi POCO F6, Android 16, HyperOS: headroid M1 server (2026-10-30 to 2026-11-03, USB and wireless adb)

| Capability | Result | Notes |
|---|---|---|
| Hidden display, launch, tap/swipe/key/text, screenshot, UI tree | ✅ | smoke script 8/8, repeated runs |
| Owner keeps focus and keyboard while the hidden display types | ✅ | 26/26 samples on display 0 while the owner typed |
| Teardown after host kill, server `kill -9`, server SIGTERM | ✅ | nothing left: display, app, server process |
| Toast, dialog, permission prompt | ✅ stay hidden | |
| Sound, vibration | ✅ muted | app-ops `PLAY_AUDIO`/`VIBRATE` ignore; vibration logged `ignored_app_ops`; restored after the session and after `kill -9` |
| Notifications | ⚠️ opt-in | app-op is overridden by the permission on A13+; muted by revoking `POST_NOTIFICATIONS` |
| Two sessions at once | ✅ | separate sockets and mute records; one does not unmute the other |
| Owner's phone stays smooth | ✅ | Instagram in front, 90 s per load: 0 janky frames, p95 6-7 ms with taps, screenshots or UI reads every second (p99 9-11 ms); owner felt no lag |
| Install sample app over adb | ⚠️ | needs Developer options → "Install via USB" |
