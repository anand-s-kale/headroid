# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""The pytest plugin, run in-process with pytester against the fake RPC server."""

import json

import pytest

from headroid import pytest_plugin
from headroid.device import Device
from headroid.rpc import RpcClient

# Load the plugin module explicitly and block the entry-point copy, so the inner run works whether or not
# headroid is installed.
PLUGIN_ARGS = ("-p", "headroid.pytest_plugin", "-p", "no:headroid")


@pytest.fixture
def fake_connect(fake_server, monkeypatch):
    connects = []

    def open_device(serial):
        connects.append(serial)
        return Device(RpcClient("127.0.0.1", fake_server.port))

    monkeypatch.setattr(pytest_plugin, "_open_device", open_device)
    return connects


def _launched(fake_server):
    return [p["package"] for m, p in fake_server.calls if m == "app.launch"]


def test_fixtures_marker_app_and_session_device(pytester, fake_server, fake_connect):
    pytester.makepyfile(
        """
        import pytest
        from headroid import Page

        @pytest.mark.headroid(app="dev.headroid.sample")
        def test_one(page, device):
            assert isinstance(page, Page) and page.app == "dev.headroid.sample"
            assert page.display in device.displays

        @pytest.mark.headroid(app="other.app")
        def test_two(page):
            assert page.app == "other.app"
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS, "--strict-markers", "--headroid-serial", "ABC")
    result.assert_outcomes(passed=2)
    assert fake_connect == ["ABC"]  # one session-scoped device
    assert _launched(fake_server) == ["dev.headroid.sample", "other.app"]
    methods = [m for m, _ in fake_server.calls]
    assert methods.count("display.release") == 2 and methods.count("app.stop") == 2


def test_app_option_is_the_fallback(pytester, fake_server, fake_connect):
    pytester.makepyfile(
        """
        import pytest

        def test_option(page):
            assert page.app == "from.option"

        @pytest.mark.headroid(app="from.marker")
        def test_marker_wins(page):
            assert page.app == "from.marker"
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS, "--headroid-app", "from.option")
    result.assert_outcomes(passed=2)


def test_no_app_fails_with_a_hint(pytester, fake_server, fake_connect):
    pytester.makepyfile("def test_x(page):\n    pass\n")
    result = pytester.runpytest(*PLUGIN_ARGS)
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*no app for the `page` fixture*--headroid-app*"])


def test_failure_saves_screenshot_and_tree(pytester, fake_server, fake_connect):
    fake_server.tree = [{"id": "0", "text": "Sign in", "children": []}]
    pytester.makepyfile(
        test_login="""
        import pytest

        @pytest.mark.headroid(app="dev.headroid.sample")
        def test_fails(page):
            assert False, "boom"

        @pytest.mark.headroid(app="dev.headroid.sample")
        def test_passes(page):
            pass
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS)
    result.assert_outcomes(failed=1, passed=1)
    folder = pytester.path / "headroid-artifacts" / "test_login.py_test_fails"
    assert (folder / "screenshot.png").read_bytes().startswith(b"\x89PNG")
    assert json.loads((folder / "tree.json").read_text(encoding="utf-8"))[0]["text"] == "Sign in"
    result.stdout.fnmatch_lines(["*headroid artifacts*", "*headroid_screenshot: *screenshot.png"])
    assert not (pytester.path / "headroid-artifacts" / "test_login.py_test_passes").exists()
    # artifacts were taken before the page closed
    methods = [m for m, _ in fake_server.calls]
    assert methods.index("display.screenshot") < methods.index("display.release")


def test_failure_report_has_artifact_paths(pytester, fake_server, fake_connect):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.headroid(app="a.b")
        def test_fails(page):
            assert False
        """
    )
    reprec = pytester.inline_run(*PLUGIN_ARGS)
    (rep,) = [r for r in reprec.getreports("pytest_runtest_logreport") if r.when == "call"]
    props = dict(rep.user_properties)
    assert props["headroid_screenshot"].endswith("screenshot.png")
    assert props["headroid_tree"].endswith("tree.json")


def test_skipped_without_device(pytester, monkeypatch):
    monkeypatch.setattr(pytest_plugin, "list_devices", lambda adb="adb": [])
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.headroid(app="a.b")
        def test_needs_phone(page):
            pass

        def test_plain():
            pass
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS, "-rs")
    result.assert_outcomes(skipped=1, passed=1)
    result.stdout.fnmatch_lines(["*no Android device attached*"])


@pytest.mark.parametrize(
    ("devices", "serial", "reason"),
    [
        ([{"serial": "A", "state": "unauthorized"}], None, "no Android device attached"),
        (
            [{"serial": "A", "state": "device"}, {"serial": "B", "state": "device"}],
            None,
            "--headroid-serial",
        ),
        ([{"serial": "A", "state": "device"}], "Z", "device Z is not attached"),
        ([{"serial": "A", "state": "device"}], "A", None),
        ([{"serial": "A", "state": "device"}], None, None),
    ],
)
def test_no_device_reason(monkeypatch, devices, serial, reason):
    monkeypatch.setattr(pytest_plugin, "list_devices", lambda adb="adb": devices)
    got = pytest_plugin._no_device_reason(serial)
    assert got is None if reason is None else reason in got


def test_adb_missing_is_a_skip_reason(monkeypatch):
    def missing(adb="adb"):
        raise pytest_plugin.AdbError("adb not found: adb")

    monkeypatch.setattr(pytest_plugin, "list_devices", missing)
    assert "adb not found" in pytest_plugin._no_device_reason(None)
