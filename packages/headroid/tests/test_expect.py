# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import pytest
from fake_display import node, page_with

from headroid import expect


def root(*children):
    return [node(bounds=(0, 0, 720, 1600), children=children)]


WELCOME = node(text="Welcome, demo", rid="p:id/form_title")


def test_to_be_visible_passes_once_element_appears():
    page, d = page_with(root(), root(), root(WELCOME))
    expect(page.get_by_id("form_title")).to_be_visible()
    assert d.tree_calls == 3


def test_to_be_visible_timeout_message():
    page, d = page_with(root())
    with pytest.raises(AssertionError) as e:
        expect(page.get_by_text("Welcome")).to_be_visible(timeout=1)
    msg = str(e.value)
    assert "expect(get_by_text('Welcome')).to_be_visible() failed after 1s" in msg
    assert "expected: visible" in msg and "actual:   not found" in msg
    assert d.clock.t == pytest.approx(1.0)


def test_to_be_hidden():
    page, _ = page_with(root(WELCOME), root(WELCOME), root())
    expect(page.get_by_id("form_title")).to_be_hidden()
    page, _ = page_with(root(node(text="x", visible=False)))
    expect(page.get_by_text("x")).to_be_hidden()
    page, _ = page_with(root(WELCOME))
    with pytest.raises(AssertionError, match="expected: hidden"):
        expect(page.get_by_id("form_title")).to_be_hidden(timeout=0.4)


def test_to_have_text_retries_then_reports_actual():
    loading = node(text="Loading", rid="p:id/form_title")
    page, _ = page_with(root(loading), root(WELCOME))
    expect(page.get_by_id("form_title")).to_have_text("Welcome, demo")
    page, _ = page_with(root(loading))
    with pytest.raises(AssertionError) as e:
        expect(page.get_by_id("form_title")).to_have_text("Welcome, demo", timeout=0.5)
    assert "expected: 'Welcome, demo'" in str(e.value) and "actual:   'Loading'" in str(e.value)


def test_to_contain_text():
    page, _ = page_with(root(WELCOME))
    expect(page.get_by_id("form_title")).to_contain_text("demo")
    with pytest.raises(AssertionError, match="text containing 'nobody'"):
        expect(page.get_by_id("form_title")).to_contain_text("nobody", timeout=0.2)


def test_to_have_count():
    item = node(text="Item", rid="p:id/row")
    page, _ = page_with(root(item), root(item, item))
    expect(page.get_by_id("row")).to_have_count(2)
    with pytest.raises(
        AssertionError, match=r"expected: 3 element\(s\)\n  actual:   2 element\(s\)"
    ):
        expect(page.get_by_id("row")).to_have_count(3, timeout=0.2)


def test_expect_timeout_argument_and_page_default():
    page, _ = page_with(root())
    page.set_default_timeout(2)
    with pytest.raises(AssertionError, match="after 2.0s"):
        expect(page.get_by_text("x")).to_be_visible()
    with pytest.raises(AssertionError, match="after 0.6s"):
        expect(page.get_by_text("x"), timeout=0.6).to_be_visible()


def test_expect_rejects_non_locator():
    with pytest.raises(TypeError):
        expect("Welcome")
