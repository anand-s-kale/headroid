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
