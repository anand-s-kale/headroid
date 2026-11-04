# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
from conftest import PNG

from headroid.device import Device, Display
from headroid.rpc import RpcClient

TREE = [
    {
        "id": "0",
        "rid": "",
        "text": "",
        "desc": "",
        "children": [
            {
                "id": "0.0",
                "rid": "dev.headroid.sample:id/login_button",
                "text": "Login",
                "desc": "",
                "children": [],
            },
            {"id": "0.1", "rid": "", "text": "", "desc": "Settings", "children": []},
        ],
    }
]


def _display(fake_server):
    return Display(RpcClient("127.0.0.1", fake_server.port), {"displayId": 1})


def test_find_by_rid(fake_server):
    fake_server.tree = TREE
    d = _display(fake_server)
    assert d.find(rid="dev.headroid.sample:id/login_button")["id"] == "0.0"
    assert d.find(rid="login_button")["text"] == "Login"
    assert d.find(text="Login")["id"] == "0.0"
    assert d.find(desc="Settings")["id"] == "0.1"
    assert d.find(rid="nope") is None


def test_screenshot_writes_file(fake_server, tmp_path):
    d = _display(fake_server)
    out = tmp_path / "s.png"
    assert d.screenshot(str(out)) == PNG
    assert out.read_bytes() == PNG


def test_device_create_display_and_tap(fake_server):
    dev = Device(RpcClient("127.0.0.1", fake_server.port))
    disp = dev.create_display()
    disp.tap(5, 6)
    assert ("input.tap", {"displayId": 1, "x": 5, "y": 6}) in fake_server.calls


def test_launch_mutes_by_default(fake_server):
    d = _display(fake_server)
    d.launch("a.b")
    d.launch("c.d", mute=False, mute_notifications=True)
    launches = [p for m, p in fake_server.calls if m == "app.launch"]
    assert launches[0]["mute"] is True and launches[0]["muteNotifications"] is False
    assert launches[1]["mute"] is False and launches[1]["muteNotifications"] is True


def test_open_url_returns_the_package_and_mutes_by_default(fake_server):
    d = _display(fake_server)
    assert d.open_url("https://example.com/") == "com.android.chrome"
    d.open_url("https://example.com/b", mute=False)
    opens = [p for m, p in fake_server.calls if m == "app.openUrl"]
    assert opens[0] == {"displayId": 1, "url": "https://example.com/", "mute": True}
    assert opens[1]["mute"] is False


def test_stop_and_clear_text(fake_server):
    d = _display(fake_server)
    d.stop("a.b")
    d.clear_text()
    assert ("app.stop", {"package": "a.b"}) in fake_server.calls
    assert ("input.clearText", {"displayId": 1}) in fake_server.calls
