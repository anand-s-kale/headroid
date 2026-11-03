# headroid (Python host)

Run Android apps on a hidden virtual display and drive them from Python. No runtime dependencies;
needs `adb` on PATH and an Android 11+ phone with USB debugging on (Android 14-16 are verified).

## 1. Install

```
pip install headroid
```

The wheel bundles the device-server jar, so there is nothing else to build. (From a source checkout, build
the jar with `cd device-server && ./gradlew :server:headroidJar`, or set `HEADROID_SERVER_JAR`.)

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
