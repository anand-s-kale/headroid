# headroid

**Headless Android app testing on your real phone, while you keep using it.**

headroid is an open-source, Playwright-style automation framework for native Android apps. It runs the app under test on a
**hidden virtual display** of a real, non-rooted phone, driven from your computer over **wireless ADB**. Taps, typing,
screenshots and UI inspection all target that hidden display, so the phone's real screen stays yours: WhatsApp, YouTube
and Instagram keep working while an AI agent or a test suite exercises your app in the background.

> **Status: pre-alpha.** The research is done ([docs/research](docs/research/SUMMARY.md)). No runnable code yet.
> The first milestone is a proof of concept on real phones. See the [roadmap](docs/ROADMAP.md).

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

## What we expect to work (to be verified on devices)

| Capability | Non-root | Notes |
|---|---|---|
| Hidden virtual display + launch any app on it | ✅ Android 10+ | Trusted display needs Android 13+ |
| Taps, swipes, keys only on the hidden display | ✅ | Physical touchscreen unaffected |
| Keep user's focus/keyboard while agent taps | ⚠️ Android 14+ | `STEAL_TOP_FOCUS_DISABLED`; dialogs/launches can still leak |
| Keyboard hidden on the test display, text injected directly | ⚠️ Android 13+ | Shared IME service; measure interference |
| Screenshots / video of the hidden display | ✅ | From our own ImageReader |
| UI tree of the hidden display | ✅ Android 11+ | Accessibility windows per display |
| Apps with `FLAG_SECURE` (banking) | ❌ | Screenshots are black without root |
| Separate audio / notifications | ❌ | Shared with the owner; mute per app |

Everything above is **unverified on hardware** until the [capability matrix](docs/CAPABILITY-MATRIX.md) says otherwise.
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
