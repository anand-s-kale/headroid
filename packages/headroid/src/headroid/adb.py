# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Thin wrapper over the adb command line."""

from __future__ import annotations

import re
import subprocess


class AdbError(RuntimeError):
    """adb failed or was used ambiguously."""


def list_devices(adb_path: str = "adb") -> list[dict]:
    """Returns [{"serial", "state", "model"}] from `adb devices -l`."""
    try:
        proc = subprocess.run(
            [adb_path, "devices", "-l"], capture_output=True, text=True, timeout=30, check=False
        )
    except FileNotFoundError as e:
        raise AdbError(f"adb not found: {adb_path}") from e
    except subprocess.TimeoutExpired as e:
        raise AdbError("adb devices timed out") from e
    devices = []
    for ln in (proc.stdout or "").splitlines()[1:]:
        parts = ln.split()
        if len(parts) < 2:
            continue
        m = re.search(r"\bmodel:(\S+)", ln)
        model = m.group(1).replace("_", " ") if m else ""
        devices.append({"serial": parts[0], "state": parts[1], "model": model})
    return devices


class Adb:
    def __init__(self, serial: str | None = None, adb_path: str = "adb"):
        self.serial = serial
        self.adb_path = adb_path
        self._checked = False

    def _base(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _devices(self) -> list[str]:
        try:
            proc = subprocess.run(
                [self.adb_path, "devices"], capture_output=True, text=True, timeout=30, check=False
            )
        except FileNotFoundError as e:
            raise AdbError(f"adb not found: {self.adb_path}") from e
        out = proc.stdout or ""
        return [ln.split()[0] for ln in out.splitlines()[1:] if re.search(r"\sdevice\b", ln)]

    def relocate(self, hardware_serial: str) -> bool:
        """Finds this phone again after a reconnect and switches to it.

        A wireless phone can come back under another adb serial (its mDNS name or ip:port), so the attached
        devices are matched on their hardware serial (ro.serialno). Returns False while it is not attached.
        """
        attached = self._devices()
        if self.serial in attached:
            return True
        for serial in attached:
            try:
                found = Adb(serial, self.adb_path).shell("getprop ro.serialno").strip()
            except AdbError:
                continue
            if found == hardware_serial:
                self.serial = serial
                return True
        return False

    def _ensure_unambiguous(self) -> None:
        if self.serial or self._checked:
            return
        devices = self._devices()
        if len(devices) > 1:
            raise AdbError(
                "multiple adb devices attached (" + ", ".join(devices) + "); "
                "pass an explicit serial"
            )
        self._checked = True

    def run(self, *args: str, timeout: float = 30) -> str:
        self._ensure_unambiguous()
        cmd = self._base() + [str(a) for a in args]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except FileNotFoundError as e:
            raise AdbError(f"adb not found: {self.adb_path}") from e
        except subprocess.TimeoutExpired as e:
            raise AdbError(f"adb timed out: {' '.join(cmd)}") from e
        if proc.returncode != 0:
            raise AdbError(f"adb failed ({proc.returncode}): {(proc.stderr or proc.stdout).strip()}")
        return proc.stdout or ""

    def shell(self, cmd: str) -> str:
        return self.run("shell", cmd)

    def push(self, local: str, remote: str) -> None:
        self.run("push", str(local), remote, timeout=120)

    def forward(self, remote: str = "localabstract:headroid") -> int:
        out = self.run("forward", "tcp:0", remote).strip()
        m = re.search(r"\d+", out)
        if not m:
            raise AdbError(f"could not parse forwarded port from adb output: {out!r}")
        return int(m.group())

    def remove_forward(self, port: int) -> None:
        self.run("forward", "--remove", f"tcp:{port}")

    def popen_shell(self, cmd: str) -> subprocess.Popen:
        self._ensure_unambiguous()
        return subprocess.Popen(
            self._base() + ["shell", cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
