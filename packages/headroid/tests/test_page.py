# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import pytest
from conftest import PNG
from fake_display import node, page_with

from headroid import Device, Page, TimeoutError
from headroid.rpc import RpcClient, RpcError


def test_new_page_creates_display_and_launches(fake_server):
    dev = Device(RpcClient("127.0.0.1", fake_server.port))
    page = dev.new_page("dev.headroid.sample", width=1080, height=2400, dpi=420, mute=False)
    assert isinstance(page, Page) and page.app == "dev.headroid.sample"
    calls = fake_server.calls
    assert calls[0] == ("display.create", {"width": 1080, "height": 2400, "dpi": 420})
    assert calls[1][0] == "app.launch"
    assert calls[1][1]["displayId"] == 1 and calls[1][1]["mute"] is False
    assert page.display in dev.displays


def test_page_close_stops_app_releases_display_once(fake_server):
    dev = Device(RpcClient("127.0.0.1", fake_server.port))
    with dev.new_page("dev.headroid.sample") as page:
        pass
    page.close()
    methods = [m for m, _ in fake_server.calls]
    assert methods == ["display.create", "app.launch", "app.stop", "display.release"]
    assert dev.displays == []
    dev.close()  # nothing left to release
    assert [m for m, _ in fake_server.calls].count("display.release") == 1


def test_new_page_releases_display_when_launch_fails(fake_server):
    dev = Device(RpcClient("127.0.0.1", fake_server.port))
    real_call = dev.client.call

    def call(method, **params):
        if method == "app.launch":
            raise RpcError(-32602, "no such package")
        return real_call(method, **params)

    dev.client.call = call
    with pytest.raises(RpcError):
        dev.new_page("nope")
    assert dev.displays == []
    assert "display.release" in [m for m, _ in fake_server.calls]


def test_page_screenshot_and_tree(fake_server, tmp_path):
    dev = Device(RpcClient("127.0.0.1", fake_server.port))
    fake_server.tree = [{"id": "0", "text": "hi", "children": []}]
    page = dev.new_page("a.b")
    out = tmp_path / "p.png"
    assert page.screenshot(str(out)) == PNG and out.read_bytes() == PNG
    assert page.screenshot() == PNG
    assert page.tree()[0]["text"] == "hi"


def test_press_names_and_refusals():
    page, d = page_with()
    page.press("BACK")
    page.press("enter")
    page.press("KEYCODE_TAB")
    page.press("a")
    page.press(67)
    assert [c[1] for c in d.calls] == [4, 66, 61, 29, 67]
    with pytest.raises(PermissionError, match="HOME"):
        page.press("HOME")
    with pytest.raises(PermissionError, match="POWER"):
        page.press(26)
    with pytest.raises(ValueError, match="unknown key"):
        page.press("FLY")
    assert len(d.calls) == 5


def test_wait_for_idle_returns_once_tree_is_unchanged():
    a = [node(text="Loading")]
    b = [node(text="Done")]
    page, d = page_with(a, b, b)
    page.wait_for_idle()
    assert d.tree_calls == 3
    assert d.clock.t == pytest.approx(1.0)  # two 0.5 s gaps


def test_wait_for_idle_timeout():
    reads = [[node(text=str(i))] for i in range(100)]
    page, _ = page_with(*reads)
    with pytest.raises(TimeoutError, match="kept changing for 2s"):
        page.wait_for_idle(timeout=2)


def test_display_wait_for_raises_headroid_timeout_error(fake_server):
    from headroid.device import Display

    t = [0.0]
    d = Display(
        RpcClient("127.0.0.1", fake_server.port),
        {"displayId": 1, "width": 720, "height": 1600},
        clock=lambda: t[0],
        sleep=lambda s: t.__setitem__(0, t[0] + s),
    )
    with pytest.raises(TimeoutError, match="nope"):
        d.wait_for(text="nope", timeout=0.5)


def test_fill_stays_within_one_timeout():
    field = node(rid="p:id/f", bounds=(0, 0, 100, 50))
    page, d = page_with([field], unfocused_clears=1000)
    with pytest.raises(RpcError):
        page.get_by_id("f").fill("x", timeout=2)
    assert d.clock.t <= 2.0 + 0.2 + 1e-9


def test_close_without_device_releases_display():
    page, d = page_with()
    page.close()
    page.close()
    assert d.calls == [("stop", "dev.headroid.sample"), ("release",)]
