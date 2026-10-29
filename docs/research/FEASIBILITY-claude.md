# Headless Android on a Physical Phone: Technical Feasibility Study

Author: Claude (research agent), 2026-10-29
Scope: AI Agent -> Controller -> Wireless ADB -> on-device `app_process` service (scrcpy-server style, uid 2000 "shell") -> isolated VirtualDisplay -> app under test, on a non-rooted phone.

## Verdict (short)

**It works on non-rooted phones, with real limits. Android 14+ is the practical floor for good isolation. Android 13 works with some leakage. Android 10 to 12 work only with significant leakage.**

- On Android 13+, a shell-uid process can create a **trusted, public, own-content-only virtual display backed by any Surface (for example an ImageReader nobody shows)**, launch any launchable activity onto it, inject input to it by `displayId`, set its IME policy, and read its UI tree. scrcpy 3.x+ does this today (`--new-display`).
- On Android 14+, the same process can also set **`VIRTUAL_DISPLAY_FLAG_OWN_FOCUS` and `VIRTUAL_DISPLAY_FLAG_STEAL_TOP_FOCUS_DISABLED`**. These two flags give true focus isolation: the user's foreground app keeps global focus and its keyboard while the agent taps and types on the virtual display. **scrcpy does not set `STEAL_TOP_FOCUS_DISABLED`**, so stock scrcpy steals the top focus on every injected tap. A small fork of the server (one flag) fixes this.
- Things that stay shared and leak, and cannot be fixed without root or system changes: audio output, vibration, notifications and heads-up alerts, toasts or system dialogs that the system routes to the default display, and the single global IME instance. Also, **FLAG_SECURE windows render black**, because shell cannot create secure displays since Android 12.

Confidence in the overall verdict: **High** for the API and permission mechanics, which come from AOSP source. **Medium** for the end-to-end behaviour on OEM skins, which needs the 1-hour PoC below.

---

## Capability table

| # | Capability | Non-root (shell uid 2000)? | Android version | Evidence | Confidence |
|---|---|---|---|---|---|
| 1 | Create a VirtualDisplay from `app_process` | Yes | 10+ (scrcpy refuses `--new-display` below 10) | scrcpy `Server.java` (API_29 gate); `wrappers/DisplayManager.createNewVirtualDisplay` uses the hidden `DisplayManager(Context)` ctor with a FakeContext | High |
| 2 | `PUBLIC` + `OWN_CONTENT_ONLY` (not a mirror, no CAPTURE_VIDEO_OUTPUT needed) | Yes | 10+ | `DisplayManagerService.createVirtualDisplayInternal`: PUBLIC adds AUTO_MIRROR, OWN_CONTENT_ONLY clears it, and the CAPTURE_VIDEO_OUTPUT check only applies to AUTO_MIRROR | High |
| 3 | `TRUSTED` (needs `ADD_TRUSTED_DISPLAY`) | Yes | **13+ only** | Shell `AndroidManifest.xml` declares `ADD_TRUSTED_DISPLAY` and `ADD_ALWAYS_UNLOCKED_DISPLAY` at tags android-13.0.0_r1, 14.0.0_r1, 15.0.0_r1, 16.0.0_r1 and branch android16-qpr2-release, but **not** at 10/11/12/12.1. DMS throws SecurityException without it. | High |
| 4 | `OWN_DISPLAY_GROUP`, `ALWAYS_UNLOCKED` | Yes | 13+ | DMS: OWN_DISPLAY_GROUP needs ADD_TRUSTED_DISPLAY; ALWAYS_UNLOCKED needs ADD_ALWAYS_UNLOCKED_DISPLAY **and** OWN/DEVICE display group (`VirtualDisplayAdapter`) | High |
| 5 | `SHOULD_SHOW_SYSTEM_DECORATIONS` | Yes, only together with TRUSTED | 13+ (silently cleared if untrusted) | DMS: `if ((flags & TRUSTED)==0) flags &= ~SHOULD_SHOW_SYSTEM_DECORATIONS` | High |
| 6 | `OWN_FOCUS` (per-display focused window) | Yes | 14+ (flag `1<<14`; ignored unless TRUSTED) | `VirtualDisplayAdapter`: "Ignoring VIRTUAL_DISPLAY_FLAG_OWN_FOCUS as it requires VIRTUAL_DISPLAY_FLAG_TRUSTED"; scrcpy sets it on API 34+ | High |
| 7 | `STEAL_TOP_FOCUS_DISABLED` | Yes (no permission check in DMS; needs TRUSTED + OWN_FOCUS) | 14+ (`1<<16`, `@SystemApi @hide`) | `DisplayManager.java` (14/15/16); `VirtualDisplayAdapter` lines ~625-633; `WindowManagerService.moveDisplayToTopInternal` returns early if `!canStealTopFocus()`. **Not set by scrcpy.** | High (code), Medium (runtime) |
| 8 | `SECURE` display (FLAG_SECURE content visible) | **No** (needs CAPTURE_SECURE_VIDEO_OUTPUT, which shell lacks) | 12+ blocked for shell | DMS secure check; shell manifest lacks CAPTURE_SECURE_VIDEO_OUTPUT; scrcpy changelog: "Android 12 no longer allows shell to create a secure display" | High |
| 9 | Invisible display (Surface = ImageReader nobody shows) | Yes | 10+ | Any Surface works. **The Surface must be non-null**: `VirtualDisplayAdapter` sets `state = STATE_OFF` when `mSurface == null`, which sends activities to sleep. | High |
| 10 | Launch any app on the virtual display | Yes (shell holds INTERNAL_SYSTEM_WINDOW, so "allow launch any on display") | 10+; device must declare `android.software.activities_on_secondary_displays` | `ActivityTaskSupervisor.isCallerAllowedToLaunchOnDisplay` / `canPlaceEntityOnDisplay`; `ActivityTaskManagerService.retrieveSettings` (`mSupportsMultiDisplay`) | High |
| 11 | Inject touch/key to a specific display | Yes (INJECT_EVENTS) | 10+ | `input -d <id> tap/swipe/text/keyevent` (`InputShellCommand`); scrcpy `InputEvent.setDisplayId` + `InputManager.injectInputEvent` | High |
| 12 | Physical touchscreen never affected by injected events | Yes | 10+ | Events carry their own displayId. Physical touch is bound to display 0. | High |
| 13 | User's app keeps focus and keyboard during agent taps | Yes **only with flag 7** | 14+ | `WindowState.handleTapOutsideFocusInsideSelf` calls `moveDisplayToTopInternal`, which is blocked by STEAL_TOP_FOCUS_DISABLED | Medium (UNVERIFIED on device) |
| 14 | Key/text to a background virtual display (not top-focused) | Yes on 14+ (OWN_FOCUS); unreliable on 10-13 | 14+ | `DisplayContent.findFocusedWindowIfNeeded`: a non-top display gets no focused window unless `hasOwnFocus()` or per-display focus is enabled | High (code) |
| 15 | IME policy LOCAL / FALLBACK / HIDE | Yes, **trusted displays only** | 13+ in practice (the API exists since 10/11, but untrusted displays throw) | `WMS.setDisplayImePolicy`: needs INTERNAL_SYSTEM_WINDOW and `displayContent.isTrusted()`; default for virtual displays is `FALLBACK_DISPLAY` (`DisplayWindowSettings.getImePolicyLocked`) | High |
| 16 | Text entry without any IME | Yes (KeyCharacterMap key events via `input text`, or `AccessibilityNodeInfo.ACTION_SET_TEXT`) | 10+ | `input text`; UiAutomator2 `setText` uses ACTION_SET_TEXT | High for ASCII key events; Medium for Flutter |
| 17 | App on the virtual display RESUMED while user uses another app | Yes (multi-resume) | 10+ | developer.android.com multi-window docs: "Android 10 ... support multi-resume" | High (docs), Medium (OEM) |
| 18 | Keep running with the phone screen off / locked | Probably (OWN_DISPLAY_GROUP gives a separate power group; ALWAYS_UNLOCKED skips keyguard) | 13+ | `VirtualDisplayAdapter` ALWAYS_UNLOCKED; scrcpy `Device.keepActive(displayId)` -> `PowerManager.userActivity(displayId)` | **UNVERIFIED** |
| 19 | Screenshot of the virtual display | Yes: read your own ImageReader (best), or `screencap -d <SurfaceFlinger id>` | ImageReader 10+; `screencap -d <virtual id>` on builds with the "Allow virtual display ID in -d" change (AOSP 16 code accepts any `DisplayId`) | `cmds/screencap/screencap.cpp` (android16-qpr2: `DisplayId::fromValue`); Appium docs: virtual-display screenshot only since API 34 on emulators | High (ImageReader), Medium (screencap) |
| 20 | UI hierarchy per display | Yes (UiAutomation `getWindowsOnAllDisplays`, `AccessibilityWindowInfo.getDisplayId`) | 11+ (API 30) | Appium UiAutomator2 driver multiwindow guide: `currentDisplayId` setting, "since Android 11"; a11y skips only untrusted **private** virtual displays (`AccessibilityManagerService.isValidDisplay`) | High |
| 21 | Audio, vibration, notifications isolated | **No** (global). Partial mitigation through appops. | all | Single audio mixer and status bar; see section 5 | High |
| 22 | Per-display focus for the whole system (`config_perDisplayFocusEnabled`) | **No** (framework resource overlay, needs a system image or root) | 10+ | source.android.com multi-display "Per-display focus" ("strongly recommends against" on phones) | High |

---

## 1. Display creation

**How shell does it.** scrcpy's server runs as `CLASSPATH=/data/local/tmp/scrcpy-server.jar app_process / com.genymobile.scrcpy.Server`, so it runs as uid 2000 under the `com.android.shell` package identity. Its `wrappers/DisplayManager.createNewVirtualDisplay(name, w, h, dpi, surface, flags)` reflects the **hidden `DisplayManager(Context)` constructor**, builds it with a `FakeContext` (package `com.android.shell`), and then calls the normal public `createVirtualDisplay(name, w, h, dpi, surface, flags)`. Binder calls arrive at `DisplayManagerService` with `callingUid = 2000`, and the permission checks are made against the Shell package's permissions.

**Flags scrcpy uses** (`server/.../video/NewDisplayCapture.java`, `startNew`):

- Always: `PUBLIC | PRESENTATION | OWN_CONTENT_ONLY | SUPPORTS_TOUCH (1<<6) | ROTATES_WITH_CONTENT (1<<7)`
- Optional: `DESTROY_CONTENT_ON_REMOVAL (1<<8)` (on by default; turned off by `--no-vd-destroy-content`), `SHOULD_SHOW_SYSTEM_DECORATIONS (1<<9)` (on by default; turned off by `--no-vd-system-decorations`)
- API 33+: `TRUSTED (1<<10) | OWN_DISPLAY_GROUP (1<<11) | ALWAYS_UNLOCKED (1<<12) | TOUCH_FEEDBACK_DISABLED (1<<13)`
- API 34+: `OWN_FOCUS (1<<14) | DEVICE_DISPLAY_GROUP (1<<15)`
- Then, only if the option is given: `IWindowManager.setDisplayImePolicy(id, policy)`

**Permission gates in `DisplayManagerService.createVirtualDisplayInternal`** (android16-qpr2-release, around lines 1772-1975):

| Flag | Check | Does shell hold it? |
|---|---|---|
| PUBLIC | Adds AUTO_MIRROR, unless OWN_CONTENT_ONLY clears it | n/a |
| AUTO_MIRROR (effective) | MediaProjection, ADD_MIRROR_DISPLAY, CAPTURE_VIDEO_OUTPUT or CAPTURE_SECURE_VIDEO_OUTPUT | Yes, CAPTURE_VIDEO_OUTPUT (in the Android 16 manifest). Not needed when OWN_CONTENT_ONLY is set. |
| SECURE | CAPTURE_SECURE_VIDEO_OUTPUT or a secure projection | **No** |
| TRUSTED | ADD_TRUSTED_DISPLAY (signature\|role) | **13+ yes, 10-12 no** |
| OWN_DISPLAY_GROUP | ADD_TRUSTED_DISPLAY | 13+ yes |
| ALWAYS_UNLOCKED | ADD_ALWAYS_UNLOCKED_DISPLAY, and it only takes effect with OWN or DEVICE display group | 13+ yes |
| SHOULD_SHOW_SYSTEM_DECORATIONS | Cleared if not TRUSTED. If untrusted, needs INTERNAL_SYSTEM_WINDOW. | yes |
| OWN_FOCUS / STEAL_TOP_FOCUS_DISABLED | No permission check. Silently ignored unless TRUSTED (and OWN_FOCUS for the latter). | n/a, so 14+ works |
| DEVICE_DISPLAY_GROUP | Only meaningful with a VirtualDevice; otherwise mostly a no-op | n/a |

Shell manifest evidence: `frameworks/base/packages/Shell/AndroidManifest.xml`, block "Permissions required for CTS test - CtsVirtualDevicesTestCases": `CREATE_VIRTUAL_DEVICE`, `ADD_TRUSTED_DISPLAY`, `ADD_ALWAYS_UNLOCKED_DISPLAY` are present at android-13/14/15/16 tags and android16-qpr1/qpr2 branches, and absent at android-10/11/12/12.1. (The AOSP `main` branch snapshot lacks this block, but it is shorter than the qpr2 branch. It appears to be a stale snapshot, not a removal. Watch this for Android 17: if a future release drops these from Shell, TRUSTED displays become impossible from adb. **UNVERIFIED risk**.) An OEM can also strip permissions from the Shell package (**UNVERIFIED** per OEM).

**Invisible display.** Yes. The Surface can belong to an `ImageReader` (or a MediaCodec input surface, as scrcpy uses). Nothing needs to be on screen. Important: a **null Surface turns the display off** (`VirtualDisplayAdapter`: `if (mSurface == null) mInfo.state = STATE_OFF`), and its activities stop. So always attach a real surface. Use a small `ImageReader` (maxImages 2-3) and call `acquireLatestImage()` on demand. That is cheap when idle, because frames are produced only when content changes.

**Recommended flag set for the framework (Android 14+):**
`OWN_CONTENT_ONLY | SUPPORTS_TOUCH | TRUSTED | OWN_DISPLAY_GROUP | ALWAYS_UNLOCKED | TOUCH_FEEDBACK_DISABLED | OWN_FOCUS | STEAL_TOP_FOCUS_DISABLED`, plus `PUBLIC` optionally, and without `SHOULD_SHOW_SYSTEM_DECORATIONS` (which avoids a launcher, a status bar and a nav bar on the virtual display). Consider dropping `PUBLIC`, `PRESENTATION` and `ROTATES_WITH_CONTENT`. A **private but trusted** display is still tracked by accessibility (`AccessibilityManagerService.isValidDisplay` only ignores *untrusted* private virtual displays), and shell can still launch onto it (INTERNAL_SYSTEM_WINDOW). It also stays hidden from other apps' `DisplayManager.getDisplays(DISPLAY_CATEGORY_PRESENTATION)`, so the user's apps (media apps, games) cannot throw a `Presentation` onto it. Confidence: Medium. This needs a device test, because launch-on-private-display paths have OEM variance.

## 2. Launching

- `adb shell am start --display <id> -n pkg/.Activity` (`--display` exists since Android 8/10) or `ActivityOptions.setLaunchDisplayId(id)` from the server process. scrcpy `Device.startApp` uses `setLaunchDisplayId` plus `IActivityManager.startActivity`.
- **Restrictions.** `ActivityTaskSupervisor.isCallerAllowedToLaunchOnDisplay`:
  - A caller holding **INTERNAL_SYSTEM_WINDOW** gets "allow launch any on display". Shell holds it (in Shell manifests from 10 to 16).
  - Otherwise, on an *untrusted* display the activity needs `allowEmbedded=true` and the caller needs ACTIVITY_EMBEDDING or must already be on the display.
  - Rear displays are refused. Android 16 adds a "display cannot host tasks" check when `ENABLE_DISPLAY_CONTENT_MODE_MANAGEMENT` and `ENABLE_MIRROR_DISPLAY_NO_ACTIVITY` are on. That affects mirror displays only, and ours is own-content.
- `canPlaceEntityOnDisplay` also needs `mSupportsMultiDisplay`, which is true when the device declares **`android.software.activities_on_secondary_displays`** and multi-window is supported (`ActivityTaskManagerService.retrieveSettings`). Check with `adb shell pm list features | grep secondary`. Most Android 10+ GMS phones declare it (UNVERIFIED per OEM).
- **No freeform or desktop setting is needed.** `force_resizable_activities` / `enable_non_resizable_multi_window` (Developer options) only matter if a non-resizable app refuses or letterboxes. On a full-screen virtual display with the phone's size and density, it usually just runs full-screen.
- Background-activity-start limits do not apply: shell holds `START_ACTIVITIES_FROM_BACKGROUND`. Shell **cannot** start non-exported activities. Use launcher or exported activities, or deep links.
- Starting an activity normally moves its display to the top (global focus). With `STEAL_TOP_FOCUS_DISABLED`, `DisplayWindowSettings` sets `dc.mDontMoveToTop = !dc.canStealTopFocus()`, which should keep the user's display on top. Medium confidence; verify with `dumpsys window | grep mTopFocusedDisplayId`.

## 3. Input isolation

- **Injection.** `input -d <displayId> tap|swipe|keyevent|text|draganddrop|press|roll ...` (`InputShellCommand`: `-d` is parsed and the displayId is put on each MotionEvent or KeyEvent). From the server, set `InputEvent.setDisplayId(id)` (hidden, by reflection) and call `InputManager.injectInputEvent(ev, mode)`. scrcpy does exactly this (`wrappers/InputManager.java`, `Device.injectEvent`). This needs INJECT_EVENTS, which shell has.
- **Physical touchscreen.** Injected events target the given display. The physical touchscreen is associated with display 0, so the user's touches never reach the virtual display and injected events never appear on display 0. High confidence.
- **Focus.** Android 10 introduced multiple displays with one "top focused display". `config_perDisplayFocusEnabled` (system resource, off on phones, needs a system image) gives every display its own focus.
  - Without it, `DisplayContent.findFocusedWindowIfNeeded` gives a non-top display a focused window **only if `hasOwnFocus()`**, which means `perDisplayFocusEnabled || Display.FLAG_OWN_FOCUS`.
  - So on **Android 10-13** a background virtual display has *no focused window*. Key or text injection to it is dropped, or waits on a focused application (ANR risk) **until a tap moves that display to the top**. That tap takes global focus away from the user. The user's app stays RESUMED (multi-resume) but loses "top resumed" (`onTopResumedActivityChanged(false)`), and its IME is hidden.
  - On **Android 14+** with `OWN_FOCUS`, the virtual display keeps its own focused window, so key and text injection with `displayId` works while it is in the background.
- **Taps still steal top focus unless `STEAL_TOP_FOCUS_DISABLED` is set.** A pointer-down outside the focused window calls `WMS.handlePointerDownOutsideFocus` -> `WindowState.handleTapOutsideFocusInsideSelf` -> `moveDisplayToTopInternal(displayId)`, which returns early when `!displayContent.canStealTopFocus()`. scrcpy's flag set does **not** include this, so with stock scrcpy every agent tap takes the top focus from the user's WhatsApp or YouTube. **A one-line server fork adds `1<<16`**, and it needs TRUSTED + OWN_FOCUS, so Android 14+.
- Hardware-keyboard-style events (scrcpy `--keyboard=uhid`) go to the *top focused* display. Do not use UHID. Use injected KeyEvents with an explicit displayId.

## 4. IME / keyboard

- There is one IME process. Where it shows is decided per display by `DisplayWindowSettings.getImePolicyLocked`:
  - The default display is LOCAL.
  - Virtual displays default to **`DISPLAY_IME_POLICY_FALLBACK_DISPLAY`**, which means the keyboard pops up **on the user's main screen**. That is the worst leak.
  - The exception is desktop-mode or content-mode displays that have system decorations.
- `IWindowManager.setDisplayImePolicy(displayId, policy)` needs INTERNAL_SYSTEM_WINDOW (shell has it) and **a trusted display** (`WMS.setDisplayImePolicy` throws "Attempted to set IME policy to an untrusted virtual display"). So it is only usable from Android 13+ from shell. Values: `LOCAL=0`, `FALLBACK_DISPLAY=1`, `HIDE=2` (`WindowManager.java`, Android 12+; Android 10/11 used `setShouldShowIme(boolean)`).
- **Recommendation: `HIDE`** for the test display. It never steals the user's keyboard. Type with:
  - (a) `input -d <id> text "..."` or injected KeyEvents (KeyCharacterMap-based, ASCII only, fine for RN `ReactEditText` and native `EditText`), or
  - (b) `AccessibilityNodeInfo.performAction(ACTION_SET_TEXT)`, which UiAutomator2 `setText` uses. It handles Unicode and needs no IME and no focus.
  - `LOCAL` is only needed if you are testing IME behaviour itself (for example a layout resize when the keyboard opens). The IME is a single instance, so it would move away from the user's screen while it shows. **UNVERIFIED** how the IME behaves when both the user's app and the test app request it at the same time. Expect them to fight.
- Flutter: text fields accept hardware key events and ACTION_SET_TEXT through semantics. Behaviour with `HIDE` is **UNVERIFIED**.

## 5. Lifecycle and leakage

- **Multi-resume (Android 10+).** "all activities remain in the RESUMED state" in multi-window or multi-display. The top focused display holds the single "top resumed" activity. The app on the virtual display stays RESUMED while the user uses display 0 (developer.android.com, *Support multi-window mode*). `onStop` happens only if its display turns off (null Surface, or a sleep token).
- **Screen off or lock.** With `OWN_DISPLAY_GROUP` + `ALWAYS_UNLOCKED` (13+), the virtual display is in its own power group and keyguard does not cover it. scrcpy calls `PowerManager.userActivity(displayId)` to keep it awake. Whether the app keeps rendering while the phone is locked in a pocket is **UNVERIFIED** and probably OEM-dependent. It is also a security consideration: an always-unlocked display lets automation run while the device is locked.
- **Leaks to the user (non-root, cannot be fully fixed):**
  - **Audio**: one global mixer, so the test app's sound plays on the phone. Mitigation: `adb shell appops set <pkg> PLAY_AUDIO ignore` (and `TAKE_AUDIO_FOCUS ignore`) so it does not duck or pause the user's YouTube. Medium confidence.
  - **Vibration**: `appops set <pkg> VIBRATE ignore`.
  - **Notifications and heads-up**: these appear in the default display's status bar. Mitigation: `cmd notification` snoozing, or deny POST_NOTIFICATIONS on 13+, but that changes the app under test.
  - **Toasts**: they follow the context's display, so they appear on the virtual display. Medium.
  - **Runtime-permission dialogs** (`GrantPermissionsActivity`) are activities launched by the app, so they open in its task on the virtual display. Medium-High. Pre-grant with `pm grant` to avoid them.
  - **ANR, crash and some system alerts** may show on the default display. **UNVERIFIED**.
  - **Camera and mic** are exclusive. "Top resumed" arbitration (`onTopResumedActivityChanged`) can make the user's camera app lose its camera.
  - **Clipboard** is global.
  - **IME**: see section 4.
- **FLAG_SECURE apps** (banking, some RN apps using `react-native-screenshot-prevent`) render **black** in captures and screencap, because the display is not secure and shell cannot create secure displays since Android 12. The accessibility tree still works.

## 6. Observation

- **Screenshots.**
  - (a) **Best**: read your own `ImageReader` in the `app_process` service: `acquireLatestImage` -> PNG/JPEG -> socket. Zero dependence on screencap quirks, any Android 10+.
  - (b) `adb exec-out screencap -p -d <SF-display-id>`. `-d` takes a **SurfaceFlinger** display id, not the logical id. Android 16's `screencap.cpp` parses it with `DisplayId::fromValue` (any id, including virtual), after an AOSP change titled "screencap: Allow virtual display ID in -d switch". Older builds only accept physical ids. Find SF ids with `dumpsys SurfaceFlinger --display-id` / `--displays`. Medium.
  - (c) The Appium UiAutomator2 `mobile: screenshots` command takes a physical or virtual display id; Appium notes emulator virtual-display screenshots work only on API 34+.
- **UI hierarchy.**
  - `UiAutomation.getWindowsOnAllDisplays()` (API 30) returns `SparseArray<List<AccessibilityWindowInfo>>` keyed by displayId, and `AccessibilityWindowInfo.getDisplayId()` gives each window's display. This needs `FLAG_RETRIEVE_INTERACTIVE_WINDOWS`.
  - Accessibility tracks public displays and *trusted* private displays (`AccessibilityManagerService.isValidDisplay`).
  - **Appium UiAutomator2 driver**: settings `currentDisplayId=<logical id>` + `enableMultiWindows=true` scope lookups, page source, screenshots and **coordinate gestures** to that display. Supported "since Android 11 (API 30)". `mobile: listDisplays` lists them.
  - So Appium + UiAutomator2 can be the hierarchy and actions layer with no fork. RN exposes `testID` as resource-id/content-desc. Flutter needs semantics, which become active when an a11y client such as UiAutomation connects.
  - `adb shell uiautomator dump` on a non-default display: **UNVERIFIED**. Older builds dump only the active window. Use UiAutomation or Appium instead.

## 7. Root vs non-root matrix

| Need | Non-root shell | Root / system signature / ROM change |
|---|---|---|
| Trusted virtual display, IME policy, own focus, no focus stealing | Yes on 13+ (focus isolation on 14+) | Not needed |
| Android 10-12: trusted display, IME policy | **No** (shell lacks ADD_TRUSTED_DISPLAY) | Root (run as system uid) |
| Secure display (FLAG_SECURE content visible) | No | Root / system uid (CAPTURE_SECURE_VIDEO_OUTPUT) |
| Global per-display focus (`config_perDisplayFocusEnabled`) | No | RRO overlay in a system image or Magisk |
| Separate audio routing per display | No (appops mute only) | System audio policy; *maybe* VirtualDeviceManager (Shell has CREATE_VIRTUAL_DEVICE + ASSOCIATE_COMPANION_DEVICES on 14-16 for CTS). **UNVERIFIED** from `app_process`. Worth a spike: VDM gives per-device audio, sensors and clipboard policy. |
| Survive reboots / Wi-Fi changes without the host | No (wireless debugging turns off on reboot, and Android 11+ pairing is per network) | Root, or `adb tcpip` after USB (still lost on reboot) |
| Hide the test display from other apps entirely | Mostly (private + trusted) | n/a |

**OEM breakage (from scrcpy FAQ and community reports; per-device behaviour UNVERIFIED here):**
- Xiaomi MIUI/HyperOS: input injection needs "USB debugging (Security settings)".
- OPPO/realme ColorOS: "Disable permission monitoring".
- Some ROMs show their own launcher or desktop on a decorated virtual display (scrcpy added `--no-vd-system-decorations` for "broken UIs or unwanted default launchers").
- Samsung One UI may treat public displays specially (DeX). **UNVERIFIED**.
- Android 16 "Advanced Protection" mode can block USB/ADB debugging.
- OEMs could strip ADD_TRUSTED_DISPLAY from Shell. **UNVERIFIED**.

## 8. Minimal 1-hour PoC (non-rooted phone, Android 14+ preferred)

Prerequisites: scrcpy >= 3.1 on the PC (current is 5.0.1), Developer options -> Wireless debugging on, and phone and PC on the same Wi-Fi.

```bash
# 0. Pair and connect (Android 11+ wireless debugging)
adb pair <phone-ip>:<pair-port>          # enter the 6-digit code shown on the phone
adb connect <phone-ip>:<debug-port>
adb shell getprop ro.build.version.sdk
adb shell pm list features | grep activities_on_secondary_displays

# 1. Create the virtual display and start the app on it (keep this terminal open).
#    Remove --no-window for the first run if you want to watch it on the PC.
scrcpy -s <phone-ip>:<debug-port> --new-display=1080x2400/420 \
       --start-app=com.example.app --no-vd-system-decorations \
       --display-ime-policy=hide --no-audio --no-window
#    The log prints: "New display: 1080x2400/420 (id=N)"

# 2. Confirm the display, the app on it, and who has global focus
adb shell dumpsys display | grep -E "mDisplayId|scrcpy"
adb shell dumpsys activity activities | grep -E "Display #|ResumedActivity|mResumedActivity"
adb shell dumpsys window | grep -E "mTopFocusedDisplayId|mCurrentFocus|mFocusedApp"

# 3. While you use WhatsApp/YouTube on the phone by hand, inject input to display N only
adb shell input -d N tap 540 1200
adb shell input -d N swipe 540 1800 540 600 300
adb shell input -d N text "hello"
adb shell input -d N keyevent KEYCODE_BACK
adb shell dumpsys window | grep mTopFocusedDisplayId   # expect it to flip to N with stock scrcpy (focus steal)

# 4. Screenshot the virtual display
adb shell dumpsys SurfaceFlinger --display-id          # physical ids; try --displays for virtual ones
adb exec-out screencap -p -d <SF-id> > vd.png           # may fail on older builds -> use the scrcpy window / --record instead
# alternative: scrcpy ... --record=vd.mp4 and extract a frame

# 5. UI hierarchy of the virtual display (Appium UiAutomator2 driver)
#    settings: {"enableMultiWindows": true, "currentDisplayId": N}; then getPageSource / findElement / W3C taps

# 6. Leak checks
adb shell appops set com.example.app PLAY_AUDIO ignore
adb shell dumpsys input_method | grep -E "mCurFocusedWindow|displayId"
```

**Pass criteria:**
1. The app renders and responds on display N while you use another app on the screen.
2. Your touches never land on display N, and injected taps never land on your screen.
3. Typed text reaches the test app's field while your keyboard is not hijacked (`--display-ime-policy=hide`).
4. Screenshots and the hierarchy come from display N.

**Expected stock-scrcpy failure to note:**
- `mTopFocusedDisplayId` flips to N on each injected tap. Your WhatsApp keyboard may close and "top resumed" moves.
- That is the gap the forked server closes by adding `VIRTUAL_DISPLAY_FLAG_STEAL_TOP_FOCUS_DISABLED (1<<16)` next to `OWN_FOCUS` in `NewDisplayCapture.startNew` (Android 14+). Run that fork as **PoC step 2**.

## Key sources

- scrcpy: `doc/virtual-display.md`; `server/src/main/java/com/genymobile/scrcpy/video/NewDisplayCapture.java`; `wrappers/DisplayManager.java`; `wrappers/InputManager.java`; `device/Device.java` (`startApp`, `injectEvent`, `keepActive`); `Server.java` (API 29 gate); man page for scrcpy 5.0.1 (man.archlinux.org/man/scrcpy.1.en)
- AOSP (android.googlesource.com/platform/frameworks/base, branch android16-qpr2-release unless noted):
  - `services/core/java/com/android/server/display/DisplayManagerService.java` (`createVirtualDisplayInternal`)
  - `.../display/VirtualDisplayAdapter.java` (flag translation, null Surface -> STATE_OFF)
  - `core/java/android/hardware/display/DisplayManager.java` (flag values; STEAL_TOP_FOCUS_DISABLED present at android-14.0.0_r1 and later)
  - `packages/Shell/AndroidManifest.xml` (tags android-10 to 16)
  - `core/res/AndroidManifest.xml` (ADD_TRUSTED_DISPLAY `signature|role`)
  - `services/core/java/com/android/server/wm/ActivityTaskSupervisor.java` (`isCallerAllowedToLaunchOnDisplay`, `canPlaceEntityOnDisplay`)
  - `.../wm/ActivityTaskManagerService.java` (`mSupportsMultiDisplay`)
  - `.../wm/WindowManagerService.java` (`setDisplayImePolicy`, `moveDisplayToTopInternal`, `handlePointerDownOutsideFocus`, `mPerDisplayFocusEnabled`)
  - `.../wm/WindowState.java` (`handleTapOutsideFocusInsideSelf`)
  - `.../wm/DisplayContent.java` (`hasOwnFocus`, `canStealTopFocus`, `findFocusedWindowIfNeeded`)
  - `.../wm/DisplayWindowSettings.java` (`getImePolicyLocked`, `mDontMoveToTop`)
  - `services/accessibility/.../AccessibilityManagerService.java` (`isValidDisplay`)
  - `cmds/screencap/screencap.cpp`; `services/core/java/com/android/server/input/InputShellCommand.java`
- source.android.com/docs/core/display/multi_display/displays ("Per-display focus")
- developer.android.com/develop/ui/views/layout/support-multi-window-mode (multi-resume, top-resumed)
- appium.github.io/appium-uiautomator2-driver/latest/guides/multiwindow/ (`currentDisplayId`, API 30+)
- CVE-2020-0440 / AOSP CTS "Test that trusted display cannot be created without permission" (history of the ADD_TRUSTED_DISPLAY gate)
