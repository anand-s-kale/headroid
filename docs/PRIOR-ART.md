# Prior art and credits

Who did related work before us, what headroid takes from each, and under which licence.
Research behind this list: [research/PRIOR-ART-claude.md](research/PRIOR-ART-claude.md) and [research/REVIEW-gemini.md](research/REVIEW-gemini.md).

## Foundations we build on (reusable, credited in NOTICE when code is used)

| Project | Licence | How headroid uses it |
|---|---|---|
| [Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) | Apache-2.0 | Base of the device server: `app_process` launch, hidden `DisplayManager` access, `--new-display`, input injection with display ids, display IME policy |
| [RikkaApps/Shizuku](https://github.com/RikkaApps/Shizuku) | Apache-2.0 | Reference for running privileged shell-uid services; possible on-phone mode later |
| [appium/appium-uiautomator2-driver](https://github.com/appium/appium-uiautomator2-driver) | Apache-2.0 | `currentDisplayId` / multi-window hierarchy approach (Android 11+) |
| [openatx/uiautomator2](https://github.com/openatx/uiautomator2) | MIT | Locator and selector design |
| [microsoft/playwright](https://github.com/microsoft/playwright) | Apache-2.0 | API shape: locators, auto-wait, `expect`, traces, test runner |
| [AOSP](https://source.android.com/) | Apache-2.0 | Primary source of truth for display, input, focus and IME behaviour |

## Related projects (studied for ideas; no code used)

| Project | Licence | What it showed us |
|---|---|---|
| [kmod-midori/Mua](https://github.com/kmod-midori/Mua) | none | On-phone MCP server with virtual-display tools for agents |
| [QY-25123/PhoneAgent](https://github.com/QY-25123/PhoneAgent) | none | Keeping keyboard and back-key focus with the user while an agent works |
| [lejw0925/android-virtual-screen](https://github.com/lejw0925/android-virtual-screen) | PolyForm Noncommercial | Control lease, wait conditions and user takeover as agent tools |
| [imoonkey/closepaw](https://github.com/imoonkey/closepaw) | Apache-2.0 | Agent on a Shizuku virtual display |
| [iamr0s/Ruto-GLM](https://github.com/iamr0s/Ruto-GLM) | Apache-2.0 | AutoGLM tasks on virtual screens |
| [firerpa/lamda](https://github.com/firerpa/lamda) | MIT (client) | Virtual-display API mirroring the main-display API |
| [mobile-next/mobile-mcp](https://github.com/mobile-next/mobile-mcp) | Apache-2.0 | MCP tool design for mobile (main display only) |
| [mobile-dev-inc/maestro](https://github.com/mobile-dev-inc/maestro) | Apache-2.0 | Auto-waiting, flake-tolerant mobile test runner design |
| [AirtestProject/Airtest](https://github.com/AirtestProject/Airtest) | Apache-2.0 | Cross-OEM capture and hierarchy handling |
| [farmerbb/Taskbar](https://github.com/farmerbb/Taskbar) | Apache-2.0 | Early non-root secondary-display launching |

Licences were read on 2026-10-29. Check them again before reusing any code.
If you maintain one of these projects and something here is inaccurate, please open an issue.
