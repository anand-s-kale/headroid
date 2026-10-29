# Handoff: where headroid stands (2026-10-30)

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

## Next work (in order)
1. Write the implementation plan from the design (superpowers `writing-plans`), saved under `docs/superpowers/plans/`.
2. **Sample app** (`sample-app/`, Kotlin, `dev.headroid.sample`) with the screens listed in design §6.7, plus a GitHub
   Actions workflow that builds it and uploads the APK artifact.
3. **M1 device server**: fork scrcpy-server v4.1 into `device-server/` (keep Genymobile headers, NOTICE), strip
   what headroid doesn't need, add JSON-RPC over an adb-forwarded `localabstract` socket, in-process input injection
   per display, ImageReader screenshots, per-display UI tree, isolation guard, governor, watchdog/teardown.
4. Host skeleton (`packages/` Python): connect/start server, call RPCs, screenshot, tree, tap/type.
5. Verify on an Android 14/15/16 emulator (AVD) on the PC. Leave a checklist of on-device checks for the owner's next
   session (60-min run with music and reels, frame-time measurements, lag root cause, screen-off 30–60 min).

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
