# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""HeadroidDriver against a fake headroid Device/Display (no phone, no adb)."""

import asyncio
import base64
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
        self.tree_sequence = []  # when set, successive tree() reads pop from here (the last one repeats)
        self.screenshot_result = PNG
        self.stop_result = {"stopped": True}
        self.open_url_result = "com.android.chrome"

    def _answer(self, result):
        if isinstance(result, Exception):
            raise result
        return result

    def tree(self):
        self.calls.append(("tree",))
        if self.tree_sequence:
            seq = self.tree_sequence
            return self._answer(seq.pop(0) if len(seq) > 1 else seq[0])
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

    def open_url(self, url):
        self.calls.append(("open_url", url))
        return self._answer(self.open_url_result)

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


class FakeTime:
    """Injected clock and sleep: sleeping advances the clock instantly."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _driver():
    device = FakeDevice()
    connected = []

    def connect(serial):
        connected.append(serial)
        return device

    fake_time = FakeTime()
    driver = HeadroidDriver(
        device_id="SERIAL1", connect=connect, clock=fake_time.clock, sleep=fake_time.sleep
    )
    driver.fake_time = fake_time
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
            "content-desc": "",
            "accessibilityText": "",
            "resource-id": "dev.headroid.sample:id/login",
            "class": "android.widget.Button",
            "package": "dev.headroid.sample",
            "bounds": "[32,91][688,166]",
            "clickable": "true",
            "long-clickable": "false",
            "enabled": "false",
            "focused": "false",
            "focusable": "false",
            "scrollable": "false",
            "checkable": "false",
            "checked": "false",
            "selected": "false",
        }
    ]
    assert data.screenshot_bytes == PNG
    assert base64.b64decode(data.screenshot_base64) == PNG
    assert (data.width, data.height) == (720, 1600)
    assert data.platform == "android"


def test_tree_to_elements_feeds_artemis_observe_pipeline():
    # The element list ARTEMIS shows the agent, and the indices click-by-number resolves, come from these
    # functions; they read uiautomator-format elements (string bounds), as from ARTEMIS's own adb driver.
    from artemis.mcp.actuators.adb import find_element_at_coords
    from artemis.utils.ocr_xml_fusion import fuse_ocr_with_xml
    from artemis.utils.visualization import format_minimal_list_with_elements

    nodes = [dict(TREE[0])]
    nodes[0]["children"] = TREE[0]["children"] + [
        {
            "cls": "android.widget.EditText",
            "text": "",
            "desc": "Search",
            "rid": "dev.headroid.sample:id/q",
            "bounds": [32, 200, 688, 260],
            "clickable": True,
            "focusable": True,
            "focused": True,
            "children": [],
        },
        {
            "cls": "android.widget.ImageView",
            "text": None,
            "desc": "Logo",
            "rid": None,
            "bounds": [10, 10, 10, 50],  # zero width: dropped, as by uiautomator
            "clickable": False,
            "children": [],
        },
    ]
    elements = tree_to_elements(nodes)
    text, indexed, _labels = format_minimal_list_with_elements(
        fuse_ocr_with_xml(elements, []), 720, 1600
    )
    assert text.splitlines() == [
        "[1] Text: 'Sign in' | Bounds: [44,56][955,103]",
        "[2] Text: 'Search' | Bounds: [44,125][955,162]",
    ]
    assert [e["center"] for e in indexed] == [[360, 128], [360, 230]]
    assert find_element_at_coords(elements, 360, 230)["focused"] == "true"


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
    assert [e["content-desc"] for e in tree_to_elements(nodes)] == ["Settings"]


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


def _shifted(tree, extra=0):
    """The same tree with every box moved right by the display width, as mid-transition."""
    import copy

    shifted = copy.deepcopy(tree)

    def walk(items):
        for node in items:
            left, top, right, bottom = node["bounds"]
            node["bounds"] = [left + 720 + extra, top, right + 720 + extra, bottom]
            walk(node["children"])

    walk(shifted)
    return shifted


def test_get_screen_data_waits_for_the_tree_to_settle_then_screenshots():
    driver, _, display = _driver()
    display.tree_sequence = [_shifted(TREE), TREE, TREE]
    data = run(driver.get_screen_data())
    assert [c[0] for c in display.calls] == ["tree", "tree", "tree", "screenshot"]
    assert data.ui_elements[0]["bounds"] == "[32,91][688,166]"
    assert driver.fake_time.sleeps == [0.15, 0.15]


def test_overflowing_descendant_does_not_block_settling():
    import copy

    tree = copy.deepcopy(TREE)
    tree[0]["children"].append(
        {
            "id": "0.1",
            "cls": "android.widget.ViewPager",
            "pkg": "dev.headroid.sample",
            "text": "Page 2",
            "desc": "",
            "rid": "",
            "bounds": [720, 200, 1440, 400],
            "clickable": False,
            "visible": True,
            "children": [],
        }
    )
    driver, _, display = _driver()
    display.tree_result = tree
    data = run(driver.get_screen_data())
    assert [c[0] for c in display.calls] == ["tree", "tree", "screenshot"]
    assert driver.fake_time.sleeps == [0.15]
    assert any(e["text"] == "Page 2" for e in data.ui_elements)


def test_get_screen_data_returns_latest_read_after_deadline_without_raising():
    driver, _, display = _driver()
    # never the same twice, never fully on screen
    display.tree_sequence = [_shifted(TREE, extra=i) for i in range(60)]
    data = run(driver.get_screen_data())
    reads = [c for c in display.calls if c[0] == "tree"]
    assert 2 <= len(reads) <= 15  # bounded by the 2.0 s deadline at 0.15 s polls
    assert driver.fake_time.now >= 2.0
    assert data.ui_elements[0]["bounds"].startswith("[7")
    assert display.calls[-1] == ("screenshot",)


def test_get_screen_data_skip_settling_reads_the_tree_once():
    driver, _, display = _driver()
    display.tree_sequence = [_shifted(TREE), TREE]
    data = run(driver.get_screen_data(skip_settling=True))
    assert [c[0] for c in display.calls] == ["tree", "screenshot"]
    assert driver.fake_time.sleeps == []
    assert data.ui_elements[0]["bounds"] == "[752,91][1408,166]"


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
    # "back", "enter", "delete" and "123" (MOVE_END) are the keys ARTEMIS itself sends.
    for key in (
        "enter",
        "back",
        "delete",
        "KEYCODE_DEL",
        "123",
        61,
        KeyCode.DELETE,
        "dpad_down",
        "menu",
    ):
        run(driver.press_key(key))
    assert device.calls == [
        ("key", 66),
        ("key", 4),
        ("key", 67),
        ("key", 67),
        ("key", 123),
        ("key", 61),
        ("key", 67),
        ("key", 20),
        ("key", 82),
    ]


@pytest.mark.parametrize("code", [7, 16, 29, 54, 55, 56, 68, 77, 81, 62, 111, 112, 122])
def test_press_key_allows_printable_and_editing_keys(code):
    driver, device, _ = _driver()
    run(driver.press_key(code))
    assert device.calls == [("key", code)]


@pytest.mark.parametrize(
    "key",
    [
        KeyCode.HOME,
        KeyCode.APP_SWITCH,
        KeyCode.POWER,
        KeyCode.VOLUME_UP,
        "KEYCODE_HOME",
        "home",
        3,
        # passed the old deny-list
        5,  # CALL
        6,  # ENDCALL
        27,  # CAMERA
        64,  # EXPLORER
        65,  # ENVELOPE
        79,  # HEADSETHOOK
        84,  # SEARCH
        85,  # MEDIA_PLAY_PAUSE
        90,  # MEDIA_FAST_FORWARD
        91,  # MUTE
        126,  # MEDIA_PLAY
        127,  # MEDIA_PAUSE
        176,  # SETTINGS
        204,  # LANGUAGE_SWITCH
        207,  # CONTACTS
        210,  # CALCULATOR
        284,  # ALL_APPS
        "KEYCODE_6",  # 6 is ENDCALL, not the digit
    ],
)
def test_press_key_refuses_keys_that_act_beyond_the_hidden_display(key):
    driver, device, _ = _driver()
    with pytest.raises(PermissionError, match="hidden display"):
        run(driver.press_key(key))
    assert device.calls == []


def test_press_key_refusal_names_the_key():
    driver, _, _ = _driver()
    with pytest.raises(PermissionError, match="KEYCODE_ENDCALL"):
        run(driver.press_key(6))
    with pytest.raises(PermissionError, match="KEYCODE_208"):
        run(driver.press_key(208))


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


def test_open_url_opens_through_headroid():
    # app.openUrl mutes the app and stops it at teardown, which a raw `am start` did not
    # the URL is one RPC value, never part of a shell line
    driver, device, _ = _driver()
    assert driver.last_opened_package is None
    assert run(driver.open_url("https://example.com/a?b=1")) is True
    assert ("open_url", "https://example.com/a?b=1") in device.calls
    assert driver.last_opened_package == "com.android.chrome"
    assert device.server.adb.calls == []


def test_open_url_raises_headroids_reason():
    driver, device, _ = _driver()
    run(driver.open_url("https://example.com/"))
    device.displays[0].open_url_result = RpcError(-32602, "url: no single app handles x:y")
    with pytest.raises(RpcError, match="no single app handles"):
        run(driver.open_url("x:y"))
    assert driver.last_opened_package is None  # not the previous link's app
    assert device.server.adb.calls == []


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
