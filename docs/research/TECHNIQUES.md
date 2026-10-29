# headroid: TECHNIQUES (clean-room "reader" document)

Date: 2026-10-29. Author role: reader. Audience: a separate implementer who has NOT read the source repos.

## 0. Clean-room status and how to use this file

| Project | Licence | What this file contains about it |
|---|---|---|
| kmod-midori/Mua | none | Behaviour and approach in my own words only. No code, no identifiers, no tool names, no structure. |
| QY-25123/PhoneAgent | none | Same. (Its docs are descriptive; I paraphrased findings and numbers, not text.) |
| lejw0925/android-virtual-screen (AVS) | PolyForm Noncommercial | Same. Learn from it, copy nothing. |
| imoonkey/closepaw | Apache-2.0 | Described more closely; file paths given. Reusable with attribution (NOTICE + licence header rules apply). |
| iamr0s/Ruto-GLM | Apache-2.0 | Same as closepaw. |
| Genymobile/scrcpy | Apache-2.0 | Same; paths are under `server/src/main/java/com/genymobile/scrcpy/`. |

What I allow myself to state as FACTS (public AOSP): API names, flag values, permissions, `dumpsys`/`am`/`cmd`/`settings`/`input` shell commands, `Settings.Secure` keys, error strings that the platform itself emits. Everything else about Mua / PhoneAgent / AVS is behaviour.

Implementer rule: write headroid from this document plus AOSP / scrcpy / closepaw / Ruto sources. Do not open Mua, PhoneAgent or AVS while implementing. If something here is ambiguous, ask the reader to clarify; do not go to the source.

Confidence tags used below: [V] = the project's own docs/tests claim it was verified on a device/emulator; [R] = I read it in code but no verification claim; [I] = from issue tracker or discussion, unverified by maintainers.

---

## 1. Shared background facts (AOSP-level, used by every project)

### 1.1 VirtualDisplay flag values (hidden ones are `@hide` or `@SystemApi`; create via reflection)

| Flag | Value | Notes |
|---|---|---|
| PUBLIC | 1<<0 | Other apps may show on it. |
| PRESENTATION | 1<<1 | Presentation API (scrcpy sets it). |
| SECURE | 1<<2 | Public API flag. Meant to allow secure (FLAG_SECURE) content; normally needs the owner to hold a secure-capable projection. See open question Q9. |
| OWN_CONTENT_ONLY | 1<<3 | Do not mirror the default display. Essential. |
| AUTO_MIRROR | 1<<4 | Do not use. |
| SUPPORTS_TOUCH | 1<<6 | Hidden. |
| ROTATES_WITH_CONTENT | 1<<7 | Hidden. |
| DESTROY_CONTENT_ON_REMOVAL | 1<<8 | Hidden. On release, apps are destroyed instead of moved to the main display. |
| SHOULD_SHOW_SYSTEM_DECORATIONS | 1<<9 | Hidden. Gives the display a launcher/system UI (some ROMs render it broken). |
| TRUSTED | 1<<10 | Hidden, API 33+. Needs ADD_TRUSTED_DISPLAY (shell has it, with caveats in 1.3). |
| OWN_DISPLAY_GROUP | 1<<11 | Hidden, API 33+. |
| ALWAYS_UNLOCKED | 1<<12 | Hidden, API 33+. Needs ADD_ALWAYS_UNLOCKED_DISPLAY. Display stays usable while the phone is locked/screen off. |
| TOUCH_FEEDBACK_DISABLED | 1<<13 | Hidden, API 33+. |
| OWN_FOCUS | 1<<14 | Hidden, API 34+. Display has its own focused window. Does NOT stop the display becoming "top focused display". |
| DEVICE_DISPLAY_GROUP | 1<<15 | Hidden, API 34+. |
| STEAL_TOP_FOCUS_DISABLED | 1<<16 | Hidden, API 34+. Honoured only together with OWN_FOCUS + TRUSTED (per our earlier AOSP read). Stops activity starts/taps on this display from moving "top focused display" away from the phone's own display. |

### 1.2 Calling convention to create the display as shell (uid 2000)
- Build a `DisplayManager` through its hidden one-arg `Context` constructor, passing a context that claims package `com.android.shell` (all three Apache projects and all three unlicensed ones do this). DisplayManagerService checks that the declared package matches the calling uid.
- The system context for a bare `app_process` is obtained by constructing a fake `ActivityThread` and marking it as a system thread (scrcpy `Workarounds.java`, `FakeContext.java` describe this; Samsung needs a non-null `ConfigurationController`, Onyx devices break if app-info filling is done; see scrcpy issues #4467, #5182).
- Alternative used by closepaw: talk to the `IDisplayManager` binder directly (obtained through Shizuku's binder wrapper), pass a `VirtualDisplayConfig` (API 33+) or the older multi-arg signature (API 31/32, two variants exist), keep the `IVirtualDisplayCallback` token per display (needed later for set-surface / release), and try package-name candidates in order (`com.android.shell`, null, Shizuku's package) because the server rejects a mismatch with "packageName must match the calling uid".
- Standalone `app_process` on very new Android (17 in AVS notes) needs the in-process `ApplicationSharedMemory` singleton created manually before touching window/keyguard services [R].

### 1.3 What shell can and cannot do (permission picture)
- Android 13/14: shell holds ADD_TRUSTED_DISPLAY, ADD_ALWAYS_UNLOCKED_DISPLAY, ADD_MIRROR_DISPLAY; trusted virtual displays work [V, scrcpy].
- Android 15 QPR2 beta and the March-2025 Pixel stable update removed those three from the Shell package; creation fails with a SecurityException "Requires ADD_TRUSTED_DISPLAY permission ..." (scrcpy #5523, still open; Google issue 384752747 answered "permissions added back for Android 16"; a poster confirmed it working on 16 beta 3). Dropping the flags is not a fix: on a Pixel 8 the app then starts on the phone screen instead of the virtual display.
- Android 10-12: no trusted display for shell; apps launched with a display option may still land on the phone display [from SUMMARY.md and Ruto issue below].

### 1.4 The main shell-level interactions
- Launch: `ActivityOptions.setLaunchDisplayId(id)` (API 26+) + `Intent.FLAG_ACTIVITY_NEW_TASK`, started through `IActivityManager.startActivityAsUser` as package `com.android.shell`, user CURRENT; or `am start --display <id> -n <component>`.
- Input: `InputEvent.setDisplayId(int)` (hidden) then `InputManager.injectInputEvent(event, mode)` where mode 0 = async, 1 = wait for result, 2 = wait for finish; or shell `input -d <id> tap|swipe|keyevent|text ...`.
- Remove all tasks on a display: `IActivityTaskManager.getAllRootTaskInfosOnDisplay(id)` then `removeTask(taskId)`.
- Per-display IME policy: `IWindowManager.setDisplayImePolicy(displayId, policy)`; 0 = LOCAL, 1 = FALLBACK_DISPLAY (default: IME shows on the default display), 2 = HIDE. Android 11 and lower use a boolean `setShouldShowIme` variant (scrcpy `wrappers/WindowManager.java`).
- Per-display accessibility: API 30+ `AccessibilityService.getWindowsOnAllDisplays()` (needs `flagRetrieveInteractiveWindows`); also usable from a `UiAutomation` created in a shell process.

---

## 2. Mua (kmod-midori/Mua) — no licence, ideas only

Shape: an Android app that, through Shizuku, runs a privileged helper in a separate process; the app exposes an MCP server on the phone (loopback or LAN, bearer token, optional relay server that multiplexes several phones). Minimum Android 12 (API 31).

### 2.1 Display creation
- Always creates an additional display with exactly the main display's current pixel size and DPI (no size parameters exposed to the agent). Size is fixed for the display's lifetime.
- Flags: public, presentation, own-content-only, supports-touch, rotates-with-content, destroy-content-on-removal, should-show-system-decorations; plus on 13+: trusted, own-display-group, always-unlocked, touch-feedback-disabled; plus on 14+: own-focus, device-display-group. It does NOT set STEAL_TOP_FOCUS_DISABLED.
- Immediately after creation it sets the display IME policy to HIDE (try/catch; logs on failure).
- Frame sink: an `ImageReader` (RGBA_8888, four buffers, usage flags GPU-sampled + CPU-read-often) created in the host app; its Surface is handed across Binder to the privileged process, which passes it to the display. The reader's surface is owned by the app, so pixels never cross Binder as bitmaps. [R]
- Registry of displays kept in the privileged process; stale (invalid) entries are pruned whenever the list is requested; the app side reconciles its capture objects against that list before every operation.

### 2.2 Launching apps
- Explicit launcher intent for the package, NEW_TASK, launch-display option, started as the shell package.
- Guard (before and after launch): query running tasks fresh from the system every time (no local registry). If another display currently has the SAME app's task focused and in front, refuse with an error rather than stealing the owner's app. An existing task of that package on the target display is reused (launch into that task id); otherwise a new task is forced with the multiple-task flag.
- Extra tools: list recent tasks (task id, label, display, running flag, base/top activity) and "move recent task to a virtual display" via `startActivityFromRecents` with a launch-display option, with a rollback that tries to restore the task to its original display if the move fails or leaves a conflict. Only moves to virtual-type displays are allowed.
- Notification content-intents and actions are fired with a launch-display option and, on 14+/36+, the PendingIntent background-activity-start mode relaxed, so an agent can open an app "via notification" onto the virtual display.

### 2.3 Input injection and target display
- Tap: DOWN then UP as touchscreen-source MotionEvents with `setDisplayId`, injected in "wait for finish" mode, with a short randomised hold (~0.2 s). Double tap = two taps ~130 ms apart. Long press = a stationary swipe of ~1 s.
- Swipe and key use the shell `input -d <id>` command (a subprocess per call, 30 s timeout) rather than synthesising events. [R]
- Every operation first verifies the display still exists.
- Text: not through an IME. An in-app accessibility service finds the input-focused node inside the windows of the chosen display (`getWindowsOnAllDisplays`) and sets its text (replace-all semantics). This works while the phone is locked. A separate "what field is focused" query returns bounds and flags (editable, password, supports set-text) but NOT the field's content.
- Clipboard get/set through the privileged process, write verified by a unique label marker read back.
- The accessibility service and notification-listener service are switched on without any user UI: the privileged process edits the enabled-accessibility-services secure setting (merging, not overwriting) and runs the `cmd notification allow_listener` command; access is lease-based and revoked automatically if the owning app process dies (Binder death) or the helper is destroyed.

### 2.4 Focus / IME / back key
- Only defence for the keyboard: IME policy HIDE on the virtual display. There is no top-focus protection in code. Back and Home go through the display-targeted key path (`input -d`), never a global action.
- Display-less tools are prohibited; every tool takes an explicit display id, including main display 0 (the agent is allowed to drive the phone's own screen too).

### 2.5 Frame capture
- Keeps only the latest frame (acquire-latest; closes the previous image). Bitmaps are produced on demand: handle row-stride padding (stride / pixel stride is wider than the display) and crop rect. Screenshot returned as PNG scaled so the longest side is at most 1980 px (never upscaled); coordinates remain native.
- "No frame yet" is a normal state: tool tells the caller to retry shortly (a display with a static/black screen emits no frames).
- Preview thumbnails (<= 480 px edge) are sampled directly from the buffer at <= 5 Hz, cached per frame version, and shared immutable.
- All device operations and capture cleanup are serialised on one queue.

### 2.6 UI tree
- Only the narrow "focused field" query above. No full tree dump tool; the agent works from screenshots. (Design is vision-first.)

### 2.7 Tools exposed to the agent (own words; ~25)
Display: create, list (with each display's focused package), destroy. Apps: list launchable, search by label/package, launch on display, ask which package is focused on a display. Tasks: list recents, move a recent task onto a virtual display. Observe: screenshot. Input: tap, double tap, long press, swipe, key code, replace text in focused field, read focused field metadata. Clipboard: read, write+verify. Notifications: list, dismiss, open, trigger an action, reply via remote input.

### 2.8 Teardown, errors, power
- Destroy path: revoke accessibility/notification leases, release each display, then terminate the helper process.
- Holds a PARTIAL_WAKE_LOCK while any display exists, releases when the last one goes (and on Shizuku disconnect). Asks the owner to exempt the app from battery optimisation for long unplugged sessions; docs note Doze ignores wake locks and that the exemption does not extend to the apps running on the virtual display.
- On Shizuku loss, captures are dropped; displays must be recreated.
- Tool results say "request accepted"; launches/moves are not polled for confirmation.

### 2.9 Documented problems
- Same app cannot be in front on two displays; tool refuses.
- Some apps reject secondary displays; hidden APIs vary by device.
- Foreground service alone does not stop CPU suspend; OEM battery managers still kill it.
- No public issues (tracker empty).

---

## 3. PhoneAgent (QY-25123/PhoneAgent) — no licence, ideas only

Shape: an Android app that runs a Claude-driven agent entirely ON the phone via Shizuku; only AOSP emulator (Pixel 8, Android 14) verified. Its engineering docs are unusually thorough about focus/IME; this is the most valuable source for the "do not disturb the owner" problem.

### 3.1 Display creation
- Reflection-built `DisplayManager` with a fake `com.android.shell` context. The frame surface comes from an `ImageReader` (RGBA_8888, 2 images) owned by the app and passed over Binder to the privileged process.
- Flags: public, own-content-only, supports-touch, rotates-with-content, destroy-content-on-removal, trusted, own-display-group, always-unlocked, touch-feedback-disabled, own-focus, and optionally STEAL_TOP_FOCUS_DISABLED (read by reflection, falling back to the literal 1<<16). Deliberately omits presentation and system decorations (no status bar/nav bar).
- Display size is a parameter (e.g. 1080x2400 in their test).
- After creation it sets IME policy HIDE explicitly; the policy is cached by the display's unique id, so it must be re-applied for every new display even though it "sticks" after release.

### 3.2 Launching apps
- `am start --display <id> --activity-clear-task -n <component>` via a subprocess in the privileged process (activity-clear-task avoids re-using a task that lives on the main display). Component without a slash is treated as a package and resolved to its launcher activity with `cmd package resolve-activity`.
- Intent launches (calendar insert, map route link, etc.) are allowed through a narrow whitelist.
- Hand-off to the human: move the root task to the phone display (`moveRootTaskToDisplay`) and then set it focused (`setFocusedRootTask`), because moving alone did not always bring it in front of the app the owner is looking at.

### 3.3 Input injection
- `InputManager.injectInputEvent` by reflection; `InputEvent.setDisplayId` to target; async mode. Tap = DOWN, ~50 ms, UP. Swipe = DOWN, 15 interpolated MOVEs spread over the duration, UP. Source is touchscreen for touches and keyboard for keys (virtual keyboard device id).
- Back = a display-targeted key event. `performGlobalAction(BACK)` is forbidden by their rules: it acts on whichever display is top focused, which with the focus flag set is the phone, so it closed the owner's activity during testing [V].
- Text: connect a `UiAutomation` inside the privileged shell process by reflection: construct it with a looper from a SEPARATE handler thread (same thread self-deadlocks on connect), pass the flag that keeps user accessibility services running, then enable interactive-windows retrieval so non-default displays are visible. Find the focused input node (or first editable) in the display's windows and `ACTION_SET_TEXT`; bypasses the IME entirely so CJK text is fine [V]. A second variant sets text on the editable node at given coordinates (needed in Gmail compose where "focused" is unreliable), and a third is paste-based (write clipboard, select all, send paste key to that display) for apps whose tree is unreadable.
- Semantic actions: click deepest clickable node at point; click a node referenced by (window id, pre-order index, expected bounds) — bounds are re-verified so a changed UI returns false and the caller falls back to coordinates; click by visible text; scroll first scrollable node. Touch is used instead of semantic click for WebView content (semantic click is not always honoured there).

### 3.4 Focus / IME / back: the finding that matters
Their experiment table (rows = IME policy x touch vs semantic click) showed:
1. The root cause is "top focused display" moving to the virtual display whenever an activity starts or a window there gains focus (start command, tap, or even a click-induced navigation). Then the phone's window loses focus and the system collapses the owner's keyboard or hands the input connection to the app on the virtual display.
2. Policy FALLBACK_DISPLAY: input connection stolen (typing on the phone keyboard went into the virtual display's search box). Policy HIDE: connection kept but keyboard collapsed. Policy LOCAL: worse. OWN_FOCUS alone changes nothing about this.
3. Adding STEAL_TOP_FOCUS_DISABLED (with HIDE) fixed it: 6/6 scripted steps passed with the keyboard still showing, focused window and input client unchanged, `mTopFocusedDisplayId` = 0 throughout, and the owner's typing still reached the phone field; the control run without the flag failed [V, Android 14 emulator only]. `dumpsys display` shows the display with both flags listed.
4. Several attempts to push focus back after the fact (inject an orphan key-up with unknown keycode, set focused root task, move task to front, focus top task, move display to top) did not work reliably; abandoned.
5. Fallback if the flag is unavailable: "pause the agent while the phone's soft keyboard is visible" (checked via `dumpsys input_method`, field `mInputShown`), resume after the keyboard has been hidden ~2 s; default off; has a race window.
- Verification vocabulary worth reusing: `dumpsys input_method` fields for shown / current focused window / current client, and `dumpsys window` field for top focused display id.

### 3.5 Frame capture
- Reader with 2 images; always close each image; handle padded stride; no new frames while screen is static (do not treat as hang); throttle to 1 fps for the preview in the spike.
- Later design: when the owner opens a live view, repoint the display to a SurfaceView with `VirtualDisplay.setSurface` (60 fps in the emulator) and let the agent grab frames via PixelCopy (<= 10 fps); when no view is open, switch back to the ImageReader.

### 3.6 UI tree per display
- Snapshot of all windows on the chosen display returned as flat JSON (depth-first order, depth number, drawing order among siblings, "text is only a hint" flag, truncation flag if node cap hit). Window of a non-active display is readable and `ACTION_SET_TEXT`-able as long as interactive-window retrieval is on [V]. First read after connecting can come back empty; retry.
- Perception layer on top: numbered element list with stable ids, plus a "wait until stable" poll that compares successive tree signatures (identity, position, text, state; deliberately NOT pixel hashes because a blinking caret keeps pixels changing) and a longer retry budget for "shell" pages (empty tree, or WebView with few elements).
- Some apps (WeChat) expose an empty root in a virtual display; their fallback is screenshots with a 0-1000 grid overlay and coordinate taps.

### 3.7 Agent tools (own words)
Open app, tap element by number, tap at x/y, type into element, paste text (optionally after tapping a point), scroll in a direction (optionally a bottom-sheet drag), back, press enter, wait N seconds, ask the user a question with options, finish with success/failure and a result. Dispatch is "observe, decide one action, execute", with caps on steps / model calls / consecutive failures / unchanged screens.

### 3.8 Safety design worth borrowing as an idea
Irreversible actions (order, pay, subscribe, send) are blocked INSIDE the privileged process by pattern rules on control text/resource ids, with one-time (~2 min) release tokens bound to a hash of the content the user confirmed, so a misbehaving model cannot bypass them. headroid is a test framework, not a shopping agent, but a "destructive-action allowlist at the privileged layer" is a cheap safety net for pointing AI agents at real accounts.

### 3.9 Teardown and errors
- Stop order: cancel waiting actions, disconnect UiAutomation, REMOVE ALL TASKS ON THE VIRTUAL DISPLAY, release the display, give focus back to the phone, close the reader, stop the foreground service.
- Why: releasing a display that still hosts tasks left orphan tasks/windows; after several cycles the top focused display stuck on the destroyed display and every window on the phone lost focus until a reboot [V, reproduced]. After the cleanup fix, `dumpsys display` and `dumpsys activity` show only display 0 after repeated cycles. The same observation confirms closepaw's design.
- Old privileged process may survive an app reinstall; they bump the Shizuku user-service version to force restart. Foreground service type specialUse; the helper process uid is 2000.

### 3.10 Documented limits / unverified list
Same app cannot be used on both displays (explicit-component launch from the phone is absorbed by the virtual-display instance; action-style launch moves the whole task to the phone). Not verified: real phones/OEM ROMs, other Android versions, screen-off/locked behaviour, FLAG_SECURE content, WebView/custom-draw text fields, multiple displays or agents in parallel, UserService crash recovery, background limits.

---

## 4. android-virtual-screen, "AVS" (lejw0925) — PolyForm Noncommercial, ideas only

Shape: Android app with MCP server on the phone, root OR Shizuku/Stellar backend, shared "display engine" that runs in a privileged process; tested on a vivo (Android 16) and Xiaomi (Android 17, root) phones plus Android 14/15 emulators. Note: it says parts of its display engine were adapted from a third-party project, so avoid assuming its structure is original.

### 4.1 Display creation and policy
- One display at a time per session; request carries width/height/density/rotation/screen-off flag/idle timeout. Display id must be > 0; handle id is a random UUID checked on every call (stale handle = error).
- Flags: public, own-content-only, supports-touch, trusted, own-display-group, rotates-with-content, destroy-content-on-removal; on 14+: own-focus and STEAL_TOP_FOCUS_DISABLED (looked up reflectively, 0 if missing); always-unlocked only if the caller asked for screen-off operation. Notes that the older constructor overload also works on Android 13.
- Rotation: freeze the display's rotation via window-manager `freezeDisplayRotation` (two-argument and three-argument signatures differ between versions; try both); sync it with the top task's requested orientation.
- Screen-off mode: a display-specific FULL wake lock (hidden `newWakeLock` overload taking a display id) is renewed every ~30 s; never holds a wake lock on the phone's own display. Without the screen-off mode, operations fail with a "screen off/locked unavailable" error if the phone is not interactive or the keyguard is locked.
- Idle auto-release (default 20 min of no commands).

### 4.2 Launching apps
- Refuses if the component is not exported/enabled, is the controller app itself, or its activity resize mode is not resizeable ("does not support display").
- Launch via `am start --display` with flags new-task + multiple-task + exclude-from-recents (Intent flags combine to 0x18800000) so the task never shows up in the owner's Recents; comment says opening a task from Recents would migrate it to the phone display and leave the virtual display blank [R].
- If the same app is running on another display it returns "restart confirmation required"; with approval it force-stops the package, verifies it is gone, then launches. Refuses for system apps and for the controller. Approval is a phone notification (2 min wait) or an auto-approve setting.
- After launch verifies every task of that package is on the virtual display, remembers those task ids, and later detects "app moved to the phone" (task id no longer on the virtual display).
- Optional VIEW uri with the launch (limited length, no NULs).

### 4.3 Input
- Strictly display-scoped: the engine takes no caller-supplied display id; input goes through a native touch stream tied to the owned display; failed ops never fall back to the phone screen.
- Coordinates must be inside display bounds; swipe is a polyline of 2-64 points; scroll is described as a signed unit count (+-20) converted to a swipe from the point; long press duration 200-2000 ms; key codes restricted to a whitelist of navigation/editing keys.
- Unicode text: accessibility service sets text in the focused editable of the display's windows (limit 20k chars, no NULs), with "replace" option; fallback for displays without accessible editors: write the clipboard, deliver paste to the display, restore the clipboard only if it is still ours.
- Gesture bookkeeping: a cancel command sends cancel to the active gesture so the previous call's delayed error cannot cancel the next one.

### 4.4 Focus / IME
- Sets STEAL_TOP_FOCUS_DISABLED + OWN_FOCUS on 14+; claims "independent focus" in its status response only for API >= 34. Does not describe IME policy changes in what I read. Takeover model instead: only one controller at a time (exclusive 5-minute lease, local phone touch revokes remote), "observation id" must match for any input (stale or ambiguous selector rejected), a "fence" counter invalidates in-flight work when control changes hands.

### 4.5 Frame capture
- An `ImageReader` (RGBA_8888, 3 buffers) drains the display without encoding anything until someone asks for pixels. Keeps a single raw buffer so a STATIC app is still observable (no new frames submitted). Encodes JPEG on demand; a fingerprint per frame supports "wait for frame change". Observation request waits up to ~2 s for a fresh encode; a stale JPEG cannot satisfy a request.
- Separate "mirror" path renders to a SurfaceView for the full-screen viewer and picture-in-picture preview (read-only PiP, phone touch = takeover). The PiP activity is started with the shell's real Binder identity (null caller) because a synthetic system context was rejected.

### 4.6 UI tree
- The app's own accessibility service reads windows of exactly the owned display (API 30+ per-display window list, filtered again by display id). Nodes get ids per observation; actions on a node check the window still exists, node refresh succeeds and a signature (stable fields, not bounds) still matches, otherwise "stale observation". Compact tree format omits default values; full format includes all states. Reports distinct situations: no running app, accessibility not connected, target window nodes not ready yet.
- Wait conditions: fixed delay, frame change, node text, node present, node absent, foreground app, UI stable for 500 ms (max 30 s). Text match defaults to case-insensitive because some widgets upper-case their labels.
- Measured: tree-only observe is ~3x faster and ~6x smaller than screenshot+tree in their fixture.

### 4.7 Tools exposed (own words; 19)
Control lease: acquire, release, request takeover (async notification approval), status/capabilities, receipt lookup by request id. Display: create, reconfigure (rebuild), close. Apps: list, launch (component + optional uri, may block for approval). Observe: tree / screenshot / both, compact / full. Input: tap at, long press at, swipe path, scroll at, type text, act on a node (click, long click, focus, scroll, set text) by id or unique selector, press key. Wait: conditions above.
Every call carries a purpose string; results include request receipts so a client can ask "did my last request execute?" after a dropped connection without replaying input.

### 4.8 Teardown / errors
Release order: mirror, input, rotation helper, capture, display, reader, wake lock, clear hosted tasks. Any failure in create triggers full release. Subprocess helper caps (8 s timeout, 64 KB output). Error vocabulary (display gone, stale handle, frame pending, coordinate out of bounds, etc.) is a good checklist for headroid's own error taxonomy.

### 4.9 Documented problems
- vivo X Fold3 + Shizuku: virtual screen could not be created in 0.1.0 (issue 1, closed; owner suggested a newer build and Stellar/Shizuku-next). On Android 15+ Shizuku compat layer reportedly dropped its user-service connection callback; they added a native Stellar path.
- Tunnel/background tests irrelevant to headroid.
- Not verified at the time of release: other ROMs, Android 13-15 physical phones, normal-shell-UID Shizuku on phone, long screen-off matrix. Root run on Android 17 needed an init workaround (see 1.2).

---

## 5. closepaw (imoonkey/closepaw) — Apache-2.0 (reusable with attribution)

Files: `app/src/main/kotlin/ai/closepaw/platform/virtualdisplay/*`, doc `doc/main/infra/virtual_display.md`, experiment note `doc/main/infra/tool/click_transport_experiment.md`. Android 12+ (API 31+). Hybrid: accessibility service (in the same app) + Shizuku for the VD mode.

### 5.1 Display creation
- `VirtualDisplayConfig.kt`: size from the real full-screen bounds (`WindowManager.maximumWindowMetrics`, API 31+, includes nav bar and cutout; falls back to `getRealMetrics`) and the phone's DPI so apps lay out like on the real screen.
- `VirtualDisplayPlatform.kt`: flags public, "0x8" (their comment says secure but 0x8 is OWN_CONTENT_ONLY; SECURE is 0x4 — see Q9), supports-touch, should-show-system-decorations, trusted, own-display-group. No always-unlocked, no own-focus, no steal-focus flag. 200 ms settle delay after creation. `ImageReader` with 2 images.
- `ShizukuDisplayTransport.kt`: calls the display-manager binder directly (see 1.2), API 33+ config-object variant, legacy variants for 31-32, and package-name candidate cycling.

### 5.2 Launch
- `VirtualDisplayAppController.kt`: primary `am start -n <component> --display <id>` through the Shizuku shell; fallback `startActivity` with launch-display option and NEW_TASK + MULTIPLE_TASK (`ShizukuActivityLauncher.kt`).

### 5.3 Input
- `VirtualDisplayInputInjector.kt`: MotionEvent with touchscreen source + `setDisplayId`; a one-time round-trip check (set 42, read back) decides whether reflection works; if not, falls back to `input -d <id> tap|swipe|keyevent`. Tap uses `ViewConfiguration.getTapTimeout()`; swipe = 20 interpolated moves; long press holds DOWN then UP. If a coroutine is cancelled or errors after DOWN, it sends ACTION_CANCEL so the target view is not left pressed or dragging. System buttons: back, home, app-switch, enter as display-targeted key events.
- Also prefers accessibility node actions (click by node reference) over raw touch because their experiment found those succeeded where raw injection did not (see 5.9).

### 5.4 Focus / IME
- `allowTapToFocus()` = false for VD mode.
- Different trick from the others: around any action that might focus an input (taps, long presses, set-text), if NO soft keyboard window is currently shown on display 0 (detected via the accessibility window list, type input-method), temporarily set the accessibility soft-keyboard show mode to HIDDEN, then restore AUTO afterward (and restore on stop so a crash cannot leave the IME disabled). It deliberately skips suppression when the owner's keyboard is already visible. Public API (`AccessibilityService.getSoftKeyboardController().setShowMode`), needs the app's accessibility service.

### 5.5 Capture
- ImageReader as default sink; hybrid mode: when its viewer is visible, repoint the display to the viewer's SurfaceView via the display-manager `setVirtualDisplaySurface` (needs the saved callback token) and capture with PixelCopy; after 2 PixelCopy failures auto-revert to ImageReader. All callback APIs wrapped with timeouts (screenshot callbacks 5 s with HardwareBuffer closed on late arrival; PixelCopy 3 s with no recycle on timeout).

### 5.6 UI tree
- `VirtualDisplayWindowAccessor.kt`: window list per display (`getWindowsOnAllDisplays` on API 33+, otherwise filter by `displayId`); the "current root" is the top-layer application-type window, excluding accessibility overlays and IME windows; multi-root capture sorts windows bottom-to-top by layer.

### 5.7 Agent tools
Tool roster (`doc/main/infra/tools.md`): one UI action tool (click, long press, type, scroll, swipe), open app, system button, plus planning/memory/shell/browser tools not relevant here. A policy engine decides per call based on which app tier the agent is in.

### 5.8 Teardown and lifecycle (very reusable)
- `VdLifecycleArbiter.kt`: states Stopped / Running / Draining / Broken. Lifecycle changes hold an exclusive lock; operational calls hold counted shared leases; stop moves to Draining (new leases fail fast) and waits up to 5 s for in-flight ops; Binder death marks Broken without taking the lock; start rolls back everything if any step after creation fails, and cleans leftovers if starting from Broken.
- Release order: restore keyboard show mode, drop binder-death listener, reset surface mode, REMOVE ALL ROOT TASKS ON THE DISPLAY (`ShizukuActivityTaskTransport.kt`), release display, close reader, clear cached binder proxies.

### 5.9 Documented findings and problems
- Click experiment (emulator API 34, Files app list rows): node-level click worked in all runs on both display 0 and the VD; accessibility `dispatchGesture` returned success but did nothing; app-side Shizuku injection returned `true` but did nothing, including on display 0, and the display-id setter failed with NoSuchMethod even after a hidden-API bypass; shell `input tap` worked on display 0 but `input -d 11 tap` on a simulated overlay display (display 11) did nothing. The author flags that the Shizuku result may be test-setup noise (bypass timing), and says other apps accepted all four transports. LESSON: injection can report success without effect; always verify an effect, and keep a node-action path as alternative.
- Reliability design: "accepted vs changed vs unverifiable" outcome classes after each action.
- Issue tracker: 2 open, none about the VD.

---

## 6. Ruto-GLM (iamr0s/Ruto-GLM) — Apache-2.0 (reusable with attribution)

Files under `app/src/main/java/com/rosan/ruto/`: `service/display/DisplayManagerServiceStub.kt`, `UService.kt`, `OtherService.kt`, `service/InputManagerService.kt`, `ImeManagerService.kt`, `MyInputMethodService.kt`, `ActivityManagerService.kt`, `ruto/GLMCommandParser.kt`, prompt `app/src/main/assets/prompts/glm_phone.txt`; AIDL in `app/src/main/aidl/com/rosan/ruto/service/`.

### 6.1 Display creation
- Plain `DisplayManager.createVirtualDisplay(name, w, h, density, surface, flags = 0)` with flags ZERO: an untrusted private display. Size from the main display's logical size/density. Surface from an `ImageReader` (RGBA_8888, 1 image) unless one is passed in. Mirror helpers exist for mirroring a real display: Android 14+ uses the hidden 5-arg mirror overload (the same one scrcpy uses for non-new-display mode); older versions use SurfaceControl display tokens (code copied in approach from scrcpy's `ScreenCapture`).
- AIDL lists: displays, info, create, mirror, own-display check, capture bitmap, set surface, release.

### 6.2 Launch
- `ActivityManagerService.kt`: fuzzy app finder (exact package > exact label > label prefix > label contains > package contains; ties broken by shorter label); launch via a PendingIntent created in a display-specific context, ActivityOptions launch display, NEW_TASK + LAUNCH_ADJACENT.

### 6.3 Input
- `InputManagerService.kt`: touchscreen-source MotionEvents, `setDisplayId` when id != 0, API 33+ "inject to target" call with default uid, wait-for-finish mode. Click hold 100 ms, double click gap 100 ms, long press 1 s, swipe 1 s on an ease-in-out cubic path with a busy loop; back/home as key events with the display id.

### 6.4 Text / IME (anti-pattern for headroid)
- Ships its own `InputMethodService`; to type, it temporarily changes the SYSTEM default IME to its own (enable then switch), waits up to 75 s for the service instance, commits text (optionally one char per 50 ms), then switches back. This changes the owner's keyboard globally for the duration and would interrupt the owner. Do not copy this behaviour.

### 6.5 Capture
- Surface pixel-copy of the display's own surface for virtual displays; `screencap -d <physical display id>` only for real physical displays (the physical-id lookup returns null for virtual ones, so it is the fallback path).

### 6.6 Agent vocabulary
Launch app, tap (coordinates normalised 0-999 on both axes), tap with a "this is a sensitive action" message, type, type-name, swipe, long press, double tap, back, home, wait N seconds, note, call-API, interact, take-over (ask human), finish.

### 6.7 Documented problems (issues, all open)
- ColorOS 16: in an app (Duolingo) later activities open on the main display instead of the virtual one; the agent loses sight of the screen. Relaunching the app returns it to the virtual display for a moment.
- Redmi Note 14 and Redmi 10X (MIUI 13, Android 12): creating the display does nothing / no display list; vivo S50: operations no response; Gemini-model task crash; session creation crash. No fixes or replies.
- The project uses an untrusted display (flags 0), which fits the "activities leak to the main display" reports. [I, inference]

---

## 7. scrcpy (Genymobile/scrcpy) — Apache-2.0 (reusable with attribution)

Relevant paths: `video/NewDisplayCapture.java` (creation), `wrappers/DisplayManager.java`, `wrappers/WindowManager.java` (IME policy, rotation), `wrappers/InputManager.java`, `device/Device.java`, `control/Controller.java`, `display/DisplayMonitor.java`, `Workarounds.java`, `FakeContext.java`, `CleanUp.java`; user docs `doc/virtual-display.md`.

### 7.1 Creation
- Flags exactly as in the table in 1.1: public, presentation, own-content-only, supports-touch, rotates-with-content; optional destroy-content-on-removal and system-decorations (default on; `--no-vd-system-decorations` off); 13+: trusted, own-display-group, always-unlocked, touch-feedback-disabled; 14+: own-focus, device-display-group. NO steal-top-focus flag. This is the fork point for headroid.
- Size/density default from the main display's NATURAL orientation size and its DPI; scales DPI if only a size is given; aligns size to codec alignment; "flex display" mode resizes the live display (`VirtualDisplay.resize`) with a debounce.
- Optional IME policy applied after creation (`--display-ime-policy=local|fallback|hide`; doc says the default behaviour is that the IME appears on the default display).
- Display change detection: `DisplayMonitor.java` uses a display-window listener (API 30+) rather than the display listener because the latter was reported broken on some Android 14 and again on Android 15 (scrcpy #5908).

### 7.2 Launch
- `Device.startApp`: launch intent from package manager (leanback fallback), NEW_TASK, `ActivityOptions.setLaunchDisplayId` (API 26+), optional force-stop first, via `ActivityManager.startActivity` as the fake shell context. Apps list = launchable apps; search by prefix on label.

### 7.3 Input
- `Device.injectEvent`: only sets a display id when the target is not display 0 and the OS is Android 10+; inject mode async for most events.
- `Controller.java` header comment explains the two ids: when a new virtual display is created, ALL events (touch and key) go to the virtual display id; when mirroring a real display, touch uses the mirror's display id and key events the real one.
- Text typing: converted to key events through the virtual keyboard character map (accents decomposed first); characters not representable are skipped with a warning (no IME, no Unicode beyond the map). Optional UHID keyboard/mouse; on Android 15+ the UHID device is bound to a display via the display's unique id association.
- Source comment in `Controller.java`: the per-display screen-on query ignores its display argument before Android 14, so per-display power logic is only trustworthy on 14+.

### 7.4 Teardown and errors
- Virtual display destroyed on exit unless `--no-vd-destroy-content`, which moves apps to the main display.
- `CleanUp.java`: a second process (started in its own session) outlives the server and restores settings and display power even if the server is killed by a USB/ADB disconnect. Good pattern for wireless ADB drops.

### 7.5 Known problems (issues)
- #5523 (open): Android 15 QPR2/March Pixel update: shell lost the three display-trust permissions; breaks `--new-display`. Fixed on Android 16 betas.
- #6643 (open): On a locked/idle phone, an app on a virtual display stops (animation freezes) after a while; a contributor found that apps with battery optimisation disabled keep running while other apps on the same virtual display freeze. Not confirmed by maintainers. [I]
- #4598 (closed, no fix): Samsung One UI on Android 14 creates an extra display when scrcpy starts; taps only work when injected at the neighbouring display id; workaround was driving two instances.
- #6561 (open): no audio isolation for virtual displays (audio plays on the phone).
- Rotation-listener and square-display reset problems were fixed (#5428, #6770).

---

## 8. Cross-project comparison

| Topic | Mua | PhoneAgent | AVS | closepaw | Ruto | scrcpy |
|---|---|---|---|---|---|---|
| Min Android | 12 | 11 (tested 14) | 13 | 12 | ? (flags 0) | 5+ for mirror; new display 10+ |
| Trusted display | 13+ | yes | yes | yes | no | 13+ |
| OWN_FOCUS | 14+ | yes | 14+ | no | no | 14+ |
| STEAL_TOP_FOCUS_DISABLED | no | yes (1<<16) | 14+ | no | no | no |
| IME policy | HIDE | HIDE | not seen | not set; uses a11y keyboard show-mode bracket | none; swaps system IME | optional |
| Text path | a11y SET_TEXT | UiAutomation SET_TEXT + paste fallback | a11y SET_TEXT + clipboard-paste fallback | a11y node set text | custom IME swap | key events from char map |
| Tree per display | none (screenshots) | UiAutomation in shell, all windows | a11y service | a11y service | none (vision) | none |
| Input method | setDisplayId + injectInputEvent / `input -d` | setDisplayId + injectInputEvent | native touch stream | setDisplayId, fallback `input -d` | setDisplayId + inject | setDisplayId + inject |
| Teardown task cleanup | no | yes (found essential) | clear hosted tasks, force-stop | yes | no | destroy-content flag |
| Real-phone evidence | none stated | none (emulator) | vivo A16, Xiaomi A17(root) | emulator | user reports of failures | many |

---

## 9. Techniques headroid should adopt (original implementation required)

### Display creation
1. Create the display from an on-device process launched by `app_process` over wireless ADB (scrcpy architecture), as shell uid with a context claiming `com.android.shell`. Capability-probe at start: Android version, whether each hidden flag constant exists, whether ADD_TRUSTED_DISPLAY works, and whether creation succeeds with the full flag set; fall back through a documented ladder (full set -> without ALWAYS_UNLOCKED -> without TRUSTED group flags -> fail with a clear message) and report the ladder level in the status.
2. Flag set: PUBLIC? (needed so other apps can be launched there) + OWN_CONTENT_ONLY + SUPPORTS_TOUCH + ROTATES_WITH_CONTENT + DESTROY_CONTENT_ON_REMOVAL, + (13+) TRUSTED, OWN_DISPLAY_GROUP, ALWAYS_UNLOCKED, TOUCH_FEEDBACK_DISABLED, + (14+) OWN_FOCUS, DEVICE_DISPLAY_GROUP, STEAL_TOP_FOCUS_DISABLED (1<<16, read constant by reflection with 1<<16 fallback). Omit SHOULD_SHOW_SYSTEM_DECORATIONS by default (configurable), omit PRESENTATION unless a test needs it.
3. Always set the display IME policy to HIDE right after creation, every time (the policy is cached per display unique id).
4. Default size: the phone's own full-screen bounds and DPI so app layouts match what testers expect; allow overriding for responsive tests.
5. Frame sink owned by the on-device server: an ImageReader whose surface is given to the display; keep only the latest image; handle row-stride padding; store a raw copy so static screens remain capturable; encode (PNG/JPEG) only on request; a per-frame fingerprint supports "wait for visual change". Do NOT rely on `screencap -d` for virtual displays.
6. Virtual display must be recreated if its surface dies; track binder death in both directions.

### Launch and app ownership
7. Launch via `ActivityOptions.setLaunchDisplayId` + NEW_TASK (+ MULTIPLE_TASK when starting a fresh task; consider EXCLUDE_FROM_RECENTS so Recents on the phone cannot pull the task over). Offer `am start --display` as a fallback. Verify success by polling the task list for the package on the target display (the call returns before the task exists).
8. Before launching, query the task list: if the same package is in front on the phone, return a typed error "app in use by owner" (default) rather than stealing it; offer opt-in force-stop-and-relaunch. After launch, store the task ids and detect "task moved to phone" on every later step.
9. Check `ActivityInfo` resizability and explicit-exported state before launch to give a precise unsupported error.
10. Provide "adopt this running task onto the virtual display" and "hand back to phone" (move root task + set it focused) for debugging sessions; roll back if the move fails.

### Input
11. All input to a display goes through one function that sets the display id on every event and injects with wait-for-finish or async mode; touch events must carry touchscreen source, key events keyboard source with the virtual keyboard device. Never use global actions (back/home) for the virtual display.
12. Implement tap, long press, multi-point swipe, scroll gesture, pinch (multi-pointer), key (whitelist), with realistic timing (tap hold roughly the platform tap timeout, swipe interpolated in 15-20 steps). Always send ACTION_CANCEL when a gesture is aborted after DOWN.
13. Provide an "effect check" after each input: new tree signature or frame fingerprint, else report `accepted_no_change`. Injection returning true proves nothing (closepaw measurements).
14. Keep a node-action path (accessibility ACTION_CLICK / SET_TEXT / SCROLL) as the preferred or fallback transport; semantic click for native views, touch for WebViews.
15. Text input without touching the owner's IME: (a) accessibility ACTION_SET_TEXT on the focused editable node found in the display's windows; (b) paste path (write clipboard, select-all, key-paste to that display, restore clipboard) for fields that refuse SET_TEXT; (c) `input -d N text` only for ASCII. Never switch the system default IME (Ruto's approach).

### Focus, IME, user isolation
16. Combine OWN_FOCUS + TRUSTED + STEAL_TOP_FOCUS_DISABLED + IME policy HIDE, then PROVE it per device with the PhoneAgent-style harness (keyboard shown, focused window, current input client, top focused display must not change while scripted actions run). Ship this as `headroid doctor --isolation` so users see a pass/fail per phone.
17. Fallback ladder when the flag is unavailable: closepaw-style soft-keyboard show-mode bracket (if headroid ships an accessibility service), and PhoneAgent-style "pause while the owner's keyboard is visible", configurable.
18. Document honestly that the same app cannot be used by owner and test at once, and that launches/dialogs can still raise top focus on some ROMs.

### UI tree per display
19. Two sources, selected automatically: (a) a `UiAutomation` created inside the shell helper (no accessibility enable step, but only one UiAutomation client per device, so it conflicts with running UiAutomator/Appium; connect with the "don't suppress accessibility services" flag, create it with a looper on a separate thread, request interactive-windows retrieval, read `windowsOnAllDisplays[displayId]`); (b) an on-device accessibility service enabled by `settings put secure enabled_accessibility_services` merged with existing ones. Provide a CLI toggle.
20. Tree format: flat depth-first list with window id, pre-order index, depth, bounds, class, resource id, text/hint flag, content description, state flags, z-order among siblings, truncation flag. Node reference = (window id, index, bounds) and re-verified at action time; mismatch -> stale-reference error with automatic re-resolve by selector.
21. "Wait for stable UI" based on tree signature equality over N polls (not pixel hash, caret blink), with longer budget for empty-tree/WebView pages; separate "empty tree" detection to switch to vision/OCR mode.
22. Top window selection: highest layer of type application, excluding accessibility overlays and IME; capture all windows (dialogs, popups) as additional roots.
23. First tree read after connecting may be empty: retry with backoff; retry also when the target window is new.

### Agent-facing API (Playwright-like)
24. Locators resolved against the per-display tree (text, id, description, class, hierarchy), auto-wait for actionable (visible, enabled, stable bounds) before action, post-action `expect` assertions, trace with screenshots + tree per step, video from the frame stream.
25. Idempotency/receipts: every command has a request id and the server keeps a short receipt log so a client that lost its connection can ask "did request X run?" without replaying input (AVS idea). Observation ids / epochs reject actions based on stale observations.
26. Exclusive control model: one controller per display at a time; local phone touch/notification can pause or revoke test control. Optional approval gate for dangerous operations (restart an app that the owner is using).
27. A typed error vocabulary: display gone, stale handle, no frame yet, app moved to phone, app not resizable, trust permission missing, screen off/locked unavailable, coordinate out of bounds, key unsupported, accepted-no-change.
28. Tool surface should include per-display `focused package`, `list tasks`, `list displays`, `capabilities`, `clipboard get/set (verified)`, and `notifications` (listing; actions with launch-display option) — Mua showed notification-driven flows (open from a notification, reply via remote input) are valuable for messaging-app tests.

### Lifecycle and teardown
29. Lifecycle state machine (Stopped/Running/Draining/Broken) with counted operation leases, exclusive lifecycle lock, 5 s drain timeout, Binder-death -> Broken, rollback on partial start (closepaw design, Apache-2.0, can be adapted with attribution).
30. Teardown order: stop gestures, disconnect tree source, REMOVE ALL ROOT TASKS ON THE DISPLAY (`getAllRootTaskInfosOnDisplay` + `removeTask`), release display, then close sinks. Verify with `dumpsys display` and `dumpsys activity` that only display 0 remains. Never skip: orphan tasks can leave top-focused display on a dead display until reboot (PhoneAgent).
31. A watchdog/cleanup process that outlives the helper (scrcpy `CleanUp.java` idea) to remove displays and restore settings (accessibility enable list, IME policies, wake locks) after an ADB drop.
32. Idle timeout auto-release; stale helper detection and restart on version mismatch; helper started fresh per session by default.

### Power, screen-off, background
33. During a session hold a partial wake lock (and optionally a display-specific wake lock) from the helper; recommend battery-optimisation exemption for the helper and the app under test (scrcpy #6643 suspicion). Detect "app frozen" by comparing frame fingerprint + tree over time and report it.
34. Report phone state per operation: interactive / locked / screen off, and refuse with a typed error unless ALWAYS_UNLOCKED display succeeded.

### Compatibility and diagnosis
35. Maintain a capability matrix (`headroid doctor --json`) per device: Android API + security patch level, brand ROM, flag support, shell permissions, UiAutomation vs a11y path, IME isolation result, secure-content rendering, rotation freeze signature, notification listener enable result. Publish community results.
36. Always call `getWindowsOnAllDisplays`/`windows` defensively (API 30+ vs 33+ differences); wrap every hidden-API call with signature fallbacks (rotation freeze 2 vs 3 args, task-callback signatures, display-listener broken on 14/15).
37. Implement the three-ID insight from scrcpy: for a NEW virtual display, events go to that display id; never inject without the id set on non-zero displays; verify `setDisplayId` actually took effect (closepaw round-trip check) and fall back to `input -d`.

---

## 10. Open questions to verify on device (suggested experiment in brackets)

Q1. Does STEAL_TOP_FOCUS_DISABLED work on real phones/ROMs, and does it still hold when (a) an activity start is initiated by the app on the VD (dialog, permission prompt, share sheet), (b) a notification-driven launch, (c) the virtual-display app shows a toast, a system alert dialog, or an IME-triggering field? [PhoneAgent harness: keyboard shown / input client / focused window / `mTopFocusedDisplayId`]
Q2. With the flag set, does touching the owner's phone keyboard continue to reach the owner's field while the VD app's field is focused and being SET_TEXT'ed? And does the owner's own IME ever show over the VD (policy HIDE with a trusted display)?
Q3. Does Android 15 QPR2+/16 on the actual target phone allow `createVirtualDisplay` with TRUSTED + OWN_DISPLAY_GROUP + ALWAYS_UNLOCKED as shell? What is the exact SecurityException text on each OEM? Is there a shell-reachable alternative (e.g. VirtualDeviceManager, or `Display` owner check)?
Q4. Which of the three trust permissions is actually needed for each flag (ADD_TRUSTED_DISPLAY / ADD_ALWAYS_UNLOCKED_DISPLAY / ADD_MIRROR_DISPLAY)? Test creation with each subset. Does dropping ALWAYS_UNLOCKED still let apps run while the owner's screen is on?
Q5. Behaviour with phone screen OFF and locked: do apps on the VD keep rendering, do frames arrive, does injection work, do tasks freeze after N minutes (scrcpy #6643)? Does battery-optimisation exemption of the app under test change this? Does a partial wake lock vs display-bound full wake lock matter?
Q6. Does the app under test pause (onPause/onStop) or keep resumed on a trusted own-focus display while another display is top focused? Resumed state of VD activities when the phone's display is in front.
Q7. How do apps that reject secondary displays (non-resizeable, `android:resizeableActivity=false`, Flutter/RN activities with fixed orientation) behave? Is a size/density override or `resizeableActivity` workaround viable via `wm`/overlay settings? How to detect "launched but landed on the phone" quickly?
Q8. Can the same app package be run on the VD while the owner uses the same app on the phone? PhoneAgent's note says an explicit-component launch is absorbed by the existing instance; test with `FLAG_ACTIVITY_MULTIPLE_TASK` + different task affinity + `documentLaunchMode`; and test `adb shell cmd` multi-user / work profile alternatives for true parallel instances.
Q9. FLAG_SECURE windows (banking, DRM, some WhatsApp screens): does the VD capture render black/blank? Does the public SECURE display flag (1<<2) change this for a shell-created display, or is a hidden permission required? (closepaw's flag comment suggests confusion between 0x4 and 0x8; check real behaviour of both.)
Q10. UiAutomation path: confirm that a shell-hosted UiAutomation sees windows of a non-default display and tolerates being used concurrently with an on-device a11y service and with Appium's UiAutomator2 instrumentation (known one-client limit). Measure tree fetch latency for large React Native / Flutter trees; does Flutter expose semantics only when accessibility is on?
Q11. Does `input -d <id> tap|swipe|keyevent|text` work on a real trusted VD on target phones (closepaw saw it fail on an overlay secondary display in an emulator)? Compare `input` shell vs direct InputManager injection latency and correctness, including multi-touch.
Q12. Multi-display ID association: on Samsung One UI 14 an extra display appeared and only the neighbour id received touches (scrcpy #4598). Check each target ROM for such duplication and for `input` routing.
Q13. Does the system IME appear at all for VD apps when policy is HIDE, and how do apps cope with no IME (some apps call showSoftInput and rely on it)? Is Unicode `ACTION_SET_TEXT` accepted by React Native `TextInput`, Flutter `TextField`, Compose fields, WebView inputs, and do app-level `onChangeText` callbacks fire?
Q14. Audio from VD apps plays on the phone speaker and vibration/notification sounds will disturb the owner (scrcpy #6561). Is there any shell-level mute per app (appops, `cmd media_session`, audio policy) that does not affect the owner's media?
Q15. Wireless ADB resilience: what happens to the helper when the Wi-Fi drops mid-run? Does `app_process` survive (nohup, new session as in scrcpy `CleanUp`)? How to reattach to a running display after reconnect?
Q16. Which Android versions need which package name / signature variants for `createVirtualDisplay`, rotation freeze, `setDisplayImePolicy`, task APIs? (closepaw lists 3 shapes for display creation; AVS lists 2 shapes for rotation freeze.) Build a reflection test suite per API level.
Q17. Does `ImageReader` frame cadence depend on the app (static screen = 0 fps)? Is a periodic forced redraw needed for video capture? What is the CPU/battery cost of a hidden display at 60 fps on a phone in the owner's pocket?
Q18. Shell clipboard access on Android 12-16: do clipboard reads/writes work from the shell helper while the phone is locked? (Mua reports a specific failure message when Android blocks it; one OEM extended the clipboard binder call with extra attribution args, so use the public ClipboardManager with a fake context where possible.)
Q19. Can headroid enable an accessibility service from shell on OEMs that guard `enabled_accessibility_services` (Xiaomi, Oppo, vivo restrict "install unknown apps"/auto-start)? Does changing the setting survive phone reboot and does it flash a user-visible warning?
Q20. Does drawing the touch cursor / "show touches" affect the VD? Does `TOUCH_FEEDBACK_DISABLED` hide the owner's pointer location overlay?
Q21. Fingerprint/PIN prompts raised by apps on the VD: where does the biometric dialog appear (phone display?), can the VD be paused behind it, and can the test detect it as "needs human"?
Q22. Rotation: how do apps with locked portrait/landscape behave when the VD is created at phone resolution; does the freeze-rotation call keep the VD size stable across app-requested orientation changes?
