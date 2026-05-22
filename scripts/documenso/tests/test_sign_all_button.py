"""Playwright tests for the BEI sign-all-button patch.

Strategy: instead of spinning up a full Documenso container, we inject the IIFE
from `patch_sign_all_button.py` into a tiny HTML harness that mimics the
signing-widget DOM structure (same class names, same `field-card-container`
markers, same email/full-name input IDs). Playwright then exercises the
button's behaviour end-to-end against the mock DOM.

This tests the *patch script's payload* — the actual JS that gets injected
into the production bundle. If this passes, the patch script is functionally
correct. The remaining risk is purely "does the upstream bundle's DOM still
match our selectors", which the live-container drift probe catches.

USAGE
-----
    pip install playwright pytest pytest-playwright
    playwright install chromium
    pytest scripts/documenso/tests/test_sign_all_button.py -v

The harness builds itself from `sign_all_harness.html` (the DOM mock) + the
PATCH_BLOCK extracted from `patch_sign_all_button.py` (the actual IIFE).
That way the harness is always in sync with the latest patch.
"""
from __future__ import annotations

import pathlib
import re

import pytest
from playwright.sync_api import Page, expect

HERE = pathlib.Path(__file__).parent
PATCH_SCRIPT = HERE.parent / "patch_sign_all_button.py"
HARNESS_TEMPLATE = HERE / "sign_all_harness.html"


def _build_harness() -> str:
    """Read the harness HTML + extract PATCH_BLOCK and inject it."""
    template = HARNESS_TEMPLATE.read_text(encoding="utf-8")
    src = PATCH_SCRIPT.read_text(encoding="utf-8")
    m = re.search(r'PATCH_BLOCK = r"""(.*?)"""', src, flags=re.DOTALL)
    if not m:
        raise RuntimeError("Could not extract PATCH_BLOCK from patch_sign_all_button.py")
    block = m.group(1)
    return template.replace(
        "<!-- PATCH_BLOCK_INSERTION_POINT -->",
        f"<script>\n{block}\n</script>",
    )


@pytest.fixture(scope="session")
def harness_url(tmp_path_factory):
    out = tmp_path_factory.mktemp("bei-sign-all") / "harness.html"
    out.write_text(_build_harness(), encoding="utf-8")
    return f"file:///{str(out).replace(chr(92), '/')}"


@pytest.fixture(autouse=True)
def _navigate(page: Page, harness_url):
    """Auto-navigate every test's page to the harness."""
    page.goto(harness_url)
    page.wait_for_timeout(200)


# -- Visibility / gating --------------------------------------------------

def test_button_appears_for_sam(page: Page):
    """The button must appear when recipient is sam@bebang.ph (harness default) with unsigned fields."""
    # Harness default email is sam@bebang.ph; initial injectButton() runs on script load.
    page.wait_for_selector(".bei-sign-all-btn", timeout=2000)
    expect(page.locator(".bei-sign-all-btn")).to_be_visible()
    expect(page.locator(".bei-sign-all-btn")).to_contain_text("Sign All My Fields")


def test_button_invisible_for_other_users(page: Page):
    """Changing email to a non-target value must remove the existing button."""
    # Ensure the button is initially visible (default email is sam@bebang.ph)
    page.wait_for_selector(".bei-sign-all-btn", timeout=2000)
    # Change email and dispatch input event — the IIFE's email-input listener triggers recheck
    page.evaluate('var i=document.getElementById("email"); i.value="someone-else@bebang.ph"; i.dispatchEvent(new Event("input",{bubbles:true}))')
    page.wait_for_timeout(400)
    expect(page.locator(".bei-sign-all-btn")).to_have_count(0)


def test_button_case_insensitive_email(page: Page):
    """Email comparison must be case-insensitive."""
    page.wait_for_selector(".bei-sign-all-btn", timeout=2000)
    page.evaluate('var i=document.getElementById("email"); i.value="SAM@BEBANG.PH"; i.dispatchEvent(new Event("input",{bubbles:true}))')
    page.wait_for_timeout(400)
    expect(page.locator(".bei-sign-all-btn")).to_be_visible()


# -- Behaviour ------------------------------------------------------------

def _activate(page: Page):
    page.evaluate('document.getElementById("email").value = "sam@bebang.ph"')
    page.evaluate('document.body.setAttribute("data-bei-trigger", String(Date.now()))')
    page.wait_for_selector(".bei-sign-all-btn", timeout=2000)


def test_signature_fields_signed_in_one_click(page: Page):
    """SIGNATURE fields auto-apply on click (no dialog) — sign-all should fill them."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    # Wait for both signature fields to be marked inserted
    page.wait_for_function(
        '() => document.querySelectorAll(\'.field-card-container[data-field-type="SIGNATURE"][data-inserted="true"]\').length === 2',
        timeout=15000,
    )
    inserted = page.evaluate('document.querySelectorAll(\'.field-card-container[data-field-type="SIGNATURE"][data-inserted="true"]\').length')
    assert inserted == 2


def test_name_field_filled_from_full_name(page: Page):
    """NAME field should be filled with the value of #full-name input."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    page.wait_for_function(
        '() => document.querySelector(\'.field-card-container[data-field-type="NAME"][data-inserted="true"]\') !== null',
        timeout=15000,
    )
    custom_text = page.evaluate('document.querySelector(\'.field-card-container[data-field-type="NAME"]\').getAttribute("data-custom-text")')
    assert custom_text == "Sam Karazi"


def test_email_field_filled_from_email_input(page: Page):
    """EMAIL field should be filled with the recipient's email."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    page.wait_for_function(
        '() => document.querySelector(\'.field-card-container[data-field-type="EMAIL"][data-inserted="true"]\') !== null',
        timeout=15000,
    )
    # The IIFE lowercases the email; the test_button_appears_for_sam set it to lowercase already
    custom_text = page.evaluate('document.querySelector(\'.field-card-container[data-field-type="EMAIL"]\').getAttribute("data-custom-text")')
    assert custom_text == "sam@bebang.ph"


def test_date_field_filled_with_today(page: Page):
    """DATE field should be filled with today's date in yyyy-mm-dd format."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    page.wait_for_function(
        '() => document.querySelector(\'.field-card-container[data-field-type="DATE"][data-inserted="true"]\') !== null',
        timeout=15000,
    )
    custom_text = page.evaluate('document.querySelector(\'.field-card-container[data-field-type="DATE"]\').getAttribute("data-custom-text")')
    # yyyy-mm-dd format
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", custom_text), f"Bad date format: {custom_text}"


def test_initials_field_derived_from_name(page: Page):
    """INITIALS field should be filled with initials derived from full name."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    page.wait_for_function(
        '() => document.querySelector(\'.field-card-container[data-field-type="INITIALS"][data-inserted="true"]\') !== null',
        timeout=15000,
    )
    custom_text = page.evaluate('document.querySelector(\'.field-card-container[data-field-type="INITIALS"]\').getAttribute("data-custom-text")')
    assert custom_text == "SK"


def test_text_field_skipped(page: Page):
    """TEXT fields are unsupported — should remain un-inserted."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    page.wait_for_timeout(8000)  # let the iteration complete
    inserted = page.evaluate('document.querySelector(\'.field-card-container[data-field-type="TEXT"]\').getAttribute("data-inserted")')
    assert inserted == "false", "TEXT fields must NOT be auto-signed"


def test_all_supported_fields_signed(page: Page):
    """End-to-end: all 6 supported fields should be inserted; TEXT is skipped."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    page.wait_for_function(
        '() => document.querySelectorAll(\'.field-card-container[data-inserted="true"]\').length === 6',
        timeout=20000,
    )
    inserted = page.evaluate('document.querySelectorAll(\'.field-card-container[data-inserted="true"]\').length')
    assert inserted == 6
    # And the TEXT field remains unsigned
    text_inserted = page.evaluate('document.querySelector(\'.field-card-container[data-field-type="TEXT"]\').getAttribute("data-inserted")')
    assert text_inserted == "false"


def test_button_idempotent_when_nothing_to_sign(page: Page):
    """Clicking the button when all fields are already signed should be a no-op."""
    _activate(page)
    page.locator(".bei-sign-all-btn").click()
    page.wait_for_function(
        '() => document.querySelectorAll(\'.field-card-container[data-inserted="true"]\').length === 6',
        timeout=20000,
    )
    # The button removes itself when no fields are unsigned (because getUnsignedFields returns empty).
    # We don't assert removal here — just confirm clicking again doesn't error.
    btns = page.locator(".bei-sign-all-btn")
    if btns.count() > 0:
        btns.first.click()
        page.wait_for_timeout(1500)
    # No exceptions, no extra inserted fields
    inserted = page.evaluate('document.querySelectorAll(\'.field-card-container[data-inserted="true"]\').length')
    assert inserted == 6
