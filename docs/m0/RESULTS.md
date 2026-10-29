# M0 results: proof of concept on a real phone

**Verdict: GO.** With a one-flag change to scrcpy-server, an app runs and is driven on a hidden display while the
owner types in another app: focus, keyboard and keystrokes stay with the owner. The owner noticed a slight keyboard lag
while the session was running; that is now an M1 item.

Date: 2026-10-29/30. Tester: project owner (own daily phone). Driver: Claude Code over adb.

## Device

| | |
|---|---|
| Phone | Xiaomi POCO F6 (24069PC21I, `peridot`) |
| OS | HyperOS 3.0 (OS3.0.303.0.WNPINXM), Android 16 (SDK 36), patch 2026-07-01 |
| Screen | 1220x2712 @ 480 dpi |
| Connection | **USB** adb (wireless ADB not tested yet) |
| `activities_on_secondary_displays` | present |
| Shell (uid 2000) permissions | `ADD_TRUSTED_DISPLAY`, `ADD_ALWAYS_UNLOCKED_DISPLAY`, `CAPTURE_VIDEO_OUTPUT`, `INJECT_EVENTS`, `INTERNAL_SYSTEM_WINDOW`: all granted |

## Setup

```sh
scrcpy -s <serial> --new-display=1080x2400/420 --start-app=com.android.settings \
  --no-vd-system-decorations --display-ime-policy=hide --no-audio \
  --no-window --no-playback --record=m0.mp4 --time-limit=600
```

Run 1 used the stock scrcpy 4.1 server. Run 2 used the same client with a server built from scrcpy v4.1 plus
[`device-server/patches/0001-steal-top-focus-disabled.diff`](../../device-server/patches/0001-steal-top-focus-disabled.diff)
(`SCRCPY_SERVER_PATH=<built server>`).

The test app was Settings: harmless, present on every phone, and has a search field for text input.

## What worked (both runs)

| Check | Result |
|---|---|
| Virtual display created by the shell | ✅ trusted, own display group, always unlocked, own focus |
| App launched on it with `--start-app` | ✅ top-resumed on the hidden display; the owner's display untouched |
| `input -d N tap / swipe / keyevent / text` | ✅ lands only on the hidden display |
| Keyboard with `--display-ime-policy=hide` | ✅ never shown for the hidden display; `input text` types without it |
| Screenshot: `screencap -d <logical id>` | ❌ "Display Id is not valid" |
| Screenshot: `screencap -d <SurfaceFlinger id>` | ✅ id from `dumpsys SurfaceFlinger --display-id` |
| UI tree: `uiautomator dump --display N` | ✅ nodes from the hidden app only |
| Teardown when scrcpy exits | ✅ display removed, its tasks closed, focus back on display 0 |

## Interference test

The owner typed continuously in Xiaomi Notes on the main display with the keyboard up. A 30-second loop injected
taps, text and swipes into the hidden display. After every action we recorded `mTopFocusedDisplayId`, `mInputShown`
and the IME input target.

| | Run 1: stock scrcpy 4.1 | Run 2: + `STEAL_TOP_FOCUS_DISABLED` |
|---|---|---|
| Focus after launching the app | moved to the hidden display | **stayed on display 0** |
| Focus during injection | moved on the first injected event; back only when the owner tapped, then moved again | **display 0 in 26/26 samples** |
| Owner's keyboard | closed; owner could not type | **open the whole time, attached to Notes** |
| Owner's keys in the hidden app | unclear (injected DELs could have erased them) | **none**: field held exactly the injected text |
| Injection on the hidden display | worked | worked (8/8 cycles) |
| Owner report | "keyboard was gone, focus also gone, I was not able to type" | "no problem, but a little lag in the keyboard while the session was connected" |

Logs: [stock](evidence/interference-stock.log), [fixed](evidence/interference-fixed.log).
Hidden-display screenshots: [stock typing](evidence/stock-01-typed-on-hidden-display.png),
[fixed typing](evidence/fixed-01-typed-on-hidden-display.png), [after owner typed](evidence/fixed-02-after-owner-typing.png)
(search box = `wifi` + `zq` x 8, no owner letters).

## Open findings

1. **Keyboard lag during the session.** Smooth before and after; slightly laggy while connected. Likely contributors,
   to measure in M1:
   - our probe loop ran three `dumpsys` calls after every action; `dumpsys window` holds the window manager lock;
   - every `adb shell input` starts a new `app_process` JVM;
   - the server encoded a 1080x2400 @ 60 fps stream and the PC recorded it.
   The M1 device server should inject over its own socket, read state without `dumpsys`, and encode only on demand
   (or at a low frame rate).
2. `uiautomator dump --display N` right after `input text` didn't contain the typed text, though the screenshot did.
   Check whether the dump lags or the field exposes text differently.
3. Not tested yet: wireless ADB, phone locked / screen off, audio and notifications from the test app, `FLAG_SECURE`
   apps, sessions longer than 10 minutes, dialogs (permissions, crash/ANR) from the hidden app.

## Privacy

Only the hidden display was captured or read. One screenshot command also captured the main display; that file was
deleted unopened. Screenshots showing personal data (Wi-Fi name, per-app battery use) are not published, nor are the
session recordings.
