# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import os
import sys
import types

import pytest

from headroid import cli

EXPECTED = {
    "ARTEMIS_DRIVER": "headroid",
    "ARTEMIS_MCP_TOOLS": "mobile_observe,mobile_act,mobile_session_end",
    "ARTEMIS_MCP_INLINE_SCREENSHOT": "1",
}


def _devs(monkeypatch, devices):
    monkeypatch.setattr(cli, "list_devices", lambda adb: devices)


def test_mcp_env(monkeypatch):
    assert cli.mcp_env("ABC") == {**EXPECTED, "ADB_DEVICE_SERIAL": "ABC"}
    _devs(monkeypatch, [{"serial": "ONE", "state": "device", "model": "m"}])
    assert cli.mcp_env(None)["ADB_DEVICE_SERIAL"] == "ONE"
    _devs(monkeypatch, [
        {"serial": "A", "state": "device", "model": "m1"},
        {"serial": "B", "state": "device", "model": "m2"},
    ])
    with pytest.raises(SystemExit) as e:
        cli.mcp_env(None)
    assert "A" in str(e.value) and "B" in str(e.value)


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
    pkg = types.ModuleType("mcp_server")
    mod = types.ModuleType("mcp_server.server")
    mod.main = lambda: seen.update(dict(os.environ))
    pkg.server = mod
    monkeypatch.setitem(sys.modules, "mcp_server", pkg)
    monkeypatch.setitem(sys.modules, "mcp_server.server", mod)
    for k in (*EXPECTED, "ADB_DEVICE_SERIAL"):
        monkeypatch.delenv(k, raising=False)
    assert cli.main(["mcp", "--serial", "ABC"]) == 0
    for k, v in {**EXPECTED, "ADB_DEVICE_SERIAL": "ABC"}.items():
        assert seen[k] == v
    assert capsys.readouterr().out == ""
    for k in (*EXPECTED, "ADB_DEVICE_SERIAL"):
        monkeypatch.delenv(k, raising=False)


def test_mcp_bad_tool_allowlist_is_an_error_not_a_hang(monkeypatch, capsys):
    mod = types.ModuleType("mcp_server.server")
    def boom():
        raise ValueError("unknown tool 'x'")
    mod.main = boom
    monkeypatch.setitem(sys.modules, "mcp_server", types.ModuleType("mcp_server"))
    monkeypatch.setitem(sys.modules, "mcp_server.server", mod)
    assert cli.main(["mcp", "--serial", "ABC"]) == 1
    assert "unknown tool" in capsys.readouterr().err
    for k in (*EXPECTED, "ADB_DEVICE_SERIAL"):
        monkeypatch.delenv(k, raising=False)
