# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import pathlib

_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "agent_e2e.py"
_spec = importlib.util.spec_from_file_location("agent_e2e", _PATH)
agent_e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent_e2e)

ELEMENTS = (
    "[1] Text: 'Login' | Bounds: [0,40][1000,90]\n"
    "[2] Hint: 'Email' | Bounds: [30,100][970,150]\n"
    "[3] Text: 'Sign in' | Bounds: [30,300][970,360]\n"
    "[4] OCR Text: 'Password' | Bounds: [30,160][970,210] | Warning: overlaps [2]"
)


def test_parse_elements():
    assert agent_e2e.parse_elements(ELEMENTS) == [(1, "Login"), (2, "Email"), (3, "Sign in"), (4, "Password")]


def test_find_index_is_case_insensitive_and_exact():
    assert agent_e2e.find_index(ELEMENTS, "email") == 2
    assert agent_e2e.find_index(ELEMENTS, "SIGN IN") == 3
    assert agent_e2e.find_index(ELEMENTS, "Sign") is None


def test_find_index_handles_missing_text():
    assert agent_e2e.find_index(None, "Login") is None
    assert agent_e2e.find_index("Not available due to hierarchy error.", "Login") is None


def test_stay_on_setting_only_reads():
    class FakeAdb:
        def __init__(self):
            self.commands = []

        def shell(self, command):
            self.commands.append(command)
            return "0\n"

    adb = FakeAdb()
    assert agent_e2e.stay_on_setting(adb) == "0"
    assert adb.commands == ["settings get global stay_on_while_plugged_in"]
