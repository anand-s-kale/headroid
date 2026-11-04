# headroid + ARTEMIS (manual mode) MCP: design

Date: 2026-11-04. Status: for owner approval. Milestone 3 of the implementation plan
(`docs/superpowers/plans/2026-10-30-headroid-implementation.md`), narrowed by the owner's decisions below.

## Intent

An AI agent the owner already uses (Claude Code, Claude Desktop, any MCP client) tests an Android app on the owner's
own phone **on a hidden display**, while the owner keeps using the phone. The agent does the thinking; no extra LLM
API key is needed. Example: the owner tells Claude "test the add-expense flow in Kharcha"; Claude opens Kharcha on a
hidden display through MCP tools, observes, taps and types until done, and the owner's screen, keyboard and focus are
never touched.

Why now: headroid 0.1.0a3 (on PyPI) already has the device side: hidden displays, per-display input, screenshots, UI
tree, muting, teardown, HyperOS freeze detection. The "AI-native" goal in the design spec
(`2026-10-30-headroid-design.md`, goal 4) is the missing headline feature for the public launch.

## Owner decisions (as decided)

1. **ARTEMIS is the agent layer, and it is the owner's fork**: `github.com/MrAk47Anand007/artemis`, built from the
   branch **`feat/manual-observe-act-mode`**. That branch adds ARTEMIS's host-agent "manual mode": MCP tools
   `mobile_observe`, `mobile_act`, `mobile_session_end`, where the calling MCP host supplies the intelligence, so
   no ARTEMIS LLM credential is needed. The owner chose this branch specifically because it needs no API key.
2. **Middle path for shipping**: headroid stays small; ARTEMIS is an optional add-on:
   - `pip install headroid`: testing API only (as today, ~0.8 MB).
   - `pip install "headroid[artemis]"`: adds the owner's fork. This is **the recommended way** to use headroid with
     an AI agent, and the docs say so.
3. **The fork is published to PyPI as `headroid-artemis`** (the name `artemis` belongs to someone else on PyPI;
   `headroid-artemis` is free as of 2026-11-04). The fork stays the single source of truth for ARTEMIS code; headroid
   does not copy ARTEMIS code.
4. **Hidden display by default under `headroid mcp`, and only there** (decided after the builder check): `headroid
   mcp` starts the fork's server with the headroid driver forced on (`ARTEMIS_DRIVER=headroid`) and exposes **only
   the three manual-mode tools** (`mobile_observe`, `mobile_act`, `mobile_session_end`). The fork's other five tools
   (`mobile_run_task`, `mobile_manage_task`, `mobile_get_device_state`, `mobile_inspect_trace`, `mobile_diagnose`) are
   not registered there, because some read display 0 or restart adb. The owner's normal `artemis mcp` (used by another
   project) is unchanged: installing headroid alone never switches ARTEMIS's driver. More tools can join `headroid mcp`
   later, each after it is made safe for the hidden display.

## Goals

- `headroid mcp` (new CLI command, available with the `[artemis]` extra) starts the fork's MCP server with the
  headroid driver active. Registering it in an MCP client is one config line, documented for Claude Code and Claude
  Desktop.
- `mobile_observe` returns a screenshot of the hidden display and the numbered element list from it.
- `mobile_act` actions run on the hidden display: click / long_press / input_text / click_sequence / swipe /
  press_key / manage_app (launch and stop) / wait_for_delay / wait_for_text / open_link / erase_one_char /
  focus_and_clear_text.
- `manage_app` launch opens the app on the hidden display with headroid's launch rules (own task, excluded from
  Recents, muted). Nothing the agent can call opens an app on display 0.
- `mobile_session_end` releases the hidden display and runs headroid's teardown (stop the app only if nobody else uses
  it, restore muting).
- Errors from headroid reach the agent as readable text, in particular the HyperOS freeze message (`-32014`) and
  "UiAutomation held by another tool".
- **Done when**: Claude Code, connected to `headroid mcp`, completes the sample app's login flow on a hidden display of
  the owner's POCO F6 (Android 16) using only `mobile_observe` / `mobile_act` / `mobile_session_end`, with
  `mTopFocusedDisplayId` 0 throughout and nothing left behind afterwards.

## Non-goals (this milestone)

- ARTEMIS Flash / Pro autonomous runs (`mobile_run_task`) on the hidden display. They need an LLM key and go through
  the same driver, so they may work, but they are not tested or promised here.
- mobile-use (`minitap-ai/mobile-use`) integration: later.
- A second, headroid-only MCP server with its own tool set. ARTEMIS's manual-mode tools are the MCP surface.
- The Playwright-style API and the pytest plugin (separate milestones).
- iOS, cloud devices, emulators-in-CI for the agent path.

## Anti-goals (failure even if it "works")

- Any read of the owner's screen (display 0): no screenshot, no UI dump, no accessibility-helper screen query, not
  even to learn the screen size. Today the fork's `_get_controller` calls `create_screen_client(device_id)
  .get_screen_data()` on the real screen at session start; with headroid active that call must not happen.
- Any input, app launch or focus change on display 0.
- Touching the owner's other project: no commits to the fork's existing branches (`main`,
  `feat/manual-observe-act-mode`, `feature/local-runner-design`, `feat/jev-driver`) and no changes in the owner's
  checkout `~/artemis`, which has uncommitted work. Work in a separate clone or worktree on a new branch.
- Making `pip install headroid` heavy, or requiring an LLM API key for the agent path.
- Copying ARTEMIS code into headroid.

## Constraints

- The fork requires **Python ≥ 3.12**; headroid supports ≥ 3.11. The `[artemis]` extra applies only on 3.12+
  (environment marker); `headroid mcp` on 3.11 explains that.
- The fork depends on `artemis-client>=0.1.0`, a workspace package in its repo (`packages/artemis-client`). A
  package named `artemis-client` 0.1.0 exists on PyPI; whether it is Google's must be checked. If not, it must be
  published or renamed alongside `headroid-artemis`, or the dependency made optional, so `pip install
  "headroid[artemis]"` resolves cleanly.
- The fork's import package is `artemis`. Installing `headroid-artemis` next to the unrelated PyPI `artemis` package
  would collide; document it, no rename.
- Apache-2.0: the fork keeps Google's headers; headroid's NOTICE credits ARTEMIS. Code headroid adds keeps its own
  headers.
- PyPI publishing of `headroid-artemis` is a public action; it uses the same trusted-publishing setup as headroid
  (owner adds a pending publisher for the fork's repo and workflow). The owner approves each first publish.
- headroid's isolation rules from `docs/HANDOFF.md` ("Rules that must not slip") apply unchanged.

## Shape of the solution

### In headroid (`packages/headroid`)

- `headroid/integrations/artemis.py`: `HeadroidDriver(BaseDeviceDriver)`. It owns one headroid `Device` connection
  and one hidden `Display` per ARTEMIS session; `connect()` creates the display, `disconnect()` releases it.
  Mapping:
  - `get_screen_data()` → `display.screenshot()` + `display.tree()`; `ScreenData.width/height` are the hidden
    display's size, `ui_elements` come from headroid's tree in the shape ARTEMIS's element indexer expects
    (`ui_hierarchy_xml` optional: the builder chooses whether to produce XML or feed parsed elements).
  - `tap`, `long_press`, `swipe`, `swipe_direction`, `input_text`, `press_key` → headroid display input.
  - `launch_app` / `stop_app` → `display.launch()` / headroid's stop with its "don't kill someone else's app" rule.
  - `get_current_package` → top package on the hidden display (from the tree), never display 0.
  - `execute_shell` → adb shell, but anything that would target display 0 (screencap, input, uiautomator dump, am
    start without `--display`) is refused with an explanation. Builder decides the exact allow/deny rule.
  - Video recording: not supported (headroid video is opt-in and not built); return a clear "not supported".
- `[project.optional-dependencies] artemis = ["headroid-artemis>=…; python_version>='3.12'"]`.
- `headroid mcp` CLI: starts the fork's MCP server (stdio by default) with the headroid driver selected and the
  device serial from `--serial` / `ADB_DEVICE_SERIAL` / the only attached device.
- Docs: README section "Use with an AI agent" (install, MCP config snippet for Claude Code and Claude Desktop, the
  HyperOS "No restrictions" tip, what the agent can and cannot do); capability matrix row; CHANGELOG.

### In the fork (new branch from `feat/manual-observe-act-mode`, e.g. `feat/headroid-driver`)

- Driver factory: select `HeadroidDriver` only when `ARTEMIS_DRIVER=headroid` (fail clearly if headroid is not
  installed); otherwise behave exactly as today.
- MCP server: a way to start it with a chosen subset of tools (e.g. a tool allowlist argument or env), used by
  `headroid mcp` to register only the three manual-mode tools.
- `_get_controller` (manual mode and other MCP entry points): when the headroid driver is selected, take the screen
  size from the hidden display and skip `create_screen_client(...).get_screen_data()` on the real screen.
- Any other manual-mode path that bypasses the driver and reaches the device directly (e.g. through
  `ctx.ui_adb_client` or raw adb) must route through the driver or be disabled under headroid. The builder audits
  `McpActionExecutor` and its action session for such paths.
- Packaging: distribution name `headroid-artemis`, version scheme of the builder's choice, a release workflow with
  trusted publishing, and the `artemis-client` question above resolved.
- No ARTEMIS LLM is invoked anywhere in the manual-mode path (already true on the branch; keep it true).

## Left to the builder

- Element extraction format between headroid's tree and ARTEMIS's indexer (XML vs parsed dicts), and whether
  headroid's settle logic or ARTEMIS's is used before observe.
- Exact `execute_shell` policy, timeouts, retries, and how many hidden displays a single MCP server allows.
- Version numbers for `headroid-artemis` and the next headroid release.
- Test layout: unit tests with a fake headroid `Display` on the fork side, a mock-ARTEMIS test on the headroid side,
  and one on-device end-to-end script for the "done when" flow (run with the owner's OK, as before).

## Settled after the builder check

- **Install weight of the extra**: `pip install "headroid[artemis]"` pulls the fork's full dependency list unchanged
  (LangChain, OpenCV, etc.). The owner chose the middle path knowing that only agent users pay this cost; slimming the
  fork's packaging is out of scope.
- **Release branch of the fork (Claude's call)**: `headroid-artemis` is released from a long-lived branch
  `headroid-artemis` in the fork, created from `feat/manual-observe-act-mode` and carrying the driver hook, packaging
  and the workflow `.github/workflows/release-headroid-artemis.yml` (the file the PyPI pending publisher names). It
  takes later ARTEMIS changes by merging `feat/manual-observe-act-mode` (or whatever branch the owner names) into it;
  it never merges back. Tags `headroid-artemis-v*` trigger releases.
- **Screenshots for clients that cannot read local files (Claude's call)**: under `headroid mcp`, `mobile_observe`
  and `mobile_act` also return the screenshot as inline MCP image content, so Claude Desktop can see it; the file path
  stays for Claude Code and existing users. Done-when is tested with Claude Code; Claude Desktop gets a config snippet
  and one manual check.
- **Session teardown**: `mobile_session_end` must also disconnect the driver (release the hidden display, headroid
  teardown); today it only releases the lock and the controller stays cached. Ordinary fork work.

## Calls made by Claude (not owner decisions)

- Driver code lives in headroid, the factory hook in the fork (avoids a circular package dependency).
- Switch name `ARTEMIS_DRIVER=headroid`, set by `headroid mcp`.
- Flash/Pro autonomous runs and mobile-use are out of scope for this milestone.
- `headroid mcp` is the entry point name; stdio transport by default.
