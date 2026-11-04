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

## Session 2026-11-03: usable by others

- Muting (plan Task 1.8, part): `AppMuter` + `AppOpsLedger` (unit-tested). `app.launch` mutes `PLAY_AUDIO` and
  `VIBRATE` by default (`mute:false` to opt out); `muteNotifications:true` revokes `POST_NOTIFICATIONS` (only when the
  app is not running, since revoking kills it). Original modes go to `/data/local/tmp/headroid-appops-<pid>.txt`
  before any change; restored on `app.stop`, teardown, and by the next server start when that pid is gone.
  `TOAST_WINDOW` dropped: text toasts are drawn by SystemUI on the app's display and never leaked.
  Verified on the POCO F6 over wireless adb: default, opt-in notifications, `kill -9` recovery, two servers at once.
- Host (merged from `claude/host-usability`): jar resolution (arg, env, wheel, source build), `wait_for`/`click`/
  `fill`, `doctor`/`devices`/`launch`, unique socket per session; jar pushed to a content-named path.
  Wheel built locally and installed in a clean venv: `doctor` all PASS and `launch` worked on the phone while
  another session was running.
- Shared phone (found by the long run: a second session's `launch` force-stopped the first one's app): teardown
  releases displays first, then force-stops only when the app was not in use before launch (`am get-uid-state`, cached
  counts as not in use) and has no activities on displays this session does not own (`AppPresence`, unit-tested).
  `app.stop` returns `{stopped, reason}`. UiAutomation is leased per call (released after 1 s idle, waits up to 10 s
  when busy). Verified: two sessions on one app, `uiautomator dump` alongside, smoke 8/8, no process left.
  Follow-up: one shared server per phone multiplexing sessions would remove the UiAutomation contention entirely.
- Wi-Fi resilience (found by the second 60-min run: adb transport dropped at minute ~17, server died with it):
  server started with `setsid ... &` and stdio closed, `grace_ms=60000`; host `ReconnectingClient` reconnects (new
  forward, `Adb.relocate` by `ro.serialno`) and resends only read calls. Verified with `adb reconnect` mid-session:
  back in 6 s, timer continued, tap worked; orphan server tore down 60 s after losing its host.
- PyPI: **0.1.0a1 published 2026-11-03** (https://pypi.org/project/headroid/) via trusted publishing; GitHub
  pre-release v0.1.0a1 has the wheel, jar and sample APK. Verified `pip install --pre headroid` in a clean venv: doctor
  all PASS and launch worked on the POCO F6. The `pypi` GitHub environment was auto-created without a reviewer.
  **0.1.0a2 published 2026-11-04** (Recents fix, UiAutomation idle 5 s); verified the same way from a clean venv:
  doctor all PASS, launch OK, no sample entry in the visible Recents.
- Open: in the third 60-min run the sample app on the hidden display ended between minute 12 and 13 with no kill
  line in the log (headroid's guard was not involved: the next process was started by another session). Possibly
  HyperOS power management; the fourth run logs the app pid and uid state every minute.
- Not done: focus check / leak watch part of Task 1.8, governor (1.9), video (1.10). Screen-off operation
  passed 30 min locked (checklist 7b rerun, 2026-11-04) but failed intermittently in 3 earlier locked runs; root
  cause not found yet.

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
3. **Owner typing while tests run** — **PASSED 2026-10-30**. Owner typed "AAAA" in their own app for 2 min while the
   server typed "zqx " into the sample form on the hidden display (85 bursts, 0 errors). 26 samples every ~4 s:
   `mTopFocusedDisplayId` 0 in 26/26, IME token display 0 in 26/26. Hidden field held only "zqx" text (screenshot);
   owner confirmed their text was only A's and the keyboard behaved normally. (Re-tapping a misspelled word opened the
   sample's spell-check popup and once replaced a word with "xerox": test-script artifact, stayed on the hidden display.)
4. **Teardown** — **PASSED 2026-10-30** after one fix. Host killed hard: display and activities gone ~15 s later
   (grace period). Server `kill -9`: gone within 3 s. Server SIGTERM: gone within 3 s, no hang. Focus on display 0
   throughout. Found: after the grace teardown the server stayed alive listening forever (an orphan process on the
   phone, which also made a later host attach to the stale server). Fixed: the server exits after the grace teardown
   (not from inside the shutdown hook, where `System.exit` blocks). Smoke rerun after the fix: 8/8, no server left.
5. **Effects leakage** — **RECORDED 2026-10-30** (sample `EffectsActivity` on the hidden display; owner watching,
   screen on, volume up, DND off; focus on display 0 throughout):
   | Effect | Reaches the owner? | Evidence |
   |---|---|---|
   | Sound (`ToneGenerator`, STREAM_MUSIC) | **Yes** | owner heard it |
   | Vibration | **Yes** | owner felt it |
   | Toast (text toast, drawn by SystemUI) | No | toast window on the hidden display (screenshot), 3 tries, owner saw none |
   | Dialog | No | dialog in the hidden display tree and screenshot; owner saw none |
   | Notification | **Yes** | owner saw it in the notification shade; removed by the teardown force-stop |
   | Camera permission prompt | No | permission controller drawn on the hidden display (screenshot); owner saw none |
   Sound, vibration and notifications are what plan Task 1.8 must mute (app-ops with restore). Test-script note: find
   dialog buttons by resource id (`android:id/button2`), not text; the displayed "CANCEL" did not match a text search.
6. **Smoothness** — **PASSED 2026-11-03** (Instagram in front, owner scrolling, 90 s per stage, wireless adb):
   0 janky frames in every stage; p95 6 ms nothing / 6 idle / 6 taps / 7 screenshots / 6 UI reads every 1 s.
   First run: UI reads every 1 s gave p99 38 ms because UiAutomation reconnected 64 times in 90 s (idle release
   1 s); with 5 s idle release, 1 connect and p99 9 ms. Owner: nothing felt laggy. Plan Task 1.12 done.
   Original plan:  `dumpsys gfxinfo <owner app> framestats` janky share and p95 with nothing / server idle / actions
   every 1 s / screenshots every 1 s / `ui.tree` every 1 s (plan Task 1.12), plus the owner's feel of keyboard lag.
7. **Long runs** — 2026-11-04, wireless adb, phone unplugged, one sample per minute (`TimerActivity` on the hidden
   display; screenshot + `find(rid="timer_value")`, `mTopFocusedDisplayId`, battery, temperature, server RSS).
   - **7a screen on — PASSED, 58 clean minutes** (07:58–08:57, owner using the phone). Same app pid throughout,
     timer within 1 s of wall time at every sample, focus on display 0 in 58/58, screenshot and tree OK every minute,
     battery 90 → 76 %, 35–37 °C, thermal status 0, server RSS 189 → 95 MB (falling). At 08:57 the phone left Wi-Fi
     adb entirely (not even in `adb mdns services`); the host waited 60 s, the server tore the session down, and the
     error was clear. Wireless debugging had to be re-enabled on the phone, so minutes 58–60 are missing.
   - **7b screen off — FAILED the "keeps working" goal** (09:02–09:32, locked by `input keyevent 223`). Good: Wi-Fi
     adb stayed up 30 min in Doze, app pid unchanged, screenshot OK every minute, focus on display 0 30/30, battery
     74 → 71 %, 38 → 33 °C, clean teardown. Bad: while the phone is asleep the hidden display sleeps with it. The
     timer text stopped updating (end screenshot shows 1089, the value from when the screen last turned off) and
     `find` returned nothing (`tree_ms` ~5.2 s, i.e. no window). At 09:20 the screen woke for one sample and the
     timer read 1081 / 1082 expected, so the process kept running; only drawing and the window tree stop. Likely
     cause guessed then (power) was **wrong**, see the rerun below.
   - **7b rerun — PASSED, 30/30 minutes locked** (10:13–10:43, no code change). New frame every minute, full tree
     (12 nodes), timer within 1 s of wall time at every sample. Investigation before it (all locked): the display
     has `OWN_DISPLAY_GROUP` + `ALWAYS_UNLOCKED`, sits in power group 1, and group 1 stays awake (wakefulness 1,
     display `state ON`) for 3+ min while group 0 dozes; TimerActivity stays RESUMED, process state TOP, not
     frozen. `dumpsys` calls between reads do not break it. Of 8 locked runs today, 3 failed early (find empty,
     ~5 s per read, which matches the 5 s accessibility interaction timeout when the app's UI thread does not
     answer) and the last 5 passed, including 6 and 30 min. One failing run also failed **before** the lock (the
     `nav_timer` tap did not open the timer). Not reproduced since, root cause unknown. Suspect: the failing runs
     reused a sample-app process left over from a session that was killed (Wi-Fi drop, orphaned host). Next time it
     fails, the trap script (scratchpad `why6.py`: one read per minute, on first failure saves screenshot, tree,
     window/activity/power/display/SurfaceFlinger/accessibility dumps, logcat, app ticks and a `debuggerd -j`
     stack) will show where the app's UI thread is stuck. A power keep-awake ticker is **not** needed.
   - **Root cause found (2026-11-04): HyperOS `GreezeManager` freezes the app under test on screen off.**
     Reproduced 3/3 right after toggling Wireless debugging, then 1/1 more: within 15–40 s of `KEYCODE_SLEEP` the
     sample's own 10 s log ticks stop, frames stop, and the tree has no windows (each read ~5 s = accessibility
     timeout). Logcat: `GreezeManager: FZ uid = 10814 reason =screen off success !`. Android's own freezer says
     `isFrozen=false` and the activity stays RESUMED, process state TOP, which is why the earlier checks looked
     healthy. HyperOS treats an app visible only on a virtual display as background. The runs that passed
     (09:52–10:43) followed the owner opening the sample on display 0 at 09:46, which apparently made Greeze treat it
     as a recently used app. Tried: `dumpsys deviceidle whitelist +pkg` does **not** stop it. Greeze
     (`service greezer`, `miui.greeze.IGreezeManager`) thaws on network packets, broadcasts to receivers, signals,
     binder calls, provider/service starts and activity launches, refreezing after `fz_timeout=5000`; its
     `persist.sys.gz.monkey` switch is not settable from shell. Next: check whether the owner-set battery mode
     "No restrictions" for the app exempts it; otherwise detect it (app pid in `dumpsys greezer` "Frozen
     processes") and fail with a clear error, or thaw on demand before each action.
     **Workaround confirmed:** with Settings > Apps > headroid sample > Battery saver > "No restrictions", 2/2 locked
     runs passed (90 s, every read OK; logcat `GreezeManager: triggerL ignore uid = 10814`). Shipped: `ui.tree`
     returns `-32014 APP_FROZEN` with that instruction when the tree is empty and a launched app's pid is in
     Greeze's frozen list (`apps/HyperOsFreezer`), and doctor's Xiaomi warning names the setting. Verified on the
     phone (default battery mode, right after a Wireless debugging toggle): read at 10 s OK, read at 21 s raised
     `RpcError [-32014] dev.headroid.sample is frozen by HyperOS ...` with the instruction. Without a toggle, the
     owner having just opened the app's settings page kept Greeze from freezing it for 100+ s.
   - **Leftover-process theory — disproved** (2026-11-04): a fresh locked session on a sample process left by a
     killed session passed 2 min. While testing it, found a real isolation bug instead: every session left the
     app's task in the owner's **Recents** (13 entries on the POCO F6; the server destroys the activities on
     release, the task record stays). At 09:46 one was opened from Recents and started `MainActivity` on display 0
     (events log: `startExistingRecents`, then `wm_create_activity` on display 0). That explains the two failed
     runs at 09:46–09:50 only partly; 7b's own task stayed on its hidden display all run (no moves or stops in the
     events log), so 7b's failure is still unexplained. Fixed: launches add `FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS`
     (verified: the new task is absent from "Visible recent tasks"; smoke 8/8). Old entries on the phone need the
     owner to swipe them away; adb has no command to drop past Recents entries. The live task on display 0 was
     removed with `am stack remove`.
     Test-harness note: on Windows, stopping a background bash task can leave its `python.exe` child running, which
     keeps the session alive on the phone; kill leftover host scripts by command line.

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
