# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""HeadroidDriver against a fake headroid Device/Display (no phone, no adb)."""

import asyncio
import base64
import shlex
import zlib

import pytest

pytest.importorskip("artemis")

from artemis.drivers.base import KeyCode, ScreenData
from conftest import PNG

from headroid.integrations.artemis import HeadroidDriver, tree_to_elements
from headroid.rpc import RpcError

FROZEN = (
    "dev.x is frozen by HyperOS (GreezeManager) because the phone's screen is off. On the phone open "
    'Settings > Apps > dev.x > Battery saver and choose "No restrictions", or keep the screen on'
)

TREE = [
    {
        "id": "0",
        "cls": "android.widget.FrameLayout",
        "pkg": "dev.headroid.sample",
        "text": "",
        "desc": "",
        "rid": "",
        "bounds": [0, 0, 720, 1600],
        "clickable": False,
        "visible": True,
        "children": [
            {
                "id": "0.0",
                "cls": "android.widget.Button",
                "pkg": "dev.headroid.sample",
                "text": "Sign in",
                "desc": "",
                "rid": "dev.headroid.sample:id/login",
                "bounds": [32, 91, 688, 166],
                "clickable": True,
                "visible": True,
                "children": [],
            }
        ],
    }
]


class FakeAdb:
    def __init__(self):
        self.calls = []

    def run(self, *args, timeout=30):
        self.calls.append(args)
        return "ok\n"


class FakeServer:
    def __init__(self):
        self.adb = FakeAdb()


class FakeDisplay:
    def __init__(self, calls):
        self.calls = calls
        self.id = 7
        self.info = {"displayId": 7, "width": 720, "height": 1600, "dpi": 320}
        self.tree_result = TREE
        self.screenshot_result = PNG
        self.stop_result = {"stopped": True}

    def _answer(self, result):
        if isinstance(result, Exception):
            raise result
        return result

    def tree(self):
        self.calls.append(("tree",))
        return self._answer(self.tree_result)

    def screenshot(self):
        self.calls.append(("screenshot",))
        return self._answer(self.screenshot_result)

    def tap(self, x, y):
        self.calls.append(("tap", x, y))

    def long_press(self, x, y, duration_ms=600):
        self.calls.append(("long_press", x, y, duration_ms))

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        self.calls.append(("swipe", x1, y1, x2, y2, duration_ms))

    def key(self, code, meta_state=0):
        self.calls.append(("key", code))

    def type(self, text):
        self.calls.append(("type", text))

    def clear_text(self):
        self.calls.append(("clear_text",))

    def launch(self, package):
        self.calls.append(("launch", package))

    def stop(self, package):
        self.calls.append(("stop", package))
        return self.stop_result

    def release(self):
        self.calls.append(("release", self.id))


class FakeDevice:
    def __init__(self):
        self.calls = []
        self.server = FakeServer()
        self.displays = []

    def create_display(self, width=720, height=1600, dpi=320):
        self.calls.append(("create_display", width, height, dpi))
        d = FakeDisplay(self.calls)
        self.displays.append(d)
        return d

    def close(self):
        self.calls.append(("close",))


def _driver():
    device = FakeDevice()
    connected = []

    def connect(serial):
        connected.append(serial)
        return device

    driver = HeadroidDriver(device_id="SERIAL1", connect=connect)
    asyncio.run(driver.connect())
    assert connected == ["SERIAL1"]
    device.calls.clear()
    return driver, device, device.displays[0]


def run(coro):
    return asyncio.run(coro)


def test_connect_creates_one_hidden_display_and_disconnect_releases_it():
    device = FakeDevice()
    driver = HeadroidDriver(device_id="SERIAL1", connect=lambda serial: device)
    run(driver.connect())
    assert device.calls == [("create_display", 720, 1600, 320)]
    run(driver.disconnect())
    assert device.calls[1:] == [("release", 7), ("close",)]
    assert driver.device_id == "SERIAL1"


def test_connect_releases_display_when_it_fails_after_creating_it():
    device = FakeDevice()

    def create_display(width=720, height=1600, dpi=320):
        d = FakeDisplay(device.calls)
        d.info = {"displayId": 7}  # no size: connect cannot finish
        device.calls.append(("create_display",))
        return d

    device.create_display = create_display
    driver = HeadroidDriver(device_id="SERIAL1", connect=lambda serial: device)
    with pytest.raises(KeyError):
        run(driver.connect())
    assert device.calls == [("create_display",), ("release", 7), ("close",)]


def test_screen_size_is_hidden_display_size():
    driver, _, _ = _driver()
    assert driver.screen_size == (720, 1600)


def test_get_screen_data_maps_tree():
    driver, _, _ = _driver()
    data = run(driver.get_screen_data())
    assert isinstance(data, ScreenData)
    assert data.ui_elements == [
        {
            "text": "Sign in",
            "resource_id": "dev.headroid.sample:id/login",
            "class": "android.widget.Button",
            "clickable": True,
            "bounds": [32, 91, 688, 166],
            "center": [360, 128],
        }
    ]
    assert data.screenshot_bytes == PNG
    assert base64.b64decode(data.screenshot_base64) == PNG
    assert (data.width, data.height) == (720, 1600)
    assert data.platform == "android"


def test_tree_to_elements_matches_artemis_xml_parser():
    from artemis.drivers.android.hierarchy import parse_ui_hierarchy

    xml = (
        '<hierarchy><node class="android.widget.FrameLayout" text="" resource-id=""'
        ' clickable="false" bounds="[0,0][720,1600]">'
        '<node class="android.widget.Button" text="Sign in"'
        ' resource-id="dev.headroid.sample:id/login" clickable="true" bounds="[32,91][688,166]"/>'
        '<node class="android.widget.ImageView" text="" content-desc="Logo" resource-id=""'
        ' clickable="false" bounds="[10,10][10,50]"/>'
        "</node></hierarchy>"
    )
    nodes = [dict(TREE[0])]
    nodes[0]["children"] = TREE[0]["children"] + [
        {
            "cls": "android.widget.ImageView",
            "text": None,
            "desc": "Logo",
            "rid": None,
            "bounds": [10, 10, 10, 50],  # zero width: dropped, as by the XML parser
            "clickable": False,
            "children": [],
        }
    ]
    assert tree_to_elements(nodes) == parse_ui_hierarchy(xml)


def test_tree_to_elements_uses_desc_and_skips_invisible_nodes():
    nodes = [
        {"cls": "V", "text": "", "desc": "Settings", "rid": "", "bounds": [0, 0, 10, 10]},
        {
            "cls": "V",
            "text": "Gone",
            "desc": "",
            "rid": "",
            "bounds": [0, 0, 10, 10],
            "visible": False,
        },
    ]
    assert [e["text"] for e in tree_to_elements(nodes)] == ["Settings"]


def test_empty_display_observe():
    driver, _, display = _driver()
    display.tree_result = []
    display.screenshot_result = RpcError(-32011, "no frame yet")
    data = run(driver.get_screen_data())
    assert data.ui_elements == []
    assert data.screenshot_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert base64.b64decode(data.screenshot_base64) == data.screenshot_bytes
    # the placeholder is a real image of the display's size, so ARTEMIS can store and show it
    assert int.from_bytes(data.screenshot_bytes[16:20], "big") == 720
    assert int.from_bytes(data.screenshot_bytes[20:24], "big") == 1600
    idat = data.screenshot_bytes.index(b"IDAT")
    length = int.from_bytes(data.screenshot_bytes[idat - 4 : idat], "big")
    assert len(zlib.decompress(data.screenshot_bytes[idat + 4 : idat + 4 + length])) == 1600 * 721


def test_other_screenshot_errors_propagate():
    driver, _, display = _driver()
    display.screenshot_result = RpcError(-32000, "boom")
    with pytest.raises(RpcError, match="boom"):
        run(driver.get_screen_data())


def test_frozen_app_error_text_reaches_caller():
    driver, _, display = _driver()
    display.tree_result = RpcError(-32014, FROZEN)
    with pytest.raises(Exception) as excinfo:
        run(driver.get_screen_data())
    assert "frozen by HyperOS" in str(excinfo.value)
    assert "No restrictions" in str(excinfo.value)


def test_input_maps():
    driver, device, _ = _driver()
    assert run(driver.tap(10, 20, times=2, delay_ms=0)) is True
    assert run(driver.swipe(1, 2, 3, 4, duration_ms=500)) is True
    assert run(driver.long_press(5, 6, duration_ms=900)) is True
    assert run(driver.input_text("hé", clear_existing=True)) is True
    assert run(driver.press_key(KeyCode.BACK)) is True
    assert device.calls == [
        ("tap", 10, 20),
        ("tap", 10, 20),
        ("swipe", 1, 2, 3, 4, 500),
        ("long_press", 5, 6, 900),
        ("clear_text",),
        ("type", "hé"),
        ("key", 4),
    ]


def test_input_text_variants():
    driver, device, _ = _driver()
    run(driver.input_text("", clear_existing=True))  # ARTEMIS's erase/clear
    run(driver.input_text("abc", clear_existing=False))
    run(driver.input_text("", clear_existing=False))
    assert device.calls == [("clear_text",), ("type", "abc")]


def test_long_tap_is_a_long_press():
    driver, device, _ = _driver()
    run(driver.tap(10, 20, duration_ms=800))
    assert device.calls == [("long_press", 10, 20, 800)]


def test_swipe_direction_uses_hidden_display_size():
    driver, device, _ = _driver()
    run(driver.swipe_direction("up", duration_ms=800))
    assert device.calls == [("swipe", 432, 1120, 432, 480, 800)]


def test_press_key_accepts_names_and_numbers():
    driver, device, _ = _driver()
    for key in ("enter", "KEYCODE_DEL", "123", 61, KeyCode.DELETE):
        run(driver.press_key(key))
    assert device.calls == [("key", 66), ("key", 67), ("key", 123), ("key", 61), ("key", 67)]


@pytest.mark.parametrize(
    "key", [KeyCode.HOME, KeyCode.APP_SWITCH, KeyCode.POWER, KeyCode.VOLUME_UP, "KEYCODE_HOME", 3]
)
def test_press_key_refuses_keys_that_act_beyond_the_hidden_display(key):
    driver, device, _ = _driver()
    with pytest.raises(PermissionError, match="hidden display"):
        run(driver.press_key(key))
    assert device.calls == []


def test_press_key_unknown_name():
    driver, _, _ = _driver()
    with pytest.raises(ValueError, match="unknown key"):
        run(driver.press_key("nope"))


def test_launch_and_stop():
    driver, device, _ = _driver()
    assert run(driver.launch_app("dev.x")) is True
    assert run(driver.stop_app("dev.x")) is True
    assert device.calls == [("launch", "dev.x"), ("stop", "dev.x")]


def test_stop_refused_when_someone_else_uses_the_app():
    driver, _, display = _driver()
    display.stop_result = {
        "stopped": False,
        "reason": "it was already running before headroid launched it",
    }
    with pytest.raises(RuntimeError, match="running before headroid"):
        run(driver.stop_app("dev.x"))


def test_get_current_package():
    driver, _, display = _driver()
    assert run(driver.get_current_package()) == "dev.headroid.sample"
    display.tree_result = []
    assert run(driver.get_current_package()) is None


@pytest.mark.parametrize(
    "command",
    [
        "screencap -p",
        "uiautomator dump",
        "input tap 1 1",
        "am start -n a/.B",
        "monkey -p a 1",
        "/system/bin/screencap -p /sdcard/s.png",
        "echo hi; screencap -p",
        "echo hi\nscreencap -p",
        "getprop x && input keyevent 3",
        "ls | uiautomator dump",
        "FOO=1 screencap",
        "toybox screencap",
        "sh -c 'screencap -p'",
        "echo $(screencap -p)",
        "am start --display 0 -n a/.B -f 0x18800000",
        "am start-activity -n a/.B",
        "cmd activity start -n a/.B",
        "cmd input tap 1 1",
        "screenrecord /sdcard/a.mp4",
        "wm size",
        "dumpsys window",
        "dumpsys",
        "sendevent /dev/input/event1 0 0 0",
        "am instrument -w a/b",
        "echo a;>f screencap -p",
        "&>/dev/null screencap",
        "screencap -p > /sdcard/a.png 2>&1",
        "taskset 1 screencap",
        "{screencap,-p}",
        "/system/bin/sc*cap -p",
        "x=screencap; $x -p",
        "env -i PATH=/system/bin input tap 1 1",
        "timeout -s 9 5 uiautomator dump",
        "am start --display 7 -n a/.B --display 0 -f 0x18800000",
        "am start --display 7 -n a/.B --display=0 -f 0x18800000",
        "am start --display=0 -n a/.B -f 0x18800000",
        "am start -n a/.B --display",
        "cmd activity start-activity --display 7 --display 0 -n a/.B",
        "am start-in-vsync -n a/.B",
        "echo hi | screencap -p",
        # allowed by the old deny-list, refused by the allow-list
        "dumpsys battery",
        "cmd package list packages",
        "getprop ro.serialno 2>&1",
        "pm list packages | grep input",
        "pm list packages | grep monkey",
        # bypasses found in review
        "awk 'BEGIN{system(ARGV[1])}' screencap",
        "echo screencap -p /sdcard/a.png | awk '{system($0)}'",
        "echo uiautomator dump > /data/local/tmp/s && chmod +x /data/local/tmp/s && /data/local/tmp/s",
        "awk 'BEGIN{system(\"input tap 1 1\")}'",
        "awk -f /data/local/tmp/x.awk",
        "/data/local/tmp/s",
        "am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS",
        "am start-foreground-service -n a/.S",
        "am force-stop dev.x",
        "pm path",
        "pm uninstall dev.x",
        "getprop a b",
        "",
        # am start options other than the intent, --display and -f
        "am start --display 7 -S -n a/.B -f 0x18800000",
        "am start --display 7 --task 5 -n a/.B -f 0x18800000",
        "am start --display 7 --user 0 -n a/.B -f 0x18800000",
        "am start --display 7 --es k v -n a/.B -f 0x18800000",
        "am start --display 7 -n a/.B -f 0x18800000 -W",
        "am start --display 7 -f 0x18800000 a/.B",
        "am start --display 7 -n a/.B -f 0x18800000 --display=7",
        # -f missing or without NEW_TASK | MULTIPLE_TASK | EXCLUDE_FROM_RECENTS
        "am start --display 7 -n a/.B",
        "am start-activity --display 7 -n a/.B",
        "am start --display 7 -n a/.B -f 0x10000000",
        "am start --display 7 -n a/.B -f 0x18800000 -f 0x10000000",
        "am start --display 7 -n a/.B -f abc",
        "am start --display 7 -f 0x18800000 -n a/.B ^ screencap",
    ],
)
def test_execute_shell_refuses_display_0(command):
    driver, device, _ = _driver()
    with pytest.raises(PermissionError, match="display 0"):
        run(driver.execute_shell(command))
    assert device.server.adb.calls == []


@pytest.mark.parametrize(
    "command",
    [
        "am start --display 7 -f 0x18800000 -n a/.B",
        (
            "am start-activity --display 7 -f 411041792 -n a/.B -a android.intent.action.MAIN"
            " -c android.intent.category.LAUNCHER"
        ),
        "am start --display 7 -f 0x1c800000 -t text/plain -d content://x -n a/.B",
        "getprop",
        "getprop ro.build.version.sdk",
        "pm list packages",
        "pm list packages -3 dev",
        "pm path dev.x",
    ],
)
def test_execute_shell_runs_other_commands(command):
    driver, device, _ = _driver()
    assert run(driver.execute_shell(command, timeout_seconds=5)) == "ok\n"
    assert device.server.adb.calls == [("shell", command)]


def test_open_url_targets_hidden_display():
    driver, device, _ = _driver()
    assert run(driver.open_url("https://example.com/a?b=1")) is True
    assert device.server.adb.calls == [
        (
            "shell",
            (
                "am start --display 7 -f 0x18800000 -a android.intent.action.VIEW"
                " -d 'https://example.com/a?b=1'"
            ),
        )
    ]


def test_open_url_quotes_the_url():
    driver, device, _ = _driver()
    run(driver.open_url("https://e.com/'; screencap -p; '"))
    cmd = device.server.adb.calls[0][1]
    assert cmd.endswith("-d 'https://e.com/'\\''; screencap -p; '\\'''")


def test_open_url_injection_stays_one_argument():
    driver, device, _ = _driver()
    url = "x'; screencap -p /sdcard/a.png; echo '"
    run(driver.open_url(url))
    cmd = device.server.adb.calls[0][1]
    # the device shell parses the line back into the same arguments: the URL is one -d value
    words = shlex.split(cmd, posix=True)
    assert words[-2:] == ["-d", url]
    assert words[:3] == ["am", "start", "--display"]


def test_open_url_follows_the_am_start_rules():
    from headroid.integrations.artemis import _am_start_problem

    driver, device, _ = _driver()
    run(driver.open_url("https://example.com/"))
    words = shlex.split(device.server.adb.calls[0][1], posix=True)
    assert words[:2] == ["am", "start"]
    assert _am_start_problem(words[2:], 7) is None


def test_video_not_supported():
    driver, _, _ = _driver()
    with pytest.raises(NotImplementedError, match="not supported"):
        run(driver.start_video_recording())
    assert run(driver.stop_video_recording()) is None


def test_not_connected():
    driver = HeadroidDriver(device_id="SERIAL1", connect=lambda serial: FakeDevice())
    with pytest.raises(RuntimeError, match="not connected"):
        _ = driver.screen_size
    run(driver.disconnect())  # no-op
