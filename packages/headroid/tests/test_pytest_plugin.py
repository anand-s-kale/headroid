# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""The pytest plugin, run in-process with pytester against the fake RPC server."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

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

    def connect(cls, serial=None, jar=None):
        connects.append(serial)
        return Device(RpcClient("127.0.0.1", fake_server.port))

    monkeypatch.setattr(
        pytest_plugin, "list_devices", lambda adb="adb": [{"serial": "ABC", "state": "device"}]
    )
    monkeypatch.setattr(pytest_plugin.Device, "connect", classmethod(connect))
    return connects


def _launched(fake_server):
    return [p["package"] for m, p in fake_server.calls if m == "app.launch"]


def test_fixtures_marker_app_and_session_device(pytester, fake_server, fake_connect):
    pytester.makepyfile(
        """
        import pytest
        from headroid import Page

        @pytest.mark.headroid(app="dev.headroid.sample")
        def test_one(headroid_page, headroid_device):
            assert isinstance(headroid_page, Page) and headroid_page.app == "dev.headroid.sample"
            assert headroid_page.display in headroid_device.displays

        @pytest.mark.headroid("other.app")
        def test_two(headroid_page):
            assert headroid_page.app == "other.app"
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS, "--strict-markers", "--headroid-serial", "ABC")
    result.assert_outcomes(passed=2)
    assert fake_connect == ["ABC"]  # one session-scoped device
    assert _launched(fake_server) == ["dev.headroid.sample", "other.app"]
    methods = [m for m, _ in fake_server.calls]
    assert methods.count("display.release") == 2 and methods.count("app.stop") == 2


def test_alias_in_project_conftest(pytester, fake_server, fake_connect):
    pytester.makeconftest(
        """
        import pytest

        @pytest.fixture
        def page(headroid_page):
            return headroid_page
        """
    )
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.headroid(app="a.b")
        def test_x(page):
            assert page.app == "a.b"
        """
    )
    pytester.runpytest(*PLUGIN_ARGS).assert_outcomes(passed=1)


def test_app_option_is_the_fallback(pytester, fake_server, fake_connect):
    pytester.makepyfile(
        """
        import pytest

        def test_option(headroid_page):
            assert headroid_page.app == "from.option"

        @pytest.mark.headroid(app="from.marker")
        def test_marker_wins(headroid_page):
            assert headroid_page.app == "from.marker"
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS, "--headroid-app", "from.option")
    result.assert_outcomes(passed=2)


def test_no_app_fails_with_a_hint(pytester, fake_server, fake_connect):
    pytester.makepyfile("def test_x(headroid_page):\n    pass\n")
    result = pytester.runpytest(*PLUGIN_ARGS)
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*no app for the `headroid_page` fixture*--headroid-app*"])


def test_bad_marker_is_a_clear_error(pytester, fake_server, fake_connect):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.headroid("a.b", "c.d")
        def test_two_apps(headroid_page):
            pass

        @pytest.mark.headroid(package="a.b")
        def test_wrong_kwarg(headroid_page):
            pass

        @pytest.mark.headroid("a.b", app="a.b")
        def test_both(headroid_page):
            pass
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS)
    result.assert_outcomes(errors=3)
    result.stdout.fnmatch_lines(
        ['*headroid marker: expected headroid("pkg")*', "*give the app once*"]
    )
    assert _launched(fake_server) == []


def test_failure_saves_screenshot_and_tree(pytester, fake_server, fake_connect):
    fake_server.tree = [{"id": "0", "text": "Sign in", "children": []}]
    pytester.makepyfile(
        test_login="""
        import pytest

        @pytest.mark.headroid(app="dev.headroid.sample")
        def test_fails(headroid_page):
            assert False, "boom"

        @pytest.mark.headroid(app="dev.headroid.sample")
        def test_passes(headroid_page):
            pass
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS)
    result.assert_outcomes(failed=1, passed=1)
    root = pytester.path / "headroid-artifacts"
    (folder,) = list(root.iterdir())  # nothing for the passing test
    assert folder.name.startswith("test_login.py_test_fails-")
    assert (folder / "screenshot.png").read_bytes().startswith(b"\x89PNG")
    assert json.loads((folder / "tree.json").read_text(encoding="utf-8"))[0]["text"] == "Sign in"
    result.stdout.fnmatch_lines(["*headroid artifacts*", "*headroid_screenshot: *screenshot.png"])
    # artifacts were taken before the page closed
    methods = [m for m, _ in fake_server.calls]
    assert methods.index("display.screenshot") < methods.index("display.release")


def test_artifact_paths_reach_report_and_junit_xml(pytester, fake_server, fake_connect):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.headroid(app="a.b")
        def test_fails(headroid_page):
            assert False
        """
    )
    xml = pytester.path / "junit.xml"
    reprec = pytester.inline_run(*PLUGIN_ARGS, f"--junitxml={xml}")
    (rep,) = [r for r in reprec.getreports("pytest_runtest_logreport") if r.when == "call"]
    props = dict(rep.user_properties)
    assert props["headroid_screenshot"].endswith("screenshot.png")
    assert props["headroid_tree"].endswith("tree.json")
    found = {p.get("name"): p.get("value") for p in ET.parse(xml).iter("property")}
    assert found["headroid_screenshot"].endswith("screenshot.png")
    assert found["headroid_tree"].endswith("tree.json")


def test_artifact_dir_failure_does_not_crash_pytest(pytester, fake_server, fake_connect):
    (pytester.path / "headroid-artifacts").write_text("a file where the folder should be")
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.headroid(app="a.b")
        def test_fails(headroid_page):
            assert False
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS)
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*headroid_artifacts_error:*"])


def test_artifact_name_is_short_unique_and_windows_safe():
    long_a = "tests/test_x.py::test_" + "a" * 300 + "[1]"
    long_b = "tests/test_x.py::test_" + "a" * 300 + "[2]"
    a, b = pytest_plugin._artifact_name(long_a), pytest_plugin._artifact_name(long_b)
    assert a != b and len(a) <= 80 and len(b) <= 80
    assert pytest_plugin._artifact_name("x.py::t[a/b]") != pytest_plugin._artifact_name(
        "x.py::t[a_b]"
    )
    assert not pytest_plugin._artifact_name("x.py::t[ends.]").split("-")[0].endswith(".")
    for reserved in ("con", "NUL.py::t", "com1", "LPT9.txt"):
        name = pytest_plugin._artifact_name(reserved)
        assert name.startswith("_"), name
    assert pytest_plugin._artifact_name("console.py::t").startswith("console")
    assert pytest_plugin._artifact_name("::")  # never empty


def test_skipped_without_device(pytester, monkeypatch):
    monkeypatch.setattr(pytest_plugin, "list_devices", lambda adb="adb": [])
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.headroid(app="a.b")
        def test_needs_phone(headroid_page):
            pass

        def test_plain():
            pass
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS, "-rs")
    result.assert_outcomes(skipped=1, passed=1)
    result.stdout.fnmatch_lines(["*no Android device attached*"])


def test_several_devices_is_a_usage_error_for_every_test(pytester, monkeypatch):
    two = [{"serial": "A", "state": "device"}, {"serial": "B", "state": "device"}]
    monkeypatch.setattr(pytest_plugin, "list_devices", lambda adb="adb": two)
    pytester.makepyfile(
        """
        def test_one(headroid_device):
            pass

        def test_two(headroid_device):
            pass
        """
    )
    result = pytester.runpytest(*PLUGIN_ARGS)
    result.assert_outcomes(errors=2)
    result.stdout.fnmatch_lines(["*several devices attached (A, B); pass --headroid-serial S*"])


@pytest.mark.parametrize(
    ("devices", "serial", "expected"),
    [
        ([], None, ("skip", "no Android device attached")),
        (
            [{"serial": "A", "state": "unauthorized"}, {"serial": "B", "state": "offline"}],
            None,
            ("skip", "A (unauthorized), B (offline); accept the USB debugging prompt"),
        ),
        (
            [{"serial": "A", "state": "device"}, {"serial": "B", "state": "device"}],
            None,
            ("fail", "several devices attached (A, B); pass --headroid-serial S"),
        ),
        (
            [{"serial": "A", "state": "device"}],
            "Z",
            ("fail", "--headroid-serial Z is not attached"),
        ),
        ([{"serial": "Z", "state": "unauthorized"}], "Z", ("fail", "Z (unauthorized)")),
        ([{"serial": "A", "state": "device"}], "A", None),
        ([{"serial": "A", "state": "device"}], None, None),
    ],
)
def test_device_problem(monkeypatch, devices, serial, expected):
    monkeypatch.setattr(pytest_plugin, "list_devices", lambda adb="adb": devices)
    got = pytest_plugin._device_problem(serial)
    if expected is None:
        assert got is None
    else:
        assert got[0] == expected[0] and expected[1] in got[1], got


def test_adb_missing_is_a_skip(monkeypatch):
    def missing(adb="adb"):
        raise pytest_plugin.AdbError("adb not found: adb")

    monkeypatch.setattr(pytest_plugin, "list_devices", missing)
    kind, reason = pytest_plugin._device_problem(None)
    assert kind == "skip" and "adb not found" in reason


def test_plugin_module_has_no_old_fixture_names():
    src = Path(pytest_plugin.__file__).read_text(encoding="utf-8")
    assert "def page(" not in src and "def device(" not in src
