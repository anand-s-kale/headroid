# headroid

**Headless Android app testing on your real phone, while you keep using it.**

headroid is an open-source, Playwright-style automation framework for native Android apps. It runs the app under test on a
**hidden virtual display** of a real, non-rooted phone, driven from your computer over **wireless ADB**. Taps, typing,
screenshots and UI inspection all target that hidden display, so the phone's real screen stays yours: WhatsApp, YouTube
and Instagram keep working while an AI agent or a test suite exercises your app in the background.

> **Status: alpha, works on a real phone.** The device server and Python SDK run end to end on a POCO F6
> (Android 16, HyperOS) over USB and wireless adb: hidden display, app launch, taps and typing, screenshots, UI tree,
> sound/vibration muting and clean teardown after crashes. Other phones are untested so far:
> [report yours](../../issues/new?template=device_report.yml). See the [roadmap](docs/ROADMAP.md).

## Try it in 2 minutes

```
pip install --pre headroid                      # alpha; the server jar is inside the package
headroid doctor                                 # checks adb, the phone and the server, with a fix for each problem
headroid launch com.your.app --screenshot shot.png
```

```python
from headroid import Device

with Device.connect() as dev:
    d = dev.create_display()          # hidden: nothing appears on your screen
    d.launch("com.your.app")          # sound and vibration muted until the session ends
    d.click(text="Sign in")           # waits until the element has settled, then taps it
    d.fill("me@example.com", rid="email")
    d.wait_for(text="Welcome")
    d.screenshot("welcome.png")
```

Full guide: [packages/headroid](packages/headroid/README.md). Xiaomi/Redmi/POCO need two extra switches in Developer
options; `headroid doctor` tells you which.

## Use with an AI agent (recommended: `headroid[artemis]`)

> New in 0.1.0a4. Verified on a POCO F6: a Claude Code session signed in to the sample app on the hidden display
> by itself, while the owner's screen kept focus.

Let Claude (or any MCP client) drive your app on the hidden display. The client does the thinking, so **no LLM API
key is needed**.

```
pip install --pre "headroid[artemis]"          # Python 3.12+; pulls headroid-artemis, the ARTEMIS fork
claude mcp add headroid -- headroid mcp        # Claude Code
```

Claude Desktop: add this to `claude_desktop_config.json` (with several devices attached, use
`"args": ["mcp", "--serial", "<serial>"]`):

```json
{"mcpServers": {"headroid": {"command": "headroid", "args": ["mcp"]}}}
```

`headroid mcp` starts the fork's MCP server with only three tools:

| Tool | What it does |
|---|---|
| `mobile_observe` | Screenshot plus a numbered element list of the hidden display (the screenshot is also returned inline, so Claude Desktop sees it) |
| `mobile_act` | One action by element number: click, long_press, input_text, click_sequence, swipe, press_key, manage_app, wait_for_delay, wait_for_text, erase_one_char, focus_and_clear_text, open_link (opens the link on the hidden display with the one app that handles it, sound and vibration muted and stopped at the end like `manage_app`; notifications are not blocked; refused when no app handles it, when Android would ask which app to use, or while that app is open on the phone's own screen) |
| `mobile_session_end` | Closes the hidden display |

The fork's other ARTEMIS tools are not exposed. Under headroid, `press_key` only sends editing and navigation keys
(back, enter, delete, forward delete, tab, space, escape, move home/end, D-pad, menu) and printable characters; HOME,
APP_SWITCH, POWER, volume, call, media, camera and every other key are refused. `execute_shell` only allows
`getprop`, `pm list packages`, `pm path` and `am start` on the hidden display. `open_link` needs a URL with a
scheme and refuses `intent`, `android-app`, `file`, `content`, `data`, `javascript`, `about`, `tel`, `sms`, `smsto`, `mms`, `mmsto`, `mailto`, `voicemail`, `geo`, `market` links. `manage_app` refuses to launch an app whose
start activity is singleTask or singleInstance while the app is open on the phone's own screen (Android would
move that task instead of opening the app on the hidden display). headroid mcp never changes the phone's
settings and turns off ARTEMIS's keep-awake service, which would wake the phone's own screen.
The agent sees the text of the fields in the app under test, password fields included, because Android's accessibility
layer exposes it: do not test with real credentials.
On Xiaomi/HyperOS set the app under test to Battery saver "No restrictions", or it freezes with the screen off
(headroid then returns error `-32014` naming the fix).

> **Warning:** `headroid-artemis` and the unrelated PyPI package `artemis` both install the import name `artemis`.
> Never put them in the same environment.

---

## Why

| Today | With headroid |
|---|---|
| Emulators are slow, miss real-device bugs, and eat RAM | Tests run on the phone you already own |
| Cloud device farms cost money and add latency | Free, local, over Wi-Fi |
| Appium / UiAutomator / Maestro take over the phone's screen | The app under test runs on a separate, invisible display |
| AI phone agents drive the main screen, so you can't use the phone | The agent works in the background; you keep the foreground |

Think of it as **Chrome Headless, but for native Android apps on a physical device.**

## Goal

1. A **Playwright-like API** for Android: locators with auto-wait, actions, assertions, a test runner, traces and video.
2. **Background isolation:** the app under test lives on its own virtual display with its own input and focus. Nothing
   touches the physical touchscreen.
3. **AI-agent ready:** an MCP server so Claude, Codex, Gemini and other agents can launch, inspect, act, and file bug
   reports with screenshots.
4. **Honest capabilities:** a published, tested [capability matrix](docs/CAPABILITY-MATRIX.md) per Android version and
   phone brand, stating what works without root and what doesn't.
5. **Framework coverage:** native Android and React Native first, Flutter later.

## Built from the best of open source

headroid doesn't reinvent Android automation. It combines existing open-source tools and adds the missing piece:
**running them on a hidden display**, so the phone stays yours.

| Layer | Comes from |
|---|---|
| Agent "brain" (plan, act, check, report) | [ARTEMIS](https://github.com/google/artemis) and [mobile-use](https://github.com/minitap-ai/mobile-use), plugged in via drivers |
| Hidden display, input, focus guard | [scrcpy](https://github.com/Genymobile/scrcpy) server, extended |
| UI tree, selectors, ADB | [uiautomator2](https://github.com/openatx/uiautomator2), [adbutils](https://github.com/openatx/adbutils), Appium's multi-display approach |
| Test API | Modelled on [Playwright](https://github.com/microsoft/playwright) |

How each one is mixed in (adapted, used as a dependency, or plugged in) is in
[ADR 0003](docs/adr/0003-compose-open-source-stack.md). Credits are in [NOTICE](NOTICE).

## How it works

```
ARTEMIS · mobile-use · test scripts · any MCP agent
        │  Python SDK · test runner · CLI · MCP server     (your computer)
        ▼
headroid controller ──── wireless ADB (adb pair / connect) ────┐
                                                                ▼
                                       headroid device server  (app_process, shell uid, no root)
                                        ├─ creates a hidden VirtualDisplay (trusted, own focus)
                                        ├─ launches the app under test on that display
                                        ├─ injects touch / key / text to that displayId only
                                        ├─ captures frames from its own ImageReader
                                        └─ reads the per-display accessibility tree
                                                                ▼
                                       App under test on display N (invisible)
                                       Physical display 0 → stays the owner's
```

The device server starts from [scrcpy](https://github.com/Genymobile/scrcpy)'s Apache-2.0 server, which already proves that
a non-root shell process can create a virtual display, launch apps on it and inject input into it. headroid adds the
missing pieces: focus-steal protection, keyboard isolation, per-display UI trees, a test API, and agent tools.
Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What works

Verified on a POCO F6 (Android 16, HyperOS); other phones are expected to behave alike on Android 14+ but are
untested. Details per device: [capability matrix](docs/CAPABILITY-MATRIX.md).

| Capability | POCO F6, Android 16 | Notes |
|---|---|---|
| Hidden virtual display + launch any app on it | ✅ verified | Trusted display needs Android 13+ |
| Taps, swipes, keys, text only on the hidden display | ✅ verified | Physical touchscreen unaffected |
| Owner keeps focus and keyboard while tests type | ✅ verified | 26/26 samples while the owner typed; Android 14+ only |
| Screenshots and UI tree of the hidden display | ✅ verified | ~0.1–0.2 s per screenshot over Wi-Fi |
| Toasts, dialogs, permission prompts stay hidden | ✅ verified | |
| Owner's phone stays smooth | ✅ verified | Instagram: 0 janky frames with taps, screenshots or UI reads every second; owner felt no lag |
| Sound and vibration muted | ✅ verified | per app (app-ops), restored after the session, also after a crash |
| Notifications | ⚠️ opt-in | reach the owner unless `mute_notifications=True` |
| Wi-Fi drop during a session | ✅ verified | the server outlives the adb connection; the host reconnects (6 s in the test) and resends reads |
| Clean teardown after host or server crash | ✅ verified | nothing left on the phone after the 60 s grace period |
| Several sessions on one phone | ✅ verified | separate server, socket and mute records; one never kills an app another uses |
| Your own copy of the app under test | ✅ verified | not force-stopped at the end when it was already running (only the hidden screen closes) |
| Appium / `uiautomator` / Maestro alongside | ⚠️ | they share one UiAutomation with headroid: it is held only while reading the screen (released after 5 s idle) and waited for up to 10 s |
| Apps with `FLAG_SECURE` (banking) | ❌ | screenshots are black without root |

You can help by [reporting your device](../../issues/new?template=device_report.yml).

## Planned API (draft)

```python
from headroid import android, expect

device = android.connect("192.168.1.20:37099")
page = device.launch("com.example.shop", display="hidden", size="1080x2400")

page.get_by_text("Sign in").tap()
page.get_by_hint("Phone number").fill("9876543210")
expect(page.get_by_text("Welcome")).to_be_visible()
page.screenshot(path="welcome.png")

page.close()   # tears down the hidden display; the phone is untouched
```

Run an ARTEMIS agent in the background instead of on your screen (planned):

```python
from headroid.integrations.artemis import HeadroidDriver   # an ARTEMIS BaseDeviceDriver
driver = HeadroidDriver(device="192.168.1.20:37099", display="hidden")
# Pass the driver to ARTEMIS: Flash/Pro tasks now run on display N while you use the phone.
```

## Repository layout

| Path | What lives there |
|---|---|
| [`device-server/`](device-server/) | On-device server (Java, `app_process`), derived from scrcpy-server |
| [`packages/`](packages/) | Host side: Python SDK, CLI, test runner, MCP server (TypeScript client later) |
| [`integrations/`](integrations/) | Drivers that run ARTEMIS and mobile-use on the hidden display |
| [`examples/`](examples/) | Sample tests for native and React Native apps |
| [`docs/`](docs/) | Architecture, roadmap, capability matrix, decision records, research |

## Credits and prior art

headroid stands on the shoulders of these projects. Full list and how each is used:
[docs/PRIOR-ART.md](docs/PRIOR-ART.md).

- **[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy)** (Apache-2.0): the device-server foundation (virtual display, input injection).
- **[google/artemis](https://github.com/google/artemis)** (Apache-2.0): AI agent brain, driver interface, diagnosis; first integration target.
- **[minitap-ai/mobile-use](https://github.com/minitap-ai/mobile-use)** (Apache-2.0): AI agent for real Android/iOS apps; ARTEMIS builds on it too.
- **[openatx/adbutils](https://github.com/openatx/adbutils)** (MIT): Python ADB client.
- **[RikkaApps/Shizuku](https://github.com/RikkaApps/Shizuku)** (Apache-2.0): reference for shell-privilege techniques.
- **[appium/appium-uiautomator2-driver](https://github.com/appium/appium-uiautomator2-driver)** (Apache-2.0) and **[openatx/uiautomator2](https://github.com/openatx/uiautomator2)** (MIT): per-display UI hierarchy and locator ideas.
- **[microsoft/playwright](https://github.com/microsoft/playwright)** (Apache-2.0): the API design we aim to feel like.
- Projects that showed AI agents on Android virtual displays: [Mua](https://github.com/kmod-midori/Mua),
  [PhoneAgent](https://github.com/QY-25123/PhoneAgent), [android-virtual-screen](https://github.com/lejw0925/android-virtual-screen),
  [ClosePaw](https://github.com/imoonkey/closepaw), [Ruto-GLM](https://github.com/iamr0s/Ruto-GLM), [lamda](https://github.com/firerpa/lamda).
  We studied their *ideas* only. headroid contains **no code** from projects that are unlicensed or non-commercial.
  See our [clean-room policy](docs/CLEAN-ROOM.md).

## Contributing

Contributions are welcome, especially device reports. Read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[clean-room policy](docs/CLEAN-ROOM.md) first. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Responsible use

headroid drives a phone through ADB, which has wide access to the device. Use it only on devices you own or are
authorised to test. See [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for third-party attributions.
