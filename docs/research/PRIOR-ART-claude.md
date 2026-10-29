# Prior art: headless Android automation on a physical phone via virtual display, driven by AI agents
Researched 2026-10-29 (gh CLI + web search; READMEs read for the top ~12). Stars/dates from the GitHub API at research time. Caveat: gh code search returned nothing (no auth scope) and gh search hit a rate limit mid-run, so coverage of tiny repos is not exhaustive.

## Ranked table
| Repo | Stars | Last push | License | What it does | Overlap | Non-root? | Notes |
|---|---|---|---|---|---|---|---|
| kmod-midori/Mua | 3 | 2026-10-22 | NONE (no LICENSE file = all rights reserved) | Android app + Shizuku; MCP server on the phone (Streamable HTTP, bearer token); tools: display_start/list/stop, launch app, screenshot, touch/key input on separate virtual displays; works with screen off (wake lock); optional central MCP gateway for many devices; `display-control` lib | **Large (~70% of the idea's runtime)** | Yes (Shizuku via ADB; Android 12+) | Closest to "agent drives apps on a virtual display while owner uses phone". No test-framework layer; no confirmed per-display UI hierarchy; no test/bug-report workflow. Unlicensed so cannot be forked. |
| lejw0925/android-virtual-screen | 26 | 2026-10-24 | PolyForm Noncommercial 1.0.0 | Android app creating virtual displays for agents; authenticated MCP, 19 tools (control lease, display, app, observe via node tree or screenshot, input, wait conditions), stale-observation IDs, PiP preview, user takeover; Root or Shizuku/Stellar; accessibility service for node targeting | **Large** | Yes with Shizuku (Android 13+) | Most "framework-like" (leases, observation IDs, receipts). Noncommercial licence, not OSI open source. |
| QY-25123/PhoneAgent | 2 | 2026-10-28 | none stated | Claude agent operating Gmail/WeChat/Maps/DoorDash on an invisible virtual display via Shizuku UserService; STEAL_TOP_FOCUS_DISABLED so keyboard/focus/back stay with the user; accessibility tree + screenshot fallback, hard safety blocks, 240+ unit tests, live SurfaceView preview | Large (agent product, not a test framework) | Yes (Shizuku) | Good reference for focus/IME isolation. No licence. |
| imoonkey/closepaw | 57 | 2026-06-05 | Apache-2.0 | On-device phone-use agent; accessibility mode or background mode on a virtual display (Shizuku); ReAct harness, skills, traces, AndroidWorld eval loop | Large (on-device agent, not PC-driven, not a test framework) | Yes (Shizuku optional) | Apache-2.0: reusable. |
| iamr0s/Ruto-GLM | 732 | 2026-01-11 | Apache-2.0 (per README) | Shizuku app; create virtual screens, run apps there (multi-instance), run Open-AutoGLM tasks on main or virtual screen "without interfering"; desktop-like multi-window manager | Large | Yes (Shizuku) | Reusable virtual-display code. |
| firerpa/lamda | 8690 | 2026-09 | MIT | Android device-control platform: on-device server, Python client, built-in MCP + natural-language `agent`; **Virtual Display API (`vd.xxx` mirrors `d.xxx`)**, watchers per virtual display, multi-display WebUI; root or non-root (Shizuku APP deploy) | Large (closest on the "Playwright-like API" axis) | Claimed yes; vd specifically unverified | Mature and MIT, but heavy all-in-one (Frida/MITM/VPN). Verify the non-root VD claim on your phone. |
| Genymobile/scrcpy | 153466 | 2026-10-26 | Apache-2.0 | `--new-display[=WxH/dpi]`, `--start-app`, `--list-apps`, resizable flex display (4.0), keeps app alive by moving it to the main display on exit (3.1); injects input to the virtual display | Building block (display + input + capture) | **Yes** | The proven non-root recipe: VirtualDisplay created from app_process as shell. |
| HackingByJT/appbridge-usb | 1 | 2026-10-24 | Apache-2.0 | Windows launcher opening a phone app on a scrcpy virtual display | Partial | Yes | Same family (all under 20 stars, human use, no AI): scrcpy-vd-launcher, appcast, dex-for-mac, DeXterous, android-desk, scrcpy-app-launcher, scrcpy-desktop-launcher. |
| mobile-next/mobile-mcp | 10103 | 2026-10-26 | Apache-2.0 | MCP for iOS/Android real devices and emulators; accessibility snapshots + coordinate taps | Building block (MCP/tool surface); no virtual display | Yes | Main display only. Could be extended with displayId. |
| droidrun/mobilerun | 9863 | 2026-10-28 | MIT | LLM-agnostic mobile agent via natural language | Partial (agent loop) | Yes | README has no virtual display mention. |
| openatx/uiautomator2 | 8455 | 2026-10-23 | MIT | Python wrapper for UiAutomator2 | Building block | Yes | Per-display hierarchy needs work (see Gap). |
| appium/appium-uiautomator2-driver (+server) | 893 / 413 | 2026-10 | Apache-2.0 | Appium Android driver | Building block (W3C API, ecosystem) | Yes | No documented virtual display support. |
| zai-org/Open-AutoGLM and forks (suyiiyii/AutoGLM-GUI, Luokavin/AutoGLM-For-Android, butlanys/Open-AutoGLM-Android) | 26501 (main) | 2026-03 | Apache-2.0 (main/GUI) | Phone-agent model/framework over ADB or Shizuku | Partial (agent loop) | Yes | Virtual display only via Ruto. |
| TencentQQGYLab/AppAgent, X-PLUG/MobileAgent, MobileLLM/AutoDroid, honeynet/droidbot | 6912 / 9340 / 504 / 994 | varied | MIT | Research LLM agents / test input generators over ADB | Partial | Yes | Main display only. |
| JuanCF/scrcpy-mcp | 125 | 2026-09 | MIT | MCP over ADB + scrcpy (screenshots/control) | Building block | Yes | README does not mention new-display; natural fork target. |
| CursorTouch/Android-MCP, minhalvp/android-mcp-server, tanbro/uiautomator2-mcp-server, AlexGladkov/claude-in-mobile, callstack/agent-device | 907 / 811 / 54 / 381 / 5183 | 2025-26 | MIT / Apache | Android MCP servers over ADB/uiautomator2 | Partial | Yes | None mention displays. |
| danielealbano/android-remote-control-mcp | 760 | 2026-10 | NOASSERTION | MCP server running on the phone | Partial | Accessibility based | Main display. |
| RikkaApps/Shizuku | 32357 | 2025-06 | Apache-2.0 | Run code as shell uid via wireless ADB | Building block | Yes | The enabling technique. |
| budtmo/docker-android, Tongyi-MAI/MobileWorld | 16054 / 298 | 2026-10 | - | Emulator container with MCP; mobile-agent benchmark | None (emulator) | n/a | |
| wuyhong715/rikkahub-agent-pure PR #254 | - | - | - | Proposed "virtual display tools: run apps off-screen without stealing foreground" | Partial | - | Shows the pattern is spreading. |

## Closest existing match
Yes: roughly 70-80% of the idea's runtime already exists, several times over, since late 2025. **Mua** (MCP + Shizuku + multiple virtual displays + screenshot/touch/key + screen-off + multi-device gateway) and **android-virtual-screen** (same plus leases, node-tree observation, wait conditions, takeover, PiP) are essentially "agent gets its own invisible Android screen while the owner keeps the phone". **PhoneAgent** shows focus/IME/back-key isolation with STEAL_TOP_FOCUS_DISABLED. **lamda** offers a `vd.*` mirror API plus MCP under MIT.

Caveats: Mua and PhoneAgent have no licence (cannot be forked); android-virtual-screen is PolyForm Noncommercial. They are phone-side apps (Shizuku UserService), not a "scrcpy-server style app_process pushed over wireless ADB" controller, and none presents itself as a Playwright-style testing framework (test runner, assertions, traces, bug reports, RN/Flutter awareness).

## Building blocks to reuse/fork (open-source compatible)
- scrcpy (Apache-2.0): server code for VirtualDisplay creation via app_process, input injection, capture. Best non-root base.
- Shizuku (Apache-2.0): alternative privileged host.
- Ruto-GLM (Apache-2.0) and ClosePaw (Apache-2.0): Shizuku virtual display code, multi-window management, agent loop.
- lamda (MIT): virtual display API shape; read for non-root behaviour.
- mobile-mcp (Apache-2.0), scrcpy-mcp (MIT), uiautomator2 (MIT), Appium UiAutomator2 server (Apache-2.0): MCP/tool surface and UI hierarchy dumping; extend with displayId.
- Study only (no or unsuitable licence): Mua, PhoneAgent, android-virtual-screen. Apache-2.0 + MIT mix is fine for an Apache-2.0 project.

## Gap (not found anywhere)
- A **Playwright-style test framework** on top of virtual displays: locator/auto-wait API, assertions, test runner, trace/video per display, auto bug reports. Existing work is agent products or raw MCP.
- A **PC-driven, wireless-ADB, scrcpy-style app_process server** exposing per-display UiAutomator/accessibility hierarchy (existing ones use Shizuku apps + accessibility service; uiautomator2/Appium have no displayId support).
- A documented **non-root capability matrix** per Android version/OEM (trusted display flags, IME on secondary display, onPause/onStop lifecycle on virtual display, FLAG_SECURE, OEM restrictions).
- React Native/Flutter-specific hooks (dev menu, Metro, semantics tree) on a virtual display.
- A permissively licensed, maintained consolidation: the best implementations are unlicensed or noncommercial.
