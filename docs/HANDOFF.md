# Handoff: where headroid stands (2026-10-30, after the overnight session)

For the next agent session picking up headroid. Read this first, then the design.

## What headroid is
Headless Chrome for a real Android phone: AI agents and test scripts drive apps on a **hidden virtual display** inside
the owner's own non-rooted phone, over Wi-Fi, while the owner keeps using the phone (music, reels, typing, or the
phone locked in a pocket). Full product, open source (Apache-2.0), owner's own use first, shown publicly when done.

- Design (approved by the owner to build): [`docs/superpowers/specs/2026-10-30-headroid-design.md`](superpowers/specs/2026-10-30-headroid-design.md)
- Roadmap: [`docs/ROADMAP.md`](ROADMAP.md). Architecture: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md). ADRs: [`docs/adr/`](adr/).
- Clean-room rules: [`docs/CLEAN-ROOM.md`](CLEAN-ROOM.md). Agent rules: [`AGENTS.md`](../AGENTS.md).

## Done so far
1. **Research** (Claude, Codex, Gemini; `docs/research/`): viable on Android 14+ without root; ~70–80 % of the runtime
   exists in other repos, but the best ones are unlicensed or non-commercial, so ideas only
   (`docs/research/TECHNIQUES.md`). scrcpy (Apache-2.0) is the base.
2. **Repo** created public at https://github.com/anand-s-kale/headroid with community files, ADRs 0001–0003,
   capability matrix, milestones M0–M5 and issues.
3. **M0 = GO** ([`docs/m0/RESULTS.md`](m0/RESULTS.md)). On a POCO F6 (Android 16, HyperOS 3):
   - stock scrcpy 4.1 `--new-display` steals focus and closes the owner's keyboard as soon as input is injected;
   - with [`device-server/patches/0001-steal-top-focus-disabled.diff`](../device-server/patches/0001-steal-top-focus-disabled.diff)
     focus, keyboard and keystrokes stayed with the owner (26/26 samples, no leaked keys);
   - the owner felt a **slight keyboard lag** while the session ran (open M1 item).
4. **Pocket spike** (not yet in `docs/m0/`): over **wireless debugging** with the screen **off** the whole time, an
   app on a 720x1600 hidden display at 5 fps ran, scrolled and rendered for 5 minutes (27/27 distinct frames); the
   phone stayed asleep; battery 93 %, 33.9 °C. Longer locked runs (30–60 min) are untested; scrcpy #6643 reports
   freezes "after a while" on locked phones.
5. **Product design** written, builder-checked, and the owner's answers recorded (design §10–11).

## Owner decisions that bind the next session
- **Full product, not an MVP.**
- **Do not use the owner's client apps** as test targets. headroid builds its own sample app (`sample-app/`, design §6.7).
- **No testing on the owner's phone without the owner.** Code work may continue unattended (e.g. overnight).
  Batch every on-device acceptance check for a session with the owner. Emulators on the PC are fine.
- Build the APK with Gradle locally and with **GitHub Actions** (owner offered Google Cloud Build; Actions chosen,
  Cloud Build stays a fallback).
- Commits are signed off (`git commit -s`) and end with the Co-Authored-By line; push to `main` is the current
  practice for this solo repo.

## Session 2026-10-30 (overnight, unattended): summary for the owner

Built the plan, the sample app, the first M1 device server and the Python host. **Nothing has run on a phone or an
emulator yet**: the owner stopped the session before the emulator check, and asked that testing wait for a session
with the phone. The owner's POCO F6 was attached over wireless debugging all session and received no commands.

| Piece | Where | Verified (evidence) |
|---|---|---|
| Implementation plan, all stages, wire protocol v1 | [`docs/superpowers/plans/2026-10-30-headroid-implementation.md`](superpowers/plans/2026-10-30-headroid-implementation.md) | Commit `3dd140f` |
| Sample app `dev.headroid.sample` (all §6.7 screens, ids + content descriptions; login `demo@headroid.dev` / `headroid`) | [`sample-app/`](../sample-app/README.md) | `./gradlew :app:assembleDebug :app:lintDebug` passes locally; Actions run 40940804222 green, artifact `headroid-sample-debug` (827 KB) |
| Device server: scrcpy-server v4.1 fork + `dev.headroid.server.HeadroidServer` | [`device-server/`](../device-server/README.md) | `:server:headroidJar :server:testDebugUnitTest` passes locally (55 headroid tests); Actions run 40940804402 green, artifact `headroid-server` |
| Python host skeleton (`Adb`, `RpcClient`, `ServerProcess`, `Device`, `Display`, CLI) | [`packages/headroid/`](../packages/headroid/README.md) | 9 pytest tests + ruff pass locally; Actions `host` workflow green on 3.11 and 3.13 |
| Emulator / phone smoke script | `packages/headroid/scripts/emulator_smoke.py` | **UNVERIFIED** (never run) |

What the server does (all UNVERIFIED on Android): JSON-RPC on `localabstract:headroid`; `display.create` with the M0
flags plus `DESTROY_CONTENT_ON_REMOVAL` (apps left on a released display are destroyed, not moved to the owner's
screen) and IME policy HIDE; ImageReader-backed screenshots; in-process tap/long press/swipe/key/text per display
with a set-text fallback for emoji and non-Latin text; `ui.tree` from a shell UiAutomation filtered to the display;
`app.launch` with `FLAG_ACTIVITY_MULTIPLE_TASK`; teardown 15 s after the host disconnects (stop launched apps, release
displays, disconnect UiAutomation); display 0 and foreign displays rejected by every RPC.

Environment notes added this session: an AVD `headroid_api36` (Android 16 / 36.1 x86_64, WHPX works) exists but has
not been booted to completion; headless it runs as `qemu-system-x86_64-headless.exe`. `android-actions/setup-android@v3`
needs an explicit `packages:` list on current runners (its default `tools` package fails).

## On-device checklist for the next session with the owner

Run in this order; stop at the first failure. Check the foreground app first (`dumpsys window | grep mCurrentFocus`),
never capture display 0, and keep screenshots of the hidden display only.

1. **Build and install** — **DONE 2026-10-30** (POCO F6, Android 16, wireless adb). Xiaomi refuses `adb install`
   (`INSTALL_FAILED_USER_RESTRICTED`) until the owner turns on Developer options → "Install via USB".
2. **Smoke** — **PASSED 2026-10-30, twice in a row**: all 8 checks true (launch and tree, PNG screenshot, login flow,
   Unicode text via `setText`, `mTopFocusedDisplayId` 0 before and after, display 0 rejected, display and app gone
   after teardown). UiAutomation, `setDisplayImePolicy` and WAIT_FOR_RESULT injection all work on HyperOS.
   First run failed: the tree reports nodes of an incoming activity at their animated position (shifted right by the
   display width for ~0.8 s), so the tap landed off-display and Android only said "failed". Fixed by: the smoke
   script waits for a node to be on screen and at the same bounds on two reads; the server rejects off-display
   touch points with `-32602 (x, y) is outside the WxH display`. The M2 `Locator` must do the same settle check.
3. **Owner typing while tests run**: owner types in a chat app while a loop taps and types on the hidden display
   (M0 method, 26 samples): focus and keyboard stay with the owner, no leaked keys.
4. **Teardown**: `kill -9` the host mid-session, then the server process; after the grace period no `headroid`
   display in `dumpsys display`, no sample activity on display 0, focus on display 0.
5. **Effects leakage** (sample `EffectsActivity`): sound, vibration, toast, dialog, notification, permission prompt.
   Record what reaches the owner (muting is plan Task 1.8, not built yet: expected to leak today).
6. **Smoothness**: `dumpsys gfxinfo <owner app> framestats` janky share and p95 with nothing / server idle / actions
   every 1 s / screenshots every 1 s / `ui.tree` every 1 s (plan Task 1.12), plus the owner's feel of keyboard lag.
7. **Long runs**: sample `TimerActivity` on the hidden display over Wi-Fi for 60 min with music and reels, then 30–60
   min screen off; record battery and temperature at start and end.

## Next work (in order)
1. Run the checklist above with the owner; fix what fails.
2. M1 remaining (plan Tasks 1.8–1.12): isolation guard (focus check, app-op muting with restore, display-0 leak
   watch), resource governor, opt-in video, strip unused scrcpy parts, `verify:true` effect checks, lag root cause.
3. M2 (plan Tasks 2.2–2.6): async API, `Page`, `Locator` + `expect`, `pair`/`connect`, `doctor`, packaging.
4. Emulator CI lane for the device-server API surface (Android 14/15/16 AVDs) once the smoke passes on the phone.

## Environment facts (owner's Windows PC)
- Repo: `C:\Users\Anand\OneDrive - Xalta Technology Services Pvt Ltd\Documents\GitHub\headroid` (OneDrive path,
  long; Gradle and git clones of large repos may hit Windows long-path limits: use a short path such as `C:\hd\`).
- Patched scrcpy v4.1 source and built server: `C:\hd\scrcpy` (`server/build/outputs/apk/release/server-release-unsigned.apk`).
- JDK 17: `C:\Users\Anand\.jdks\ms-17.0.18` (default `java` on PATH is Java 8, so set `JAVA_HOME`).
- Android SDK: `C:\Users\Anand\AppData\Local\Android\Sdk` (platforms 31–37, build-tools up to 37, emulator installed).
  `local.properties` needs forward slashes: `sdk.dir=C:/Users/Anand/AppData/Local/Android/Sdk`.
- scrcpy 4.1 client installed via winget; adb on PATH.
- Git Bash rewrites `/sdcard/...` paths: prefix adb commands with `MSYS_NO_PATHCONV=1`.
- `screencap -d` needs the **SurfaceFlinger** display id (`dumpsys SurfaceFlinger --display-id`), not the logical id.
- `uiautomator dump --display N` works on Android 16 for the hidden display.
- ARTEMIS fork (Apache-2.0) at `~/artemis`; driver contract `artemis/drivers/base.py` (`BaseDeviceDriver`).

## Rules that must not slip
- Never capture or read the owner's display 0 or personal apps. Never publish screenshots with personal data.
- Never copy code from Mua, PhoneAgent or android-virtual-screen.
- Restore every phone setting you change; tear down tasks before releasing a display.
