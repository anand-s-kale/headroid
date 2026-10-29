# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import subprocess
from types import SimpleNamespace

import pytest

from headroid.adb import Adb, AdbError
from headroid.server import MAIN_CLASS, REMOTE_JAR, ServerProcess


def _fake_run(devices_out="List of devices attached\nAAA\tdevice\n", forward_out="41234\n"):
    def run(cmd, **kw):
        if cmd[-1] == "devices":
            return SimpleNamespace(returncode=0, stdout=devices_out, stderr="")
        if "forward" in cmd and "--remove" not in cmd:
            return SimpleNamespace(returncode=0, stdout=forward_out, stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return run


def test_forward_parses_port(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run())
    assert Adb("AAA").forward() == 41234


def test_refuses_ambiguous_device(monkeypatch):
    out = "List of devices attached\nAAA\tdevice\nBBB\tdevice\n"
    monkeypatch.setattr(subprocess, "run", _fake_run(devices_out=out))
    with pytest.raises(AdbError, match="multiple"):
        Adb(None).shell("true")
    # an explicit serial is fine
    assert Adb("AAA").shell("true") == ""


def test_single_device_allowed(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run())
    assert Adb(None).shell("true") == ""


def test_start_order(fake_server, tmp_path):
    jar = tmp_path / "s.jar"
    jar.write_bytes(b"x")
    log = []

    class FakeProc:
        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    class FakeAdb:
        def push(self, local, remote):
            log.append(("push", local, remote))

        def popen_shell(self, cmd):
            log.append(("shell", cmd))
            return FakeProc()

        def forward(self, remote):
            log.append(("forward", remote))
            return fake_server.port

        def remove_forward(self, port):
            log.append(("remove_forward", port))

    sp = ServerProcess(FakeAdb(), str(jar))
    sp.start()
    assert [e[0] for e in log] == ["push", "shell", "forward"]
    assert log[0][2] == REMOTE_JAR
    assert MAIN_CLASS in log[1][1] and "app_process" in log[1][1]
    assert "socket=headroid" in log[1][1]
    sp.stop()
    assert log[-1] == ("remove_forward", fake_server.port)
