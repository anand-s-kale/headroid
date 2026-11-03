# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import PNG

from headroid import cli, doctor, jar
from headroid.adb import Adb, list_devices
from headroid.device import Device, Display
from headroid.rpc import RpcClient
from headroid.server import ServerProcess

# ---- jar resolution ----


def test_jar_argument_wins(monkeypatch):
    monkeypatch.setenv("HEADROID_SERVER_JAR", "/env.jar")
    assert jar.resolve_jar("/arg.jar") == "/arg.jar"


def test_jar_env_before_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("HEADROID_SERVER_JAR", "/env.jar")
    monkeypatch.setattr(jar, "_bundled", lambda: tmp_path / "b.jar")
    assert jar.resolve_jar() == "/env.jar"


def test_jar_bundle_before_source(monkeypatch, tmp_path):
    monkeypatch.delenv("HEADROID_SERVER_JAR", raising=False)
    monkeypatch.setattr(jar, "_bundled", lambda: tmp_path / "b.jar")
    assert jar.resolve_jar() == str(tmp_path / "b.jar")


def test_jar_source_checkout(monkeypatch, tmp_path):
    built = tmp_path / "headroid-server.jar"
    built.write_bytes(b"x")
    monkeypatch.delenv("HEADROID_SERVER_JAR", raising=False)
    monkeypatch.setattr(jar, "_bundled", lambda: None)
    monkeypatch.setattr(jar, "_source_checkout", lambda: built)
    assert jar.resolve_jar() == str(built)


def test_jar_missing_explains_fix(monkeypatch, tmp_path):
    monkeypatch.delenv("HEADROID_SERVER_JAR", raising=False)
    monkeypatch.setattr(jar, "_bundled", lambda: None)
    monkeypatch.setattr(jar, "_source_checkout", lambda: tmp_path / "nope.jar")
    with pytest.raises(FileNotFoundError, match=r"gradlew :server:headroidJar.*HEADROID_SERVER_JAR"):
        Device.connect()


# ---- socket ----


def test_socket_unique_and_overridable():
    a, b = ServerProcess(Adb("A"), "x.jar"), ServerProcess(Adb("A"), "x.jar")
    assert a.socket.startswith("headroid-") and len(a.socket) == len("headroid-") + 8
    assert a.socket != b.socket
    assert ServerProcess(Adb("A"), "x.jar", socket="mine").socket == "mine"


# ---- wait_for / click / fill ----


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _display(fake_server, width=720, height=1600):
    c = Clock()
    return Display(
        RpcClient("127.0.0.1", fake_server.port),
        {"displayId": 1, "width": width, "height": height},
        clock=c.now,
        sleep=c.sleep,
    )


def _node(bounds, **kw):
    return {"id": "0", "rid": "p:id/btn", "text": "Go", "desc": "", "bounds": bounds,
            "visible": True, "children": [], **kw}


def test_wait_for_needs_two_stable_reads(fake_server):
    d = _display(fake_server)
    fake_server.tree = [_node([100, 100, 300, 200])]
    assert d.wait_for(rid="btn")["bounds"] == [100, 100, 300, 200]
    assert [m for m, _ in fake_server.calls].count("ui.tree") == 2


def test_wait_for_skips_offscreen_animated_position(fake_server):
    d = _display(fake_server)
    fake_server.tree = [_node([820, 100, 1020, 200])]  # shifted by one display width
    with pytest.raises(TimeoutError, match="rid"):
        d.wait_for(rid="btn", timeout=1.0)


def test_wait_for_invisible_and_timeout_names_criteria(fake_server):
    d = _display(fake_server)
    fake_server.tree = [_node([0, 0, 10, 10], visible=False)]
    with pytest.raises(TimeoutError, match="Go"):
        d.wait_for(text="Go", timeout=1.0)


def test_wait_for_moving_node_not_settled(fake_server):
    d = _display(fake_server)
    reads = iter([[820, 0, 900, 50], [500, 0, 600, 50], [300, 0, 400, 50], [300, 0, 400, 50]])
    d.tree = lambda: [_node(next(reads))]
    assert d.wait_for(rid="btn")["bounds"] == [300, 0, 400, 50]


def test_click_taps_centre_and_fill_types(fake_server):
    d = _display(fake_server)
    fake_server.tree = [_node([100, 100, 300, 201])]
    d.fill("hello", rid="btn")
    calls = fake_server.calls
    assert ("input.tap", {"displayId": 1, "x": 200, "y": 150}) in calls
    assert calls[-1] == ("input.text", {"displayId": 1, "text": "hello"})
    assert [m for m, _ in calls].index("input.tap") < [m for m, _ in calls].index("input.text")


# ---- adb devices / CLI ----

DEVICES_L = (
    "List of devices attached\n"
    "ABC123\tdevice usb:1-1 product:peridot model:POCO_F6 device:peridot transport_id:1\n"
    "DEF456\tunauthorized usb:1-2 transport_id:2\n"
)


def test_list_devices(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=DEVICES_L, stderr="")
    )
    assert list_devices() == [
        {"serial": "ABC123", "state": "device", "model": "POCO F6"},
        {"serial": "DEF456", "state": "unauthorized", "model": ""},
    ]


def test_cli_devices_prints(monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=DEVICES_L, stderr="")
    )
    assert cli.main(["devices"]) == 0
    out = capsys.readouterr().out
    assert "ABC123\tdevice\tPOCO F6" in out and "DEF456\tunauthorized" in out


def test_cli_jar_optional_in_parser():
    for argv in (["info"], ["tree"], ["screenshot"], ["doctor"], ["launch", "a.b"]):
        assert cli._parser().parse_args(argv).jar is None
    a = cli._parser().parse_args(["launch", "a.b", "--activity", "X", "--screenshot", "o.png"])
    assert (a.wait, a.activity, a.screenshot) == (3.0, "X", "o.png")


def test_cli_launch(fake_server, monkeypatch, tmp_path, capsys):
    dev = Device(RpcClient("127.0.0.1", fake_server.port))
    monkeypatch.setattr(cli.Device, "connect", classmethod(lambda cls, **kw: dev))
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)
    out = tmp_path / "o.png"
    assert cli.main(["launch", "dev.headroid.sample", "--screenshot", str(out), "--wait", "0"]) == 0
    assert out.read_bytes() == PNG
    methods = [m for m, _ in fake_server.calls]
    assert methods.index("app.launch") < methods.index("display.screenshot")
    assert "display.release" in methods


# ---- doctor ----


def _fake_adb(monkeypatch, devices=DEVICES_L, api="34", maker="Xiaomi", adb_missing=False):
    def run(cmd, **kw):
        if adb_missing:
            raise FileNotFoundError(cmd[0])
        if cmd[-1] == "version":
            return SimpleNamespace(returncode=0, stdout="Android Debug Bridge version 1.0.41\n", stderr="")
        if cmd[-2:] == ["devices", "-l"]:
            return SimpleNamespace(returncode=0, stdout=devices, stderr="")
        if cmd[-1].endswith("ro.build.version.sdk"):
            return SimpleNamespace(returncode=0, stdout=api + "\n", stderr="")
        if cmd[-1].endswith("ro.product.manufacturer"):
            return SimpleNamespace(returncode=0, stdout=maker + "\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)


def _status(checks):
    return {c.name: c.status for c in checks}


def _connect_factory(fake_server, png_ok=True):
    def connect(serial=None, jar=None):
        dev = Device(RpcClient("127.0.0.1", fake_server.port))
        dev.info = lambda: {"sdk": 34, "model": "POCO F6", "capabilities": ["display"]}
        return dev

    return connect


@pytest.fixture
def jar_file(tmp_path):
    p = tmp_path / "headroid-server.jar"
    p.write_bytes(b"x")
    return str(p)


def test_doctor_all_pass_with_xiaomi_warn(monkeypatch, fake_server, jar_file):
    _fake_adb(monkeypatch)
    checks = doctor.run_doctor("ABC123", jar_file, connect=_connect_factory(fake_server))
    st = _status(checks)
    assert st["manufacturer"] == "WARN"
    assert st["hidden display screenshot"] == "PASS" and st["server.info"] == "PASS"
    assert doctor.ok(checks)
    assert "display.release" in [m for m, _ in fake_server.calls]


def test_doctor_no_adb(monkeypatch):
    _fake_adb(monkeypatch, adb_missing=True)
    checks = doctor.run_doctor()
    assert checks[0].status == "FAIL" and "platform-tools" in checks[0].fix
    assert not doctor.ok(checks)


def test_doctor_multiple_devices_needs_serial(monkeypatch):
    devices = "List of devices attached\nA\tdevice model:X\nB\tdevice model:Y\n"
    _fake_adb(monkeypatch, devices=devices)
    checks = doctor.run_doctor()
    assert checks[-1].status == "FAIL" and "--serial" in checks[-1].fix and "A (device)" in checks[-1].detail


def test_doctor_unauthorized_and_offline(monkeypatch):
    _fake_adb(monkeypatch)
    c = doctor.run_doctor("DEF456")
    assert c[-1].status == "FAIL" and "USB debugging prompt" in c[-1].fix
    _fake_adb(monkeypatch, devices="List of devices attached\nZ\toffline\n")
    c = doctor.run_doctor()
    assert c[-1].status == "FAIL" and "reconnect" in c[-1].fix


def test_doctor_old_android_fails(monkeypatch):
    _fake_adb(monkeypatch, api="29")
    c = doctor.run_doctor("ABC123")
    assert c[-1].name == "Android API level" and c[-1].status == "FAIL"


def test_doctor_unverified_api_warns(monkeypatch, fake_server, jar_file):
    _fake_adb(monkeypatch, api="31", maker="Google")
    st = _status(doctor.run_doctor("ABC123", jar_file, connect=_connect_factory(fake_server)))
    assert st["Android API level"] == "WARN" and "manufacturer" not in st


def test_doctor_missing_jar(monkeypatch):
    _fake_adb(monkeypatch)
    monkeypatch.delenv("HEADROID_SERVER_JAR", raising=False)
    monkeypatch.setattr(jar, "_bundled", lambda: None)
    monkeypatch.setattr(jar, "_source_checkout", lambda: Path("/nonexistent/headroid-server.jar"))
    c = doctor.run_doctor("ABC123")
    assert c[-1].name == "server jar" and c[-1].status == "FAIL"
    assert "headroidJar" in c[-1].fix


def test_doctor_server_start_failure(monkeypatch, jar_file):
    _fake_adb(monkeypatch)

    def boom(**kw):
        raise TimeoutError("server did not come up")

    c = doctor.run_doctor("ABC123", jar_file, connect=boom)
    assert c[-1].name == "server starts" and c[-1].status == "FAIL"


def test_cli_doctor_exit_codes(monkeypatch, capsys):
    _fake_adb(monkeypatch, adb_missing=True)
    assert cli.main(["doctor"]) == 1
    assert "[FAIL] adb on PATH" in capsys.readouterr().out
