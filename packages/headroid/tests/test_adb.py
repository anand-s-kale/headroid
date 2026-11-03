# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import subprocess
from types import SimpleNamespace

import pytest

from headroid.adb import Adb, AdbError
from headroid.server import MAIN_CLASS, ServerProcess, remote_jar_path


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

    class FakeAdb:
        def push(self, local, remote):
            log.append(("push", local, remote))

        def shell(self, cmd):
            log.append(("shell", cmd))
            return ""

        def forward(self, remote):
            log.append(("forward", remote))
            return fake_server.port

        def remove_forward(self, port):
            log.append(("remove_forward", port))

    sp = ServerProcess(FakeAdb(), str(jar))
    sp.start()
    assert [e[0] for e in log] == ["shell", "push", "shell", "forward"]
    assert log[0][1] == "getprop ro.serialno"
    assert log[1][2] == remote_jar_path(str(jar))
    assert log[1][2].startswith("/data/local/tmp/headroid-server-")
    assert MAIN_CLASS in log[2][1] and "app_process" in log[2][1]
    assert "socket=headroid" in log[2][1]
    # detached from the adb shell, so a dropped wireless connection does not kill the server
    assert "setsid app_process" in log[2][1] and log[2][1].rstrip().endswith("&")
    assert "grace_ms=60000" in log[2][1]
    sp.stop()
    assert log[-1] == ("remove_forward", fake_server.port)


class _ForwardOnlyAdb:
    def __init__(self, port):
        self.port = port
        self.forwards = 0

    def forward(self, remote):
        self.forwards += 1
        return self.port

    def remove_forward(self, port):
        pass


def _reconnecting(fake_server):
    from headroid.rpc import RpcClient
    from headroid.server import ReconnectingClient

    sp = ServerProcess(_ForwardOnlyAdb(fake_server.port), "unused.jar", grace_s=5)
    sp.port = fake_server.port
    return sp, ReconnectingClient(sp, RpcClient("127.0.0.1", fake_server.port))


def test_reads_are_resent_after_a_dropped_connection(fake_server):
    sp, client = _reconnecting(fake_server)
    fake_server.drop_next = True
    assert client.call("display.screenshot", displayId=1)["format"] == "png"
    assert sp.adb.forwards == 1  # a new forward for the new transport
    client.close()


def test_actions_are_not_resent_after_a_dropped_connection(fake_server):
    import pytest

    _, client = _reconnecting(fake_server)
    fake_server.drop_next = True
    with pytest.raises(ConnectionError, match="may or may not have run"):
        client.call("input.tap", displayId=1, x=1, y=1)
    taps = [m for m, _ in fake_server.calls if m == "input.tap"]
    assert len(taps) == 1
    assert client.call("server.info") == {}  # the reconnected client works
    client.close()


def test_relocate_finds_the_phone_under_a_new_serial(monkeypatch):
    # after a wireless reconnect adb listed the same phone as ip:port instead of its mDNS name
    def fake_run(cmd, **kw):
        if cmd[1:] == ["devices"]:
            out = "List of devices attached\nemulator-5554\tdevice\n192.168.31.198:45267\tdevice\n"
        elif cmd[-1] == "getprop ro.serialno":
            out = {"emulator-5554": "EMU1\n", "192.168.31.198:45267": "c24b2c3f\n"}[cmd[2]]
        else:
            out = ""
        return subprocess.CompletedProcess(cmd, 0, out, "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adb = Adb("adb-c24b2c3f-k1Tv5k._adb-tls-connect._tcp")
    assert adb.relocate("c24b2c3f")
    assert adb.serial == "192.168.31.198:45267"
    assert not Adb("gone").relocate("nope")
