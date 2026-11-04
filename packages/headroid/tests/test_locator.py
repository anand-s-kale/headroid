# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import builtins

import pytest
from fake_display import node, page_with

import headroid
from headroid import TimeoutError
from headroid.rpc import RpcError

EMAIL = node(rid="dev.headroid.sample:id/login_email", text="", bounds=(40, 300, 680, 380))
SIGN_IN = node(
    text="Sign in", rid="dev.headroid.sample:id/login_submit", bounds=(40, 500, 680, 580)
)
SIGN_UP = node(text="Sign up", bounds=(40, 600, 680, 680))


def root(*children):
    return [node(bounds=(0, 0, 720, 1600), children=children)]


def test_click_waits_for_element_that_appears_on_third_read():
    page, d = page_with(root(), root(), root(SIGN_IN))
    page.get_by_text("Sign in").click()
    # reads 1-2 empty, 3 first sighting, 4 same bounds -> settled
    assert d.tree_calls == 4
    assert d.calls == [("tap", 360, 540)]


def test_click_waits_until_offscreen_element_comes_on_screen():
    shifted = node(text="Sign in", bounds=(760, 500, 1400, 580))  # animated in from the right
    page, d = page_with(root(shifted), root(shifted), root(SIGN_IN))
    page.get_by_text("Sign in").click()
    assert d.calls == [("tap", 360, 540)]
    assert d.tree_calls == 4


def test_click_waits_for_moving_element_to_stop():
    a = node(text="Go", bounds=(300, 0, 400, 50))
    b = node(text="Go", bounds=(200, 0, 300, 50))
    page, d = page_with(root(a), root(b), root(b))
    page.get_by_text("Go").click()
    assert d.calls == [("tap", 250, 25)]


def test_locator_is_lazy_and_reresolved():
    page, d = page_with(root(SIGN_IN), root(SIGN_IN), root(SIGN_UP))
    loc = page.get_by_text("Sign in")
    assert d.tree_calls == 0
    assert loc.count() == 1 and loc.count() == 1
    assert loc.count() == 0  # the screen changed: the same locator sees it


def test_get_by_id_full_and_short_and_desc():
    settings = node(desc="Settings", bounds=(0, 0, 50, 50))
    page, _ = page_with(root(EMAIL, SIGN_IN, settings))
    assert page.get_by_id("login_email").count() == 1
    assert page.get_by_id("dev.headroid.sample:id/login_email").count() == 1
    assert page.get_by_id("email").count() == 0
    assert page.get_by_desc("Settings").is_visible()
    assert page.locator(text="Sign in", rid="login_submit").count() == 1
    assert page.locator(text="Sign in", rid="login_email").count() == 0


def test_get_by_text_not_exact_is_case_insensitive_substring():
    page, _ = page_with(root(SIGN_IN, SIGN_UP))
    assert page.get_by_text("sign", exact=False).count() == 2
    assert page.get_by_text("sign").count() == 0


def test_nth_first_last_and_text():
    page, _ = page_with(root(SIGN_IN, SIGN_UP))
    loc = page.get_by_text("SIGN", exact=False)
    assert loc.first.text() == "Sign in"
    assert loc.nth(1).text() == "Sign up"
    assert loc.last.text() == "Sign up"
    assert repr(loc.nth(1)) == "get_by_text('SIGN', exact=False).nth(1)"


def test_is_visible_false_for_hidden_or_offscreen():
    hidden = node(text="A", visible=False)
    off = node(text="B", bounds=(0, 1700, 100, 1800))
    page, _ = page_with(root(hidden, off))
    assert not page.get_by_text("A").is_visible()
    assert not page.get_by_text("B").is_visible()
    assert not page.get_by_text("C").is_visible()


def test_fill_clears_then_types():
    page, d = page_with(root(EMAIL))
    page.get_by_id("login_email").fill("demo@headroid.dev")
    assert d.calls == [("tap", 360, 340), ("clear_text",), ("type", "demo@headroid.dev")]


def test_fill_retries_clear_until_focus_lands():
    page, d = page_with(root(EMAIL), unfocused_clears=2)
    page.get_by_id("login_email").fill("x")
    assert [c[0] for c in d.calls] == [
        "tap",
        "clear_text_failed",
        "clear_text_failed",
        "clear_text",
        "type",
    ]


def test_fill_empty_only_clears():
    page, d = page_with(root(EMAIL))
    page.get_by_id("login_email").fill("")
    assert d.calls[-1] == ("clear_text",)


def test_fill_other_rpc_error_propagates():
    page, d = page_with(root(EMAIL))

    def boom():
        raise RpcError(-32000, "server error")

    d.clear_text = boom
    with pytest.raises(RpcError):
        page.get_by_id("login_email").fill("x")


def test_timeout_names_locator_state_and_closest_texts():
    page, d = page_with(root(SIGN_UP, node(text="Forgot password?")))
    with pytest.raises(TimeoutError) as e:
        page.get_by_text("Sign in").click(timeout=1)
    msg = str(e.value)
    assert "get_by_text('Sign in')" in msg and "within 1" in msg and "not found" in msg
    assert "'Sign up'" in msg and "Forgot" not in msg
    assert isinstance(e.value, builtins.TimeoutError)
    assert headroid.TimeoutError is TimeoutError
    assert d.clock.t == pytest.approx(1.0)


def test_timeout_reports_offscreen_and_rid_suggestions():
    off = node(rid="p:id/login_email", bounds=(760, 0, 900, 50))
    page, _ = page_with(root(off))
    with pytest.raises(TimeoutError, match=r"not found\)\. Closest on screen: 'login_email'"):
        page.get_by_id("login_emial").click(timeout=0.5)
    with pytest.raises(TimeoutError, match=r"found off screen at \[760, 0, 900, 50\]"):
        page.get_by_id("login_email").click(timeout=0.5)


def test_default_timeout_per_page():
    page, d = page_with(root())
    page.set_default_timeout(3)
    with pytest.raises(TimeoutError, match="within 3.0s"):
        page.get_by_text("x").click()
    assert d.clock.t == pytest.approx(3.0)


def test_text_does_not_need_on_screen():
    off = node(text="Below the fold", bounds=(0, 1700, 100, 1800))
    page, _ = page_with(root(off))
    assert page.get_by_text("Below", exact=False).text() == "Below the fold"


def test_locator_needs_a_criterion():
    page, _ = page_with()
    with pytest.raises(ValueError):
        page.locator()
