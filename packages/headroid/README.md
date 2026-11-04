# headroid (Python host)

Run Android apps on a hidden virtual display and drive them from Python. No runtime dependencies;
needs `adb` on PATH and an Android 11+ phone with USB debugging on (Android 14-16 are verified).

## 1. Install

```
pip install --pre headroid
```

(`--pre` while headroid is an alpha. The wheel is also attached to each
[GitHub release](https://github.com/anand-s-kale/headroid/releases).)

The wheel bundles the device-server jar, so there is nothing else to build. From a source checkout instead:
`cd device-server && ./gradlew :server:headroidJar`, then `pip install -e packages/headroid`; the jar is found
in the build folder (or set `HEADROID_SERVER_JAR`).

## 2. Check your setup

```
headroid devices
headroid doctor            # add --serial <serial> when more than one device is attached
```

`doctor` checks adb, the device and its state, the Android version, the server jar, and that the server can
create a hidden display and take a screenshot. Each line is PASS, WARN or FAIL with a one-line fix. It exits
0 unless something FAILed.

**Xiaomi / Redmi / POCO:** in Developer options enable "USB debugging (Security settings)" (needed for
input) and "Install via USB" (needed to install apps).

## 3. See an app on a hidden display

```
headroid launch dev.headroid.sample --screenshot shot.png
```

This creates a hidden display, launches the app on it, waits 3 seconds (`--wait`), saves the screenshot and
releases the display. Nothing appears on the phone's own screen.

## 4. Drive it from Python

```python
from headroid import Device

with Device.connect() as dev:                      # jar found automatically
    d = dev.create_display(720, 1600, 320)         # hidden virtual display
    d.launch("dev.headroid.sample")
    d.click(rid="nav_login")                       # waits until the node has settled, then taps it
    d.fill("demo@headroid.dev", rid="login_email")
    d.fill("headroid", rid="login_password")
    d.click(rid="login_submit")
    d.wait_for(rid="form_name")                    # raises TimeoutError naming what it waited for
    d.screenshot("form.png")
```

`click`, `fill` and `wait_for` take `text=`, `rid=` or `desc=` and a `timeout` (default 10 s). They wait
until the node is visible, fully on the display and at the same position on two reads in a row, because
during an activity transition nodes are reported at animated positions and an immediate tap misses.
Lower-level calls (`tap`, `swipe`, `key`, `type`, `tree`, `find`) are also available.

## 5. Write tests with pytest

Unreleased (in `main`, not yet on PyPI). A Playwright-style layer on top of `Display`:

```python
import pytest
from headroid import expect

@pytest.mark.headroid(app="dev.headroid.sample")      # or @pytest.mark.headroid("dev.headroid.sample")
def test_login(headroid_page):
    page = headroid_page
    page.get_by_id("nav_login").click()
    page.get_by_id("login_email").fill("demo@headroid.dev")
    page.get_by_id("login_password").fill("headroid")
    page.get_by_text("Sign in").click()
    expect(page.get_by_id("form_name")).to_be_visible()
```

Run it with `pytest` (7 or later; `pip install --pre "headroid[test]"` pulls it in). `--headroid-serial S` picks a
phone; `--headroid-app PKG` sets the app for tests without the marker (the marker wins). The plugin is registered
automatically when headroid is installed.

The fixtures are prefixed so they do not clash with other plugins (pytest-playwright also has a `page`). For
shorter names, alias them in your project's `conftest.py`:

```python
import pytest

@pytest.fixture
def page(headroid_page):
    return headroid_page
```

- **Fixtures.** `headroid_device` (one per session, `Device.connect`) and `headroid_page` (one per test:
  `headroid_device.new_page(app)`, closed after the test).
- **No phone.** When adb is missing or no device is ready, tests using the fixtures are skipped with the reason (an
  unauthorised or offline phone is named, with a reminder to accept the USB debugging prompt). Several ready devices
  without `--headroid-serial`, or a `--headroid-serial` that is not attached, is a usage error: every such test
  errors with the message.
- **Failure artifacts.** Only when the test body fails (not setup or teardown), `screenshot.png` and `tree.json` are
  saved under `headroid-artifacts/<test id>-<hash>/` in the rootdir. Their paths are listed in a "headroid
  artifacts" report section and as test properties (`user_properties`, which `--junitxml` writes as `<property>`
  elements). A problem saving them is reported as `headroid_artifacts_error` and never fails the run.
- **Page** (`Device.new_page(app, width=720, height=1600, dpi=320, mute=True)`, also usable without pytest and as a
  context manager): `locator(text=, rid=, desc=, exact=True)`, `get_by_text(text, exact=True)` (`exact=False`
  matches a case-insensitive substring), `get_by_id(rid)` (full `pkg:id/name` or short `name`; a React Native
  `testID` is a resource id), `get_by_desc(desc)`, `screenshot(path=None)`, `tree()`, `press(key)` (`"BACK"`,
  `"ENTER"`, `"TAB"`, `"DEL"`, `"ESCAPE"`, DPAD keys, letters, digits; keys that act on the whole phone such as HOME,
  POWER, volume and Recents raise `PermissionError`), `wait_for_idle(timeout)` (tree unchanged on two reads 0.5 s
  apart), `set_default_timeout(s)`, `close()` (stops the app unless someone else uses it, then releases the display).
- **Locator** is lazy: every call reads the screen again. `click()`, `fill(text)` (taps, clears, types) and `text()`
  wait until the element exists, is visible, lies fully on the display and is at the same place on two reads (the
  same rule as `Display.wait_for`); `text()` only needs it to exist. `is_visible()` and `count()` answer at once.
  `nth(i)`, `first`, `last` pick among several matches (actions use the first by default). Timeouts default to 10 s,
  can be set per call or per page, and raise `headroid.TimeoutError` (a built-in `TimeoutError`) naming the locator,
  what the last read saw, and the closest texts on screen.
- **expect(locator)**: `to_be_visible()`, `to_be_hidden()`, `to_have_text(text)`, `to_contain_text(text)`,
  `to_have_count(n)`. Each retries until it holds or the timeout passes, then raises `AssertionError` with expected
  and actual.

Not yet: an async API, XPath / image / role / Flutter locators, parallel pages, an HTML report, video, and crash /
ANR detection.

## What stays with you, and what does not

- Taps, typing and the keyboard go to the hidden display only; your screen keeps focus.
- `launch` mutes the app's **sound and vibration** (app-ops) and restores them when the app is stopped or the
  session ends, even if the server was killed (the next server start restores them). Pass `mute=False` to hear it.
  App-ops are per app: while muted, the same app is silent on your screen too.
- **Notifications** still reach your notification shade by default. `launch(..., mute_notifications=True)` blocks
  them by revoking the notification permission while the session runs; the app can see that and may ask for the
  permission again, so it is opt-in, and it is skipped when the app is already running.
- Toasts, dialogs and permission prompts appear on the hidden display.
- A Wi-Fi drop does not end the session: the server keeps it for 60 s, the host reconnects (finding the phone even
  under a new adb serial) and resends reads; an action that was in flight raises `ConnectionError` saying it may or
  may not have run. If no host returns within 60 s, the server tears everything down and exits.
- Several sessions can share one phone: each gets its own server socket and its own mute records.
- At the end, an app is force-stopped only if headroid started it and nobody else has it open. If it was already
  running (your copy on the phone, or another session's), only the hidden display is closed and the app keeps running.
- Android has one UiAutomation (used for the UI tree and `setText` typing) for every tool on the phone. headroid holds it
  only while reading the screen and releases it after 5 s idle; when another tool (Appium, `uiautomator`, Maestro,
  another session) holds it, a tree read waits up to 10 s, then fails with a message naming the cause.

## Use with an AI agent

New in 0.1.0a4. `pip install --pre "headroid[artemis]"` (Python 3.12+) adds `headroid mcp
[--serial S]`, an MCP server for Claude Code, Claude Desktop and other MCP clients. It exposes only
`mobile_observe`, `mobile_act` and `mobile_session_end` on the hidden display and needs no LLM API key. Setup,
the tool list and the limits (only editing, navigation and printable keys; no `open_link` yet; Xiaomi needs Battery
saver "No restrictions") are in the
[main README](https://github.com/anand-s-kale/headroid/blob/main/README.md#use-with-an-ai-agent-recommended-headroidartemis).
Do not install it next to the unrelated PyPI package `artemis`: both use the import name `artemis`.

## Other commands

```
headroid info | screenshot -o shot.png | tree     # all accept --serial and --jar
```

`--jar` is optional everywhere. Resolution order: `--jar` / `jar=`, then `HEADROID_SERVER_JAR`, then the
jar bundled in the wheel, then a source-checkout build.

## Development

```
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]" && python -m pytest -q
```

Tests use a fake JSON-RPC server and a fake adb; no phone needed. To build a wheel with the jar bundled:
build the jar, then `python scripts/build_wheel.py` (needs `pip install build`).
