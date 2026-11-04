# headroid + ARTEMIS manual-mode MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pip install "headroid[artemis]"` + `headroid mcp` gives any MCP client ARTEMIS's no-API-key manual-mode tools (`mobile_observe`, `mobile_act`, `mobile_session_end`) acting on a headroid hidden display.

**Architecture:** headroid gains `HeadroidDriver`, an implementation of ARTEMIS's `BaseDeviceDriver` over headroid's `Device`/`Display`. The owner's ARTEMIS fork gets a long-lived branch `headroid-artemis` (from `feat/manual-observe-act-mode`) that selects that driver when `ARTEMIS_DRIVER=headroid`, never reads display 0 in that mode, can register a subset of MCP tools, and is published to PyPI as `headroid-artemis` (+ `headroid-artemis-client`). `headroid mcp` sets the environment and starts the fork's MCP server over stdio.

**Tech Stack:** Python 3.12 (fork) / 3.11+ (headroid), MCP Python SDK (FastMCP, already a fork dependency), pytest, setuptools, GitHub Actions trusted publishing, adb.

**Spec:** `docs/superpowers/specs/2026-11-04-headroid-artemis-mcp-design.md`

## Global Constraints

- Fork source: `https://github.com/MrAk47Anand007/artemis`, base branch `feat/manual-observe-act-mode` (commit `a7355c4`). New branch name: `headroid-artemis`. Never commit to `main`, `feat/manual-observe-act-mode`, `feature/local-runner-design`, `feat/jev-driver`.
- Never modify `~/artemis` (owner's checkout with uncommitted work). Work in a fresh clone at `C:\hd\headroid-artemis` (short path: Windows long-path limits).
- Distribution names: `headroid-artemis` (root package, import names `artemis`, `mcp_server`, `apps` unchanged) and `headroid-artemis-client` (from `packages/artemis-client`, import name `artemis_client` unchanged). PyPI's `artemis-client` is an unrelated Hikvision client and must never be installed by us.
- Fork requires Python ≥ 3.12; headroid stays ≥ 3.11. Extra: `artemis = ["headroid-artemis>=0.1.0a1; python_version >= '3.12'"]`.
- Driver switch: `ARTEMIS_DRIVER=headroid`. Without it the fork behaves exactly as on `feat/manual-observe-act-mode`.
- Tool allowlist env: `ARTEMIS_MCP_TOOLS` (comma-separated names). `headroid mcp` sets it to `mobile_observe,mobile_act,mobile_session_end`.
- Inline screenshot env: `ARTEMIS_MCP_INLINE_SCREENSHOT=1` (set by `headroid mcp`).
- Under `ARTEMIS_DRIVER=headroid`: no screenshot, UI dump, input, accessibility-helper query or `am start` without `--display` may target display 0. No ARTEMIS LLM call in the manual-mode path.
- Apache-2.0: fork files keep Google's headers; new fork files carry `Copyright 2026 Google LLC` + the owner's modification line in the fork's existing style; headroid files keep `Copyright 2026 Anand S Kale and the headroid contributors` / `SPDX-License-Identifier: Apache-2.0`. headroid's `NOTICE` credits ARTEMIS.
- Publishing to PyPI and on-device runs need the owner's go-ahead at the time (they are public / touch the owner's phone).
- headroid rules in `docs/HANDOFF.md` "Rules that must not slip" apply.

## Review Focus

1. **Observe before any app is open** (hidden display empty): `mobile_observe` succeeds with zero elements and a screenshot or a clear "nothing drawn yet" message, never a crash. → test in Task 5.
2. **HyperOS freezes the app mid-session**: the `-32014` text reaches the agent verbatim in the tool's error. → test in Task 5.
3. **An `execute_shell` command aimed at display 0** (`screencap`, `uiautomator dump`, `input tap`, `am start` without `--display`, `monkey`): refused with a message, nothing run. → test in Task 5.
4. **A second `headroid mcp` on the same phone**: gets its own hidden display (headroid sessions are independent) or a clear busy error from ARTEMIS's device lock, never a shared display. → test in Task 2.
5. **`mobile_session_end` then `mobile_observe` again**: a new hidden display is created; the old one is gone (no leaked display). → test in Task 2.

---

### Task 1: Fork branch and driver selection

**Files:**
- Modify (fork): `artemis/drivers/factory.py` (`create_driver`)
- Test (fork): `tests/unit/drivers/test_factory_headroid.py`

**Interfaces:**
- Consumes: `headroid.integrations.artemis.HeadroidDriver(device_id: str)` (Task 5; faked here via `sys.modules`).
- Produces: `create_driver(ctx)` returns `HeadroidDriver(device_id=ctx.device.device_id)` when `os.environ["ARTEMIS_DRIVER"] == "headroid"`; helper `artemis.drivers.factory.headroid_selected() -> bool`.

- [ ] **Step 1:** `git clone https://github.com/MrAk47Anand007/artemis C:\hd\headroid-artemis`, `git switch -c headroid-artemis origin/feat/manual-observe-act-mode`, `uv sync` (or `pip install -e .[dev]` on Python 3.12), run the fork's unit suite once and record the baseline pass count.
- [ ] **Step 2: Write failing tests** in `test_factory_headroid.py`:
  - `test_default_is_adb_driver`: no env → `create_driver(ctx)` is `AndroidAdbDriver` (patch `AdbClient`).
  - `test_headroid_env_selects_headroid`: env `ARTEMIS_DRIVER=headroid`, fake module `headroid.integrations.artemis` with a `HeadroidDriver` class in `sys.modules` → instance of it, `device_id == ctx.device.device_id`, and `ctx.adb_client` left `None`.
  - `test_headroid_env_without_headroid_fails_clearly`: env set, module import raises → `RuntimeError` whose message contains `pip install "headroid[artemis]"`.
- [ ] **Step 3:** Run `pytest tests/unit/drivers/test_factory_headroid.py -v` → 2 FAIL, 1 PASS.
- [ ] **Step 4:** Implement the branch at the top of `create_driver` (before cloud/mock checks) plus `headroid_selected()`.
- [ ] **Step 5:** Run the test file → PASS; run the full fork unit suite → same count as baseline + 3.
- [ ] **Step 6:** Commit `feat(headroid): select HeadroidDriver with ARTEMIS_DRIVER=headroid`.

### Task 2: Manual mode never reads display 0, and session end releases the display

**Files:**
- Modify (fork): `artemis/mcp/adb_server.py` (`_get_controller`), `mcp_server/manual_session.py` (`ManualSessionRegistry._end_key`), `artemis/mcp/actuators/adb.py` (direct-device paths)
- Test (fork): `tests/unit/mcp_server/test_manual_headroid.py`

**Interfaces:**
- Consumes: `headroid_selected()` (Task 1); driver methods from `BaseDeviceDriver` plus optional `HeadroidDriver.open_url(url: str) -> bool` (Task 5).
- Produces: `adb_server.drop_controller(device_serial: str | None) -> None` (removes the cached controller and awaits `driver.disconnect()`); `_end_key` calls it.

- [ ] **Step 1: Write failing tests** (fake driver class registered as in Task 1, recording calls):
  - `test_controller_under_headroid_skips_screen_client`: patch `create_screen_client` to raise if called; `_get_controller("SERIAL")` succeeds; `ctx.device.device_width/height` equal the fake driver's `screen_size`; `ctx.ui_adb_client is None`.
  - `test_session_end_disconnects_driver`: registry `get_or_create` then `end` → fake driver `disconnect` called once; next `_get_controller("SERIAL")` builds a new controller (new driver instance).
  - `test_second_session_same_serial_is_busy`: two registries (simulating two servers) sharing `DeviceExecutionLock` → second `get_or_create` raises `DeviceBusyError`.
  - `test_manage_app_launch_uses_driver`: under headroid, the `manage_app` launch path calls `driver.launch_app(pkg)` and never `device.shell("monkey ...")` / `am start` (patch adbutils device to raise).
  - `test_open_link_uses_open_url`: under headroid, `open_link` calls `driver.open_url(url)`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement: in `_get_controller`, when `headroid_selected()`: skip adb device listing and `create_screen_client`; build the context with `adb_client=None`, `ui_adb_client=None`; create the controller, `await`/run `driver.connect()`, take width/height from `driver.screen_size`. Audit `artemis/mcp/actuators/adb.py` (and anything `McpActionExecutor`'s manual actions reach) for `device.shell`, `ctx.adb_client`, `ctx.ui_adb_client`, `create_screen_client` uses; under headroid route launch/stop through the driver, `open_link` through `open_url`, and refuse anything else that would hit the device directly with a clear error. List each path changed in the commit message.
- [ ] **Step 4:** Run the test file and full unit suite → PASS.
- [ ] **Step 5:** Commit `feat(headroid): manual mode on the hidden display, teardown on session end`.

### Task 3: Tool allowlist and inline screenshots

**Files:**
- Modify (fork): `mcp_server/server.py` (startup), `mcp_server/tools/manual_mode.py` (`mobile_observe`, `mobile_act` return values)
- Test (fork): `tests/unit/mcp_server/test_tool_allowlist.py`, extend `tests/unit/mcp_server/test_manual_mode_tools.py`

**Interfaces:**
- Produces: `mcp_server.server.apply_tool_allowlist(mcp, names: set[str] | None) -> None`; when `ARTEMIS_MCP_INLINE_SCREENSHOT=1`, `mobile_observe`/`mobile_act` return `[dict, mcp.server.fastmcp.Image(path=screenshot)]` (dict unchanged, still has `screenshot` path); otherwise exactly today's dict.

- [ ] **Step 1: Write failing tests:**
  - `test_allowlist_keeps_only_named_tools`: env `ARTEMIS_MCP_TOOLS=mobile_observe,mobile_act,mobile_session_end` → `await mcp.list_tools()` names == that set.
  - `test_no_allowlist_keeps_all_eight`.
  - `test_unknown_name_in_allowlist_fails_at_startup` → `ValueError` naming it.
  - `test_inline_screenshot_returns_image_content` (fake session observe with a temp PNG) and `test_default_returns_dict_only`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement; remove tools through FastMCP's public `remove_tool` if the installed version has it, else its tool manager.
- [ ] **Step 4:** Run tests + full suite → PASS.
- [ ] **Step 5:** Commit `feat(mcp): ARTEMIS_MCP_TOOLS allowlist and inline screenshots`.

### Task 4: Fork packaging and release workflow

**Files:**
- Modify (fork): `pyproject.toml` (`name = "headroid-artemis"`, `version = "0.1.0a1"`, dependency `headroid-artemis-client==0.1.0a1` instead of `artemis-client`, project URLs → fork), `packages/artemis-client/pyproject.toml` (`name = "headroid-artemis-client"`, `version = "0.1.0a1"`), `README.md` (short "This is the headroid-artemis distribution of a fork of google/artemis" note)
- Create (fork): `.github/workflows/release-headroid-artemis.yml`

**Interfaces:**
- Produces: wheels `headroid_artemis-0.1.0a1-py3-none-any.whl`, `headroid_artemis_client-0.1.0a1-py3-none-any.whl`; tag pattern `headroid-artemis-v*`; GitHub environment `pypi`.

- [ ] **Step 1:** Workflow: on push of `headroid-artemis-v*` tags and on `workflow_dispatch`; Python 3.12; Node LTS; `npm ci --prefix apps/showcase_ui && npm run build --prefix apps/showcase_ui` (setup.py refuses to build without it); `USE_CYTHON=0`; build both wheels; `twine check --strict`; tag/version match check; job `pypi` with `environment: pypi`, `permissions: id-token: write`, `pypa/gh-action-pypi-publish` uploading the client first, then the root package.
- [ ] **Step 2:** Local check: build both wheels, create a clean Python 3.12 venv, `pip install` both wheel files, then `python -c "import artemis, artemis_client, mcp_server; from mcp_server.tools import mobile_observe"` → no error, and `pip show artemis-client` → not installed.
- [ ] **Step 3:** Push branch `headroid-artemis` to the fork; run the workflow via `workflow_dispatch` without publishing (guard the publish job with `if: startsWith(github.ref, 'refs/tags/')`) → build job green.
- [ ] **Step 4:** Commit `build: publish as headroid-artemis and headroid-artemis-client`.
- [ ] **Step 5 (owner):** On pypi.org add two pending publishers, both owner `MrAk47Anand007`, repository `artemis`, workflow `release-headroid-artemis.yml`, environment `pypi`, projects `headroid-artemis` and `headroid-artemis-client`. Hold until Task 8.

### Task 5: `HeadroidDriver` in headroid

**Files:**
- Create: `packages/headroid/src/headroid/integrations/__init__.py`, `packages/headroid/src/headroid/integrations/artemis.py`
- Test: `packages/headroid/tests/test_artemis_driver.py` (module-level `pytest.importorskip("artemis")`)

**Interfaces:**
- Consumes: `headroid.Device.connect(serial) -> Device`, `Device.create_display(width=720, height=1600, dpi=320) -> Display`, `Display.screenshot/tree/tap/long_press/swipe/type/key/launch/release`, `Display.info["width"/"height"]`, `RpcError(code, message)`; ARTEMIS `BaseDeviceDriver`, `ScreenData`, `KeyCode`, `SwipeDirection`.
- Produces: `class HeadroidDriver(BaseDeviceDriver)` with `__init__(self, device_id: str, *, connect=Device.connect)`; all abstract methods; extra `async def open_url(self, url: str) -> bool`; module function `tree_to_elements(nodes: list[dict]) -> list[dict]`.

- [ ] **Step 1: Write failing tests** with a fake `Display`/`Device` (record calls, return canned tree and PNG):
  - `test_connect_creates_one_hidden_display_and_disconnect_releases_it`.
  - `test_screen_size_is_hidden_display_size` → `(720, 1600)`.
  - `test_get_screen_data_maps_tree`: canned headroid tree (text "Sign in", rid `dev.headroid.sample:id/login`, bounds `[32,91,688,166]`, clickable) → one element with the same keys and value types as `artemis/drivers/android/hierarchy.py` produces (`text`, `resource_id`, `bounds == [32,91,688,166]`, `center == [360,128]`, …); `screenshot_bytes` is the PNG; `width/height` 720/1600.
  - `test_empty_display_observe` (Review Focus 1): tree `[]`, screenshot raises `RpcError(-32011, ...)` → `ScreenData` with `ui_elements == []` and a placeholder image; no exception.
  - `test_frozen_app_error_text_reaches_caller` (Review Focus 2): `tree` raises `RpcError(-32014, "dev.x is frozen by HyperOS ...")` → raised error message contains `frozen by HyperOS` and `No restrictions`.
  - `test_input_maps`: `tap(10, 20, times=2)` → two taps; `swipe`, `long_press`, `input_text("hé", clear_existing=True)` (clears focused field first, then `type`), `press_key(KeyCode.BACK)` → `key(4)`.
  - `test_launch_and_stop`: `launch_app("dev.x")` → `Display.launch("dev.x")`; `stop_app` uses headroid's stop RPC (the one that keeps the "don't stop an app someone else uses" rule).
  - `test_execute_shell_refuses_display_0` (Review Focus 3): each of `screencap -p`, `uiautomator dump`, `input tap 1 1`, `am start -n a/.B`, `monkey -p a 1` → raises `PermissionError` mentioning "display 0"; `am start --display 7 ...` and `getprop ro.build.version.sdk` run through adb shell.
  - `test_open_url_targets_hidden_display`: adb shell called with `am start --display <id> -f 0x18800000 -a android.intent.action.VIEW -d '<url>'`.
  - `test_video_not_supported` → `NotImplementedError` with a message.
- [ ] **Step 2:** Run `pytest packages/headroid/tests/test_artemis_driver.py -v` on Python 3.12 with the fork installed (`pip install -e C:\hd\headroid-artemis`) → FAIL.
- [ ] **Step 3:** Implement. Sync headroid calls run in `asyncio.to_thread`. `get_current_package` = `pkg` of the first tree node or `None`. If headroid lacks an RPC needed for stop or clearing a field, add it to the device server with a unit test (follow `Session.register` patterns) rather than shelling out.
- [ ] **Step 4:** Run → PASS; run the whole headroid suite on 3.11 (file skipped) and 3.12 → PASS.
- [ ] **Step 5:** Add a CI job (Python 3.12) that installs the fork from git (`pip install "git+https://github.com/MrAk47Anand007/artemis@headroid-artemis"`) and runs this test file.
- [ ] **Step 6:** Commit `feat: HeadroidDriver for ARTEMIS`.

### Task 6: `headroid mcp` command and the `[artemis]` extra

**Files:**
- Modify: `packages/headroid/pyproject.toml` (extra), `packages/headroid/src/headroid/cli.py` (subcommand `mcp`)
- Test: `packages/headroid/tests/test_mcp_cli.py`

**Interfaces:**
- Consumes: env names from Global Constraints; the fork's MCP entry point (`mcp_server.server` main function, as `python -m mcp_server` uses it).
- Produces: `headroid mcp [--serial S]`; function `headroid.cli.mcp_env(serial: str | None) -> dict[str, str]`.

- [ ] **Step 1: Write failing tests:**
  - `test_mcp_env`: `mcp_env("ABC")` == `{"ARTEMIS_DRIVER": "headroid", "ARTEMIS_MCP_TOOLS": "mobile_observe,mobile_act,mobile_session_end", "ARTEMIS_MCP_INLINE_SCREENSHOT": "1", "ADB_DEVICE_SERIAL": "ABC"}`; with `None` and exactly one attached device, its serial; with several, exits with the device list.
  - `test_mcp_without_artemis_explains`: import of `mcp_server` fails → exit code 2, message contains `pip install "headroid[artemis]"` and, on Python < 3.12, `Python 3.12`.
  - `test_mcp_runs_server_with_env` (monkeypatched entry point records `os.environ` at call time).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat: headroid mcp starts ARTEMIS manual mode on a hidden display`.

### Task 7: Docs

**Files:**
- Modify: `README.md`, `packages/headroid/README.md`, `NOTICE`, `CHANGELOG.md` (`[Unreleased]` → Added), `docs/CAPABILITY-MATRIX.md` (row: AI agent via ARTEMIS manual mode), `docs/HANDOFF.md`

- [ ] **Step 1:** README section "Use with an AI agent (recommended: `headroid[artemis]`)": install line; Claude Code `claude mcp add headroid -- headroid mcp`; Claude Desktop `claude_desktop_config.json` snippet (`"command": "headroid", "args": ["mcp"]`); the three tools and what they do; no API key needed; Xiaomi "No restrictions" tip; Python 3.12 requirement; note that the fork's other ARTEMIS tools are not exposed; warn that `headroid-artemis` and the unrelated PyPI package `artemis` both install the import name `artemis` and must not share an environment.
- [ ] **Step 2:** NOTICE: "Agent integration uses ARTEMIS (https://github.com/google/artemis), Apache-2.0, via the headroid-artemis fork."
- [ ] **Step 3:** Commit `docs: using headroid with an AI agent`.

### Task 8: On-device end-to-end, Claude check, and releases

**Files:**
- Create: `packages/headroid/scripts/agent_e2e.py`

- [ ] **Step 1:** Script: starts `headroid mcp --serial S` as an MCP stdio client (MCP Python SDK `ClientSession`), asserts `list_tools` names == the three; `mobile_act manage_app` launch `dev.headroid.sample`; `mobile_observe`; logs in with the sample's test credentials from `sample-app` sources via `mobile_act` click/input_text by element index; `mobile_observe` shows the post-login screen; `mobile_session_end`. Before, during and after: `dumpsys window | grep mTopFocusedDisplayId` == 0; afterwards no `headroid` virtual display and no server process. Refuses non-emulator serials without `--allow-device` (same rule as `emulator_smoke.py`).
- [ ] **Step 2 (owner OK):** Run on the POCO F6 → all assertions true.
- [ ] **Step 3 (owner OK):** Register `headroid mcp` in Claude Code, ask Claude to "log in to the headroid sample app"; record the result. Claude Desktop: one manual run confirming screenshots are visible.
- [ ] **Step 4 (owner OK):** Tag `headroid-artemis-v0.1.0a1` in the fork → both packages on PyPI. Then headroid `0.1.0a4` per `docs/RELEASING.md` with the extra. Verify in a clean Python 3.12 venv: `pip install --pre "headroid[artemis]"`, `headroid mcp` lists three tools against the phone.
- [ ] **Step 5:** Commit `test: agent end-to-end on a hidden display`; update HANDOFF with results.
