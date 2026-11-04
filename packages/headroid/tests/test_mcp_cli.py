# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import os
import sys
import types

import pytest

from headroid import cli

EXPECTED = {
    "ARTEMIS_DRIVER": "headroid",
    "ARTEMIS_MCP_TOOLS": "mobile_observe,mobile_act,mobile_session_end",
    "ARTEMIS_MCP_INLINE_SCREENSHOT": "1",
    "ARTEMIS_KEEP_DEVICE_AWAKE": "0",
}


def _with_serial(serial):
    return {**EXPECTED, "ARTEMIS_DEVICE_ID": serial, "ADB_DEVICE_SERIAL": serial}


@pytest.fixture(autouse=True)
def _restore_environ():
    """cli._mcp sets os.environ for the ARTEMIS server; put it back after each test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def _devs(monkeypatch, devices):
    monkeypatch.setattr(cli, "list_devices", lambda adb: devices)


def _fake_server(monkeypatch, main, on_import=None):
    """Installs a fake mcp_server.server. on_import(os.environ) runs when cli imports it, as ARTEMIS's .env
    loading does."""
    pkg = types.ModuleType("mcp_server")
    mod = types.ModuleType("mcp_server.server")
    mod.main = main
    pkg.server = mod
    pkg.__path__ = []  # a package, so the submodule import goes through sys.meta_path
    monkeypatch.setitem(sys.modules, "mcp_server", pkg)
    if on_import is None:
        monkeypatch.setitem(sys.modules, "mcp_server.server", mod)
        return
    monkeypatch.delitem(sys.modules, "mcp_server.server", raising=False)

    class Loader:
        def create_module(self, spec):
            return mod

        def exec_module(self, module):
            on_import(os.environ)

    class Finder:
        def find_spec(self, name, path=None, target=None):
            return importlib.util.spec_from_loader(name, Loader()) if name == "mcp_server.server" else None

    monkeypatch.setattr(sys, "meta_path", [Finder(), *sys.meta_path])


def test_mcp_env(monkeypatch):
    assert cli.mcp_env("ABC") == _with_serial("ABC")
    _devs(monkeypatch, [{"serial": "ONE", "state": "device", "model": "m"}])
    env = cli.mcp_env(None)
    assert env["ADB_DEVICE_SERIAL"] == env["ARTEMIS_DEVICE_ID"] == "ONE"
    _devs(monkeypatch, [
        {"serial": "A", "state": "device", "model": "m1"},
        {"serial": "B", "state": "device", "model": "m2"},
    ])
    with pytest.raises(SystemExit) as e:
        cli.mcp_env(None)
    assert "A" in str(e.value) and "B" in str(e.value)


def test_mcp_env_turns_off_artemis_awake_service():
    # ARTEMIS's awake service would set stay_on_while_plugged_in and wake the phone's own screen.
    assert cli.mcp_env("ABC")["ARTEMIS_KEEP_DEVICE_AWAKE"] == "0"


def test_mcp_without_artemis_explains(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "mcp_server", None)  # makes the import raise ImportError
    monkeypatch.setitem(sys.modules, "mcp_server.server", None)
    assert cli.main(["mcp", "--serial", "ABC"]) == 2
    out = capsys.readouterr()
    assert out.out == ""
    assert 'pip install "headroid[artemis]"' in out.err
    if sys.version_info < (3, 12):
        assert "Python 3.12" in out.err


def test_mcp_runs_server_with_env(monkeypatch, capsys):
    seen = {}
    _fake_server(monkeypatch, lambda: seen.update(dict(os.environ)))
    for k in _with_serial("x"):
        monkeypatch.delenv(k, raising=False)
    assert cli.main(["mcp", "--serial", "ABC"]) == 0
    for k, v in _with_serial("ABC").items():
        assert seen[k] == v
    assert capsys.readouterr().out == ""


def test_mcp_restores_env_a_dotenv_changed_at_import(monkeypatch, capsys):
    seen = {}

    def dotenv(environ):
        environ["ARTEMIS_DRIVER"] = "adb"
        environ["ADB_DEVICE_SERIAL"] = "OTHER"
        environ["ARTEMIS_DEVICE_ID"] = "OTHER"
        environ["ARTEMIS_MCP_TOOLS"] = "mobile_run_task"
        environ["ARTEMIS_KEEP_DEVICE_AWAKE"] = "1"

    _fake_server(monkeypatch, lambda: seen.update(dict(os.environ)), on_import=dotenv)
    assert cli.main(["mcp", "--serial", "ABC"]) == 0
    for k, v in _with_serial("ABC").items():
        assert seen[k] == v, k
    out = capsys.readouterr()
    assert out.out == ""
    assert "ADB_DEVICE_SERIAL" in out.err and "restored" in out.err


def test_mcp_refuses_when_a_dotenv_changed_inline_screenshot(monkeypatch, capsys):
    served = []

    def dotenv(environ):
        environ["ARTEMIS_MCP_INLINE_SCREENSHOT"] = "0"

    _fake_server(monkeypatch, lambda: served.append(True), on_import=dotenv)
    assert cli.main(["mcp", "--serial", "ABC"]) == 1
    out = capsys.readouterr()
    assert served == []
    assert out.out == ""
    assert "ARTEMIS_MCP_INLINE_SCREENSHOT" in out.err and ".env" in out.err


def test_mcp_bad_tool_allowlist_is_an_error_not_a_hang(monkeypatch, capsys):
    def boom():
        raise ValueError("unknown tool 'x'")

    _fake_server(monkeypatch, boom)
    assert cli.main(["mcp", "--serial", "ABC"]) == 1
    assert "unknown tool" in capsys.readouterr().err
