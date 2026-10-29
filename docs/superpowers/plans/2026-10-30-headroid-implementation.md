# headroid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full headroid product (design §7: M1 device server through Launch), starting with the headroid sample app and the M1 device server.

**Architecture:** A Java device server forked from scrcpy-server v4.1 runs on the phone as the shell user (`app_process`), owns hidden virtual displays backed by `ImageReader`s, injects input per display in-process, reads the per-display UI tree through `UiAutomation`, and serves newline-delimited JSON-RPC 2.0 over a `localabstract` socket that the host reaches with `adb forward`. A Python 3.11+ host package (`packages/headroid`) starts the server and wraps the RPCs in `Device` / `Display` objects; SDK, CLI, test runner, MCP server and agent drivers build on it.

**Tech Stack:** Java 17 toolchain targeting Android (AGP 9.1, Gradle 9.3.1, compileSdk 36, JUnit 4) for the device server; Kotlin 2.0.21 + AGP 8.7.3 + Gradle 8.10.2, framework-only (no AndroidX) for the sample app; Python 3.11+, pytest, adb (user-installed) for the host; GitHub Actions for CI.

**Spec:** [`docs/superpowers/specs/2026-10-30-headroid-design.md`](../specs/2026-10-30-headroid-design.md)

## Global Constraints

- Licence Apache-2.0. Files adapted from scrcpy keep the Genymobile / Romain Vimont header, mark changes with `headroid:` and are listed in `NOTICE`.
- Clean room: no code, identifiers, comments or strings from Mua, PhoneAgent or android-virtual-screen (`docs/CLEAN-ROOM.md`).
- Android 14+ (API 34) is the floor for full isolation; API 33 "works with caveats", API 29–32 "best effort". Server `minSdk` 29 (per-display injection needs API 29).
- Everything on the phone runs as uid 2000 via `app_process`; no app install for headroid itself (the sample app is a test target, not part of headroid).
- Hidden display flags on API 34+: `PUBLIC | PRESENTATION | OWN_CONTENT_ONLY | SUPPORTS_TOUCH | ROTATES_WITH_CONTENT | DESTROY_CONTENT_ON_REMOVAL | TRUSTED | OWN_DISPLAY_GROUP | ALWAYS_UNLOCKED | TOUCH_FEEDBACK_DISABLED | OWN_FOCUS | DEVICE_DISPLAY_GROUP | STEAL_TOP_FOCUS_DISABLED`; never `SHOULD_SHOW_SYSTEM_DECORATIONS`; IME policy `HIDE` (2).
- Never capture, read or inject into display 0. Every RPC that takes a `displayId` rejects 0 and any display the server did not create.
- Never swap the system IME, never use global BACK/HOME/accessibility global actions.
- Sample app: package `dev.headroid.sample`, Kotlin, every control has a resource-id and a content description.
- Commits: `git commit -s`, message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; push to `main`.
- The owner's phone is touched only in sessions with the owner. Unattended runs use emulators only, always with `adb -s emulator-NNNN`.
- Governor defaults: pause above thermal status MODERATE (2); stop below 15 % battery when not charging.
- Video: opt-in only, H.264, default 720p at 10 fps; no encoder runs when nobody records.

## Review Focus

1. **Host disappears mid-session** (Wi-Fi drop, `kill -9` of the host): displays must not leak and no activity may move to display 0. Expect: after the grace period the server stops launched packages and releases displays with `DESTROY_CONTENT_ON_REMOVAL`. Pinned by `WatchdogTest.teardownRunsAfterGrace` and `WatchdogTest.reconnectCancelsTeardown` (Task 1.6).
2. **Non-ASCII text** (`"héllo 😀"`, Hindi, CJK) in `input.text`: `KeyCharacterMap` returns null for these. Expect: falls back to setting text on the focused editable node of that display; error `-32010` "no focused editable" if none. Pinned by `TextPlannerTest.nonAsciiUsesSetText` (Task 1.4).
3. **A request naming display 0 or a foreign display**: expect `-32602` "display not owned by headroid", nothing injected or captured. Pinned by `DisplayRegistryTest.rejectsDisplayZeroAndUnknown` (Task 1.3).
4. **Malformed or partial JSON lines, huge lines, unknown methods, batch arrays**: expect JSON-RPC errors (`-32700`, `-32600`, `-32601`), connection stays open. Pinned by `RpcDispatcherTest` (Task 1.2).
5. **Screenshot before the first frame / static screen**: `ImageReader` gets no new frame on a static screen. Expect: the last frame is kept and returned; before any frame, error `-32011` "no frame yet" (host retries). Pinned by `FrameStoreTest` (Task 1.5).

---

## Wire protocol v1 (shared by Tasks 1.x and 2.x)

- Transport: `localabstract:headroid` (name overridable with server arg `socket=<name>`), host side `adb forward tcp:0 localabstract:headroid`.
- Framing: one JSON object per line, UTF-8, `\n` terminated, max line 16 MiB. JSON-RPC 2.0 (`{"jsonrpc":"2.0","id":N,"method":"...","params":{...}}`). Notifications from server: `{"jsonrpc":"2.0","method":"event","params":{"type":...}}`.
- Binary payloads (screenshots) are base64 in `result.data` for v1; a separate binary frame channel comes with video (Task 1.10).
- Error codes: `-32700` parse error, `-32600` invalid request, `-32601` method not found, `-32602` invalid params, `-32000` internal error, `-32010` no focused editable, `-32011` no frame yet, `-32012` UiAutomation unavailable, `-32013` paused by governor.

| Method | Params | Result |
|---|---|---|
| `server.info` | – | `{protocol:1, version, sdk, release, manufacturer, model, uid, capabilities:{...}}` |
| `server.shutdown` | – | `{}` (tears down, then exits) |
| `display.create` | `width, height, dpi` | `{displayId, width, height, dpi, flags}` |
| `display.list` | – | `{displays:[{displayId,width,height,dpi}]}` |
| `display.release` | `displayId` | `{}` |
| `display.screenshot` | `displayId, format:"png"\|"jpeg"="png", quality=80, maxSize=0` | `{width, height, format, data}` |
| `app.launch` | `displayId, package, activity?=null, forceStop?=false` | `{}` |
| `app.stop` | `package` | `{}` |
| `input.tap` | `displayId, x, y` | `{}` |
| `input.longPress` | `displayId, x, y, durationMs=600` | `{}` |
| `input.swipe` | `displayId, x1, y1, x2, y2, durationMs=300` | `{}` |
| `input.key` | `displayId, keyCode, metaState=0` | `{}` |
| `input.text` | `displayId, text` | `{method:"keys"\|"setText"}` |
| `ui.tree` | `displayId` | `{displayId, nodes:[Node]}` |

`Node = {id, cls, pkg, text, desc, rid, bounds:[l,t,r,b], clickable, longClickable, enabled, focused, focusable, scrollable, checkable, checked, editable, selected, visible, children:[Node]}`; `id` is the index path from the window root (`"0.2.1"`, window index first), stable within one observation.

---

## Stage S: headroid sample app (design §6.7)

### Task S.1: Sample app skeleton, home screen and CI

**Files:**
- Create: `sample-app/settings.gradle.kts`, `sample-app/build.gradle.kts`, `sample-app/gradle.properties`, `sample-app/gradlew`, `sample-app/gradlew.bat`, `sample-app/gradle/wrapper/*` (Gradle 8.10.2), `sample-app/app/build.gradle.kts`, `sample-app/app/src/main/AndroidManifest.xml`, `sample-app/app/src/main/java/dev/headroid/sample/MainActivity.kt`, `sample-app/README.md`
- Create: `.github/workflows/sample-app.yml`

- [ ] Step 1: AGP 8.7.3, Kotlin 2.0.21, `compileSdk 35`, `targetSdk 35`, `minSdk 26`, `applicationId dev.headroid.sample`, versionName `0.1.0`; framework widgets only (no AndroidX), layouts built in code or XML with ids.
- [ ] Step 2: `MainActivity` lists one button per screen (`@+id/nav_<screen>`), each with a content description.
- [ ] Step 3: Build: `./gradlew :app:assembleDebug` with `JAVA_HOME` = JDK 17. Expected: `app/build/outputs/apk/debug/app-debug.apk`.
- [ ] Step 4: Workflow on push / PR touching `sample-app/**` and `workflow_dispatch`: Temurin 17, `android-actions/setup-android@v3`, `./gradlew :app:assembleDebug :app:lintDebug`, upload `headroid-sample-debug` artifact; on tags `v*` attach the APK to the release.
- [ ] Step 5: Commit, push, `gh run watch` until green, `gh run view --json` shows the artifact.

### Task S.2: Screens

**Files:** one Activity per screen in `sample-app/app/src/main/java/dev/headroid/sample/`.

| Screen (Activity) | Controls (resource-ids) | Behaviour |
|---|---|---|
| `LoginActivity` | `login_email`, `login_password`, `login_submit`, `login_error` | `demo@headroid.dev` / `headroid` succeeds → `FormActivity`; otherwise `login_error` shows "Invalid email or password" |
| `FormActivity` | `form_name`, `form_phone` (phone input), `form_notes` (multi-line), `form_newsletter` (checkbox), `form_plan` (radio group `plan_free`/`plan_pro`), `form_submit`, `form_result` | Submit shows "Saved: <name>" in `form_result` |
| `ListActivity` | `list_items` (ListView of `Item 1`…`Item 200`), `list_selected` | Tap sets "Selected: Item N" |
| `CheckoutActivity` | `checkout_step` text "Step k of 3", `checkout_next`, `checkout_back`, step views `checkout_cart`, `checkout_address` (`checkout_address_input`), `checkout_pay`, `checkout_done` "Order placed" | Three steps then confirmation; Next disabled on step 2 until address non-empty |
| `EffectsActivity` | `effects_sound` (ToneGenerator beep 300 ms), `effects_vibrate` (300 ms), `effects_toast` ("Hello from headroid"), `effects_dialog` (AlertDialog "Sample dialog" OK/Cancel → `effects_dialog_result`), `effects_notification` (channel `sample`, POST_NOTIFICATIONS requested on 33+), `effects_permission` (requests CAMERA, result in `effects_permission_result`) | Each logs `HeadroidSample: <event>` to logcat |
| `CrashActivity` | `crash_now` (throws `IllegalStateException("headroid sample crash")`), `anr_now` (sleeps 20 s on main thread) | – |
| `SecureActivity` | `secure_text` | `FLAG_SECURE` set in `onCreate` |
| `TimerActivity` | `timer_value` (seconds since start, updated every 1 s via Handler), `timer_started_at` | Survives screen off; logs a line every 10 s |

- [ ] Step 1: Implement screens; manifest declares VIBRATE, POST_NOTIFICATIONS, CAMERA.
- [ ] Step 2: Local build + lint pass; Actions green; commit.

---

## Stage M1: Device server (design §6.1)

Layout: `device-server/` is the forked Gradle project (root `build.gradle`, `settings.gradle`, `gradle/`, `config/`, module `server/`). Upstream code stays in `com.genymobile.scrcpy` (kept intact so `--new-display` mirroring still works for debugging, stripping is Task 1.11). headroid code lives in `server/src/main/java/dev/headroid/server/`, tests in `server/src/test/java/dev/headroid/server/`. Entry point `dev.headroid.server.HeadroidServer`; started with
`CLASSPATH=/data/local/tmp/headroid-server.jar app_process / dev.headroid.server.HeadroidServer [socket=headroid] [grace_ms=15000] [log=info]`.

### Task 1.1: Fork and build

**Files:** copy `C:\hd\scrcpy` (v4.1 + patch 0001) `build.gradle`, `settings.gradle`, `gradle.properties`, `gradlew*`, `gradle/`, `config/`, `server/` into `device-server/`; modify `server/build.gradle` (`applicationId "dev.headroid.server"`, `minSdkVersion 29`, versionName `0.1.0`); `device-server/README.md`; `NOTICE`; `.github/workflows/device-server.yml`.

- [ ] Step 1: Copy; remove `patches/` (now applied in tree; README records it); upstream `LICENSE` copied to `device-server/LICENSE-scrcpy`.
- [ ] Step 2: `./gradlew :server:assembleRelease :server:testDebugUnitTest` passes locally.
- [ ] Step 3: Workflow builds, runs unit tests, uploads `headroid-server` artifact (the release APK renamed `headroid-server.jar`).
- [ ] Step 4: Commit.

### Task 1.2: JSON codec and RPC dispatcher

**Files:** Create `dev/headroid/server/rpc/Json.java`, `RpcDispatcher.java`, `RpcException.java`, `Params.java`, `RpcMethod.java`; tests `JsonTest`, `RpcDispatcherTest`, `ParamsTest`.

**Interfaces — Produces:**
- `Json.parse(String) -> Object` (Map<String,Object> as LinkedHashMap, List<Object>, String, Long, Double, Boolean, null); `Json.write(Object) -> String` (also accepts int/float/arrays of primitives, `byte[]` is not accepted).
- `interface RpcMethod { Object call(Params p) throws Exception; }`
- `RpcException(int code, String message)`; constants `PARSE_ERROR=-32700, INVALID_REQUEST=-32600, METHOD_NOT_FOUND=-32601, INVALID_PARAMS=-32602, INTERNAL=-32000, NO_FOCUSED_EDITABLE=-32010, NO_FRAME=-32011, UIA_UNAVAILABLE=-32012, PAUSED=-32013`.
- `Params.getInt(name)`, `optInt(name, def)`, `getString`, `optString`, `optBool`, `getDouble`; missing/wrong type → `RpcException(INVALID_PARAMS, "<name>: ...")`.
- `RpcDispatcher.register(String, RpcMethod)`; `String handleLine(String line)` returns the response line or `null` for notifications.

- [ ] Tests: `JsonTest.roundTripsNestedValues`, `parsesEscapesAndUnicode` (`"\u00e9\ud83d\ude00"`), `rejectsTrailingGarbage`, `writesNonFiniteAsNull`; `RpcDispatcherTest.parseErrorKeepsConnection` (→ `-32700`, `id:null`), `missingMethodIsInvalidRequest`, `unknownMethod` (`-32601`), `batchArrayRejected` (`-32600`), `paramsErrorsAreInvalidParams`, `exceptionBecomesInternal`, `notificationReturnsNull`.
- [ ] Implement, run `:server:testDebugUnitTest`, commit.

### Task 1.3: Hidden displays

**Files:** `dev/headroid/server/display/DisplayFlags.java`, `HiddenDisplay.java`, `DisplayRegistry.java`, `FrameStore.java`; tests `DisplayFlagsTest`, `DisplayRegistryTest`.

**Interfaces — Produces:**
- `DisplayFlags.forSdk(int sdk) -> int` (Global Constraints set on 34+; without OWN_FOCUS / DEVICE_DISPLAY_GROUP / STEAL_TOP_FOCUS_DISABLED on 33; only the first six on 29–32).
- `HiddenDisplay.create(int w, int h, int dpi) -> HiddenDisplay` (ImageReader RGBA_8888, 3 images, own `HandlerThread`, `ServiceManager.getDisplayManager().createNewVirtualDisplay("headroid", ...)`, IME policy HIDE); `int id()`, `FrameStore frames()`, `void release()`.
- `DisplayRegistry.add(HiddenDisplay)`, `HiddenDisplay require(int displayId)` (throws `INVALID_PARAMS` "display not owned by headroid" for 0 / unknown), `remove(int)`, `List<HiddenDisplay> all()`, `void releaseAll()`. Registry is written against `interface ManagedDisplay { int id(); void release(); }` so tests use fakes.
- Methods `display.create`, `display.list`, `display.release`.

- [ ] Tests: `DisplayFlagsTest.api34HasStealTopFocusDisabled` (`(flags & (1<<16)) != 0`, `(flags & (1<<9)) == 0`, `(flags & (1<<8)) != 0`), `api33HasNoOwnFocus`, `api30Minimal`; `DisplayRegistryTest.rejectsDisplayZeroAndUnknown`, `releaseAllReleasesEach`.
- [ ] Implement, test, commit.

### Task 1.4: In-process input per display

**Files:** `dev/headroid/server/input/InputInjector.java`, `TextPlanner.java`, `Gestures.java`; tests `GesturesTest`, `TextPlannerTest`.

**Interfaces — Produces:**
- `Gestures.swipePoints(x1,y1,x2,y2,durationMs, stepMs=16) -> List<long[]{t,x,y}>` (first point at t=0, last at t=durationMs, ≥2 points).
- `TextPlanner.plan(String text, Function<char[], KeyEvent[]> keyMap) -> Plan{boolean useSetText; KeyEvent[] events}`; `useSetText` when keyMap returns null for the text.
- `InputInjector(int displayId)`: `tap(x,y)`, `longPress(x,y,ms)`, `swipe(...)`, `key(code, meta)`, `text(String) -> "keys"|"setText"`; MotionEvents with `SOURCE_TOUCHSCREEN`, `InputManager.setDisplayId`, injected with `INJECT_INPUT_EVENT_MODE_WAIT_FOR_RESULT` for DOWN/UP and `ASYNC` for MOVE.
- Methods `input.tap`, `input.longPress`, `input.swipe`, `input.key`, `input.text`.

- [ ] Tests: `GesturesTest.endpointsAndMonotonicTime`, `zeroDurationStillTwoPoints`; `TextPlannerTest.asciiUsesKeys`, `nonAsciiUsesSetText`.
- [ ] Implement, test, commit.

### Task 1.5: Screenshots

**Files:** `FrameStore.java` (from 1.3), `dev/headroid/server/display/ScreenshotEncoder.java`; test `FrameStoreTest`.

- [ ] `FrameStore<T>` keeps the latest frame, closes the previous (`Consumer<T> closer`), `withLatest(Function<T,R>)` throws `RpcException(NO_FRAME)` before the first frame. Tests: `FrameStoreTest.closesPreviousFrame`, `noFrameYet`, `keepsLastFrameWhenIdle`.
- [ ] `ScreenshotEncoder.encode(Image, format, quality, maxSize)` copies the plane honouring `rowStride`, scales the longest side to `maxSize` if `> 0`, compresses to PNG/JPEG, base64.
- [ ] Method `display.screenshot`; commit.

### Task 1.6: Session, watchdog, teardown, apps

**Files:** `dev/headroid/server/HeadroidServer.java`, `Session.java`, `Watchdog.java`, `apps/AppLauncher.java`; test `WatchdogTest`.

**Interfaces — Produces:**
- `Watchdog(ScheduledExecutorService, long graceMs, Runnable teardown)`: `onDisconnect()` schedules teardown after `graceMs`; `onConnect()` cancels a pending one. Tests with a fake scheduler: `teardownRunsAfterGrace`, `reconnectCancelsTeardown`, `teardownRunsOnce`.
- Teardown order: force-stop every package launched on headroid displays → release every display (DESTROY_CONTENT_ON_REMOVAL) → disconnect UiAutomation → restore app-ops (Task 1.8).
- `AppLauncher.launch(displayId, pkg, activity, forceStop)` uses `ActivityOptions.setLaunchDisplayId`, `FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_MULTIPLE_TASK`.
- Server: `LocalServerSocket(name)`, one client at a time, reader loop → `RpcDispatcher`, writes under a lock; `server.info`, `server.shutdown`; `Looper.loop()` on main; shutdown hook runs teardown.
- [ ] Implement, test, commit.

### Task 1.7: UI tree per display

**Files:** `dev/headroid/server/ui/UiAutomationHost.java`, `TreeBuilder.java`, `NodeView.java`; test `TreeBuilderTest`.

**Interfaces — Produces:**
- `interface NodeView { String cls(); ... int childCount(); NodeView child(int i); Rect bounds(); boolean visible(); ... }` with an `AccessibilityNodeInfo` adapter.
- `TreeBuilder.build(List<NodeView> windowRoots, int maxDepth=80) -> List<Map<String,Object>>` (Node per wire protocol; skips null children; ids `"w.i.j"`).
- `UiAutomationHost.get()` lazily constructs `UiAutomation` by reflection (`(Looper, IUiAutomationConnection)` then `(Context, IUiAutomationConnection)`), `connect(FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES)`, sets `FLAG_RETRIEVE_INTERACTIVE_WINDOWS | FLAG_REPORT_VIEW_IDS | FLAG_INCLUDE_NOT_IMPORTANT_VIEWS`; `windowsOn(displayId)` via `getWindowsOnAllDisplays()`; `findFocusedEditable(displayId)`; `disconnect()`. Failure → `RpcException(UIA_UNAVAILABLE)`.
- Method `ui.tree`; `input.text` setText path uses `findFocusedEditable` + `ACTION_SET_TEXT`.
- [ ] Tests: `TreeBuilderTest.idsAreIndexPaths`, `boundsAndFlagsSerialized`, `depthLimited`, `nullChildSkipped`. Implement, commit.

### Task 1.8: Isolation guard
- Focus check: poll `mTopFocusedDisplayId` via `IWindowManager` reflection only on actions (no periodic dumpsys); event `focus.stolen` if not 0 after an action, then re-focus display 0 by no-op? Report only in v1.
- Mute: `appops set <pkg> PLAY_AUDIO ignore`, `VIBRATE ignore`, `TOAST_WINDOW ignore` through `IAppOpsService.setMode` reflection, remembered and restored on teardown. Tests on the remember/restore bookkeeping (`AppOpsLedgerTest.restoresOriginalModes`).
- Leak watch: `IDisplayWindowListener` / task stack listener for tasks of the package under test appearing on display 0 → move back with `IActivityTaskManager.moveRootTaskToDisplay` if available, else event `leak.display0`.

### Task 1.9: Resource governor
- `Governor` reads `PowerManager.getCurrentThermalStatus()`, battery via sticky `ACTION_BATTERY_CHANGED`; policy pure class `GovernorPolicy.decide(thermal, batteryPct, charging) -> RUN|PAUSE|STOP` (tests at thresholds 2 and 15 %); actions return `-32013` while paused; event `governor.state`.

### Task 1.10: Video recording (opt-in)
- Reuse scrcpy `SurfaceEncoder` path on a second socket `headroid_video`, started by `video.start {displayId, maxSize=1280, fps=10, bitRate=2000000}` / `video.stop`; ImageReader stays the screenshot source (encoder gets its own surface through an `OpenGLRunner` split or a second VirtualDisplay surface swap — decide after measuring).

### Task 1.11: Strip and harden
- Remove scrcpy audio, camera, UHID, clipboard paths not used by headroid; keep wrappers. Effect checks: `input.*` accept `verify:true` → returns `{changed:bool}` from frame hash before/after (300 ms settle).

### Task 1.12: Keyboard-lag root cause (owner session)
- Measure owner `dumpsys gfxinfo <owner pkg> framestats` jank and p95 with: nothing, server idle, server + actions every 1 s, + screenshots every 1 s, + `ui.tree` every 1 s. Record in `docs/m1/RESULTS.md`.

**M1 done when** (design §7): sample app driven on a hidden display over Wi-Fi for 60 min, screen on and off, owner using music and reels with no felt lag; measured frame times and battery; clean teardown after `kill -9` of host and server.

---

## Stage M2: SDK and CLI (design §6.2)

### Task 2.1: Host skeleton (`packages/headroid`)

**Files:** `packages/headroid/pyproject.toml` (hatchling, `requires-python >=3.11`, no runtime deps), `src/headroid/__init__.py`, `adb.py`, `rpc.py`, `server.py`, `device.py`, `cli.py`; tests `tests/test_rpc.py`, `tests/test_adb.py`, `tests/test_device.py`.

**Interfaces — Produces:**
- `Adb(serial: str | None, adb_path="adb")`: `run(*args, timeout=30) -> str`, `shell(cmd) -> str`, `push(local, remote)`, `forward(remote="localabstract:headroid") -> int` (parses `adb forward tcp:0 ...` port), `remove_forward(port)`, `popen_shell(cmd) -> subprocess.Popen`. Refuses to run when `serial` is None and more than one device is attached.
- `RpcClient(host, port, timeout=30)`: `call(method, **params) -> dict`, raises `RpcError(code, message)`; `close()`; events collected in `client.events`.
- `ServerProcess(adb, jar_path, socket="headroid")`: `start() -> RpcClient` (push to `/data/local/tmp/headroid-server.jar`, start `app_process` with `popen_shell`, forward, retry connect for 10 s), `stop()`.
- `Device.connect(serial=None, jar=None) -> Device`; `info()`, `create_display(width=720, height=1600, dpi=320) -> Display`, `close()`.
- `Display`: `id`, `launch(package, activity=None)`, `tap(x,y)`, `long_press`, `swipe`, `key(code)`, `type(text)`, `screenshot(path=None, format="png") -> bytes`, `tree() -> list[dict]`, `find(text=None, rid=None, desc=None) -> dict|None`, `release()`.
- CLI `headroid info|screenshot|tree` (argparse) for smoke tests.
- [ ] Tests use a fake JSON-RPC server thread on `127.0.0.1` and a fake adb (`subprocess.run` patched): `test_call_roundtrip`, `test_error_raises_rpcerror`, `test_forward_parses_port`, `test_refuses_ambiguous_device`, `test_find_by_rid`.
- [ ] `python -m pytest packages/headroid` passes; commit.

### Tasks 2.2–2.6 (outline)
- 2.2 Async API (`asyncio` client, sync wrapper), `Page` (one display + one app), `wait_for_idle` (frame hash stable 500 ms).
- 2.3 `Locator` (text, rid, RN `testID` → rid, desc, role, XPath over the tree converted to uiautomator XML, image), auto-wait visible+stable, `expect(locator).to_have_text()`.
- 2.4 `headroid pair` / `connect`: `adb pair`, mDNS (`adb mdns services`), reconnect with back-off when IP/port changes; server reconnects within the watchdog grace period keep the display.
- 2.5 `headroid doctor`: probes from design §6.5, output table + JSON device report.
- 2.6 Packaging: server jar bundled as package data; PyPI build in CI.

**M2 done when** a Python script completes the sample app's login and form flows with locators (resource-id, text, and `testID` on the React Native sample, which is created in 2.3).

## Stage M3: Agents (design §6.4)
- 3.1 `headroid mcp` (MCP Python SDK): tools `open_app`, `observe`, `tap`, `type`, `swipe`, `press`, `assert_visible`, `record`, `report_bug`, `close`.
- 3.2 `integrations/artemis`: `HeadroidDriver(BaseDeviceDriver)` against the owner's fork at a pinned commit; factory hook.
- 3.3 `integrations/mobile-use`: controller.
- 3.4 Exploratory mode: time-boxed agent run producing a bug report (steps, screenshots, video).
- **Done when** ARTEMIS Flash, Pro and Claude Code via MCP each complete the sample checkout flow on the hidden display.

## Stage M4: Test runner (design §6.3)
- 4.1 pytest plugin `headroid.test`: fixtures `device`, `page`, `app`; `expect` with auto-wait; retries.
- 4.2 Traces (actions, before/after screenshots, trees, app logcat), crash/ANR detection (sample `crash_now`, `anr_now` are the fixtures), video.
- 4.3 HTML report + console summary + optional desktop notification.
- 4.4 Parallel pages on several displays of one phone and across phones.
- **Done when** the sample suite runs in parallel on 2 hidden displays with an HTML report.

## Stage M5: Frameworks and devices (design §6.5, §6.6)
- 5.1 React Native sample (same screens, `testID`s) if not already done in 2.3; Flutter sample with semantics labels; Compose test tags.
- 5.2 Capability matrix from `doctor` reports; ≥3 OEMs.

## Launch
- Docs site, PyPI release, demo video, LinkedIn post; README quick start verified on a clean PC.

## Cross-cutting
- CI: sample app, device server (build + unit tests), host (pytest + ruff), NOTICE check.
- Emulator lane (Android 14/15/16 AVDs) for the device-server API surface (`display.create` → `app.launch dev.headroid.sample` → `input.tap` → `ui.tree` contains `nav_login`).
