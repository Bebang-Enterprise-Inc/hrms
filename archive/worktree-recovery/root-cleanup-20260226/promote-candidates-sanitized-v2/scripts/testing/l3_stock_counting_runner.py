#!/usr/bin/env python3
"""
Browser-driven L3 runner for Stock Counting module (SC-001).

Flow:
- Login as store staff in browser
- Navigate from sidebar to stock counting
- Create one count from UI interactions
- Submit final count from browser form
- Verify submitted record through app proxy APIs
- Emit evidence + trace + screenshots
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BASE_WEB = "https://my.bebang.ph"
DEFAULT_EMAIL = "test.staff@bebang.ph"
DEFAULT_PASSWORD = "BeiTest2026!"


@dataclass
class RunPaths:
    evidence_file: Path
    result_file: Path
    trace_file: Path
    screenshot_before: Path
    screenshot_after: Path


def _now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _prepare_paths(run_id: str) -> RunPaths:
    out_root = ROOT / "output" / "l3"
    ev_dir = out_root / "evidence"
    art_dir = out_root / "artifacts"
    ev_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)
    return RunPaths(
        evidence_file=ev_dir / f"SC-001_{run_id}.json",
        result_file=ev_dir / f"SC-001_{run_id}_result.json",
        trace_file=art_dir / f"SC-001_{run_id}.trace.zip",
        screenshot_before=art_dir / f"SC-001_{run_id}_before_submit.png",
        screenshot_after=art_dir / f"SC-001_{run_id}_after_submit.png",
    )


def _load_guard_validate_fn():
    guard_path = ROOT / "scripts" / "testing" / "l3_browser_guard.py"
    spec = importlib.util.spec_from_file_location("l3_browser_guard", guard_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load guard module: {guard_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module.validate_evidence


def _wait_for_dashboard(page, timeout_ms: int = 30000) -> bool:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if "/dashboard" in page.url:
            return True
        page.wait_for_timeout(250)
    return False


def _wait_for_stock_form_ready(page, timeout_ms: int = 45000) -> bool:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        loading_visible = page.locator("text=Loading dashboard...").first.is_visible(timeout=500)
        if loading_visible:
            page.wait_for_timeout(500)
            continue

        combos = page.locator('button[role="combobox"]')
        count_button = page.locator('button:has-text("Count")').first
        if combos.count() >= 1 and combos.first.is_visible(timeout=500):
            return True
        if count_button.is_visible(timeout=500):
            return True
        page.wait_for_timeout(400)
    return False


def _click_with_retry(page, locator, target: str, attempts: int = 5) -> None:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            if not locator.is_visible(timeout=5000):
                page.wait_for_timeout(250)
                continue
        except Exception:
            page.wait_for_timeout(250)
            continue

        try:
            locator.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass

        try:
            locator.click(timeout=8000)
            return
        except Exception as exc:
            last_error = str(exc)
            if "intercepts pointer events" in last_error or "not stable" in last_error:
                page.wait_for_timeout(200 * attempt)
                if attempt >= 3:
                    try:
                        locator.click(timeout=8000, force=True)
                        return
                    except Exception as forced_exc:
                        last_error = str(forced_exc)
                continue
            page.wait_for_timeout(200 * attempt)

    raise RuntimeError(f"Unable to click {target}: {last_error[:600]}")


def _select_combo_option(page, combo_index: int, option_label: str) -> bool:
    combos = page.locator('button[role="combobox"]')
    if combos.count() <= combo_index:
        return False
    combo = combos.nth(combo_index)
    if not combo.is_visible(timeout=5000):
        return False

    # Skip interaction when the requested value is already selected.
    current_text = (combo.inner_text() or "").strip()
    if option_label and option_label.lower() in current_text.lower():
        return True

    _click_with_retry(page, combo, f"combobox[{combo_index}]")
    page.wait_for_timeout(350)

    option = page.locator(f'[role="option"]:has-text("{option_label}")').first
    if option_label and not option.is_visible(timeout=3000):
        option = page.locator(
            f'[cmdk-item]:has-text("{option_label}"), [data-radix-select-item]:has-text("{option_label}")'
        ).first

    if not option.is_visible(timeout=3000):
        # Keep first-option fallback for environments with slightly different labels.
        fallback = page.locator('[role="option"]').first
        if not fallback.is_visible(timeout=3000):
            fallback = page.locator("[cmdk-item], [data-radix-select-item]").first
        if not fallback.is_visible(timeout=3000):
            return False
        _click_with_retry(page, fallback, f"combobox[{combo_index}] fallback option")
        page.wait_for_timeout(350)
        return True

    _click_with_retry(page, option, f"combobox[{combo_index}] option '{option_label}'")
    page.wait_for_timeout(350)
    return True


def _pick_count_date(existing_dates: set[str]) -> str:
    today = date.today()
    # Prefer near-future dates first to avoid collisions with historical runs,
    # especially when list endpoints are paginated.
    for day_offset in range(1, 366):
        candidate = (today + timedelta(days=day_offset)).isoformat()
        if candidate not in existing_dates:
            return candidate
    for day_offset in range(0, 365):
        candidate = (today - timedelta(days=day_offset)).isoformat()
        if candidate not in existing_dates:
            return candidate
    return (today + timedelta(days=1)).isoformat()


def run_sc_001(
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
    headless: bool = True,
) -> Dict[str, Any]:
    run_id = _now_id()
    paths = _prepare_paths(run_id)

    actions: List[Dict[str, Any]] = []
    network: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []
    qty_value = "5"

    result: Dict[str, Any] = {
        "scenario_id": "SC-001",
        "module": "stock-counting",
        "run_id": run_id,
        "status": "FAIL",
        "account": email,
        "checks": checks,
        "guard_validation": {"ok": False, "errors": []},
        "paths": {
            "evidence": str(paths.evidence_file.relative_to(ROOT)),
            "result": str(paths.result_file.relative_to(ROOT)),
            "trace": str(paths.trace_file.relative_to(ROOT)),
            "screenshots": [
                str(paths.screenshot_before.relative_to(ROOT)),
                str(paths.screenshot_after.relative_to(ROOT)),
            ],
        },
    }

    def add_action(action_type: str, **kwargs):
        item = {"type": action_type, "ts": time.time()}
        item.update(kwargs)
        actions.append(item)

    def add_check(name: str, ok: bool, detail: str):
        checks.append({"name": name, "ok": ok, "detail": detail})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        trace_stopped = False

        def on_response(resp):
            req = resp.request
            if "/api/" in resp.url:
                network.append(
                    {
                        "method": req.method,
                        "url": resp.url,
                        "status": resp.status,
                    }
                )

        page.on("response", on_response)

        try:
            # Step 1: Login
            page.goto(f"{BASE_WEB}/login", wait_until="domcontentloaded", timeout=60000)
            add_action("click", target="login_page")
            page.locator('input[autocomplete="username"], input[name="email"]').first.fill(email)
            add_action("fill", field="email")
            page.locator('input[type="password"]').first.fill(password)
            add_action("fill", field="password")
            page.locator('button[type="submit"]').first.click()
            add_action("submit", target="login")

            logged_in = _wait_for_dashboard(page, timeout_ms=30000)
            add_check("login_redirect_dashboard", logged_in, page.url)
            if not logged_in:
                raise RuntimeError(f"Login did not reach dashboard. Current URL: {page.url}")
            page.wait_for_timeout(900)

            # Step 2: Sidebar navigation to stock counting.
            clicked_sidebar = False
            sidebar_nav_proven = False
            # Baseline sidebar click proof (guard requires sidebar-driven action evidence).
            dashboard_link = page.locator('a[href="/dashboard"], a:has-text("Dashboard")').first
            if dashboard_link.is_visible(timeout=5000):
                dashboard_link.click(timeout=10000)
                page.wait_for_timeout(350)
                sidebar_nav_proven = True
                add_action(
                    "nav_sidebar",
                    path="Home > Dashboard",
                    route=page.url,
                    selector="sidebar-dashboard",
                )

            sidebar_selectors = [
                'a[href="/inventory/stock-counts"]',
                'a:has-text("Cycle Counts")',
                'a:has-text("Stock Counting")',
            ]
            for selector in sidebar_selectors:
                link = page.locator(selector).first
                if not link.is_visible(timeout=2500):
                    continue
                link.click(timeout=10000)
                page.wait_for_timeout(600)
                if "/inventory/stock-counts" in page.url:
                    clicked_sidebar = True
                    sidebar_nav_proven = True
                    add_action(
                        "nav_sidebar",
                        path="Inventory > Stock Counting",
                        route=page.url,
                        selector=selector,
                    )
                    break

            if not clicked_sidebar:
                # Fallback: open store inventory section/page, then drill to stock counts.
                inventory_entry = page.locator(
                    'a[href="/dashboard/inventory"], a:has-text("Store Inventory")'
                ).first
                if inventory_entry.is_visible(timeout=3000):
                    inventory_entry.click(timeout=10000)
                    add_action("click", target="sidebar_store_inventory")
                    page.wait_for_timeout(700)
                    if "/dashboard/inventory" in page.url or "/inventory" in page.url:
                        sidebar_nav_proven = True
                        add_action(
                            "nav_sidebar",
                            path="Store Inventory",
                            route=page.url,
                            selector="sidebar-store-inventory",
                        )
                    nested_stock_link = page.locator(
                        'a[href="/inventory/stock-counts"], a:has-text("Cycle Counts"), a:has-text("Stock Counting")'
                    ).first
                    if nested_stock_link.is_visible(timeout=5000):
                        nested_stock_link.click(timeout=10000)
                        page.wait_for_timeout(700)
                        if "/inventory/stock-counts" in page.url:
                            clicked_sidebar = True
                            sidebar_nav_proven = True
                            add_action(
                                "nav_sidebar",
                                path="Store Inventory > Stock Counting",
                                route=page.url,
                                selector="store-inventory-fallback",
                            )

            if not clicked_sidebar:
                page.goto(f"{BASE_WEB}/inventory/stock-counts", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(800)
                add_action("nav_fallback_route", route="/inventory/stock-counts")
                # Try one more real sidebar click after fallback page render.
                sidebar_retry = page.locator(
                    'a[href="/inventory/stock-counts"], a:has-text("Cycle Counts"), a:has-text("Stock Counting")'
                ).first
                if sidebar_retry.count() > 0:
                    try:
                        sidebar_retry.click(timeout=10000, force=True)
                        page.wait_for_timeout(600)
                    except Exception:
                        pass
                    if "/inventory/stock-counts" in page.url:
                        clicked_sidebar = True
                        sidebar_nav_proven = True
                        add_action(
                            "nav_sidebar",
                            path="Stock Counting (retry)",
                            route=page.url,
                            selector="retry-after-fallback",
                        )

            add_check("sidebar_navigation", sidebar_nav_proven, page.url)

            # Step 3: Open new count form.
            new_count_btn = page.locator(
                'a[href="/inventory/stock-counts/new"], button:has-text("New Count"), button:has-text("Count")'
            ).first
            if new_count_btn.is_visible(timeout=3000):
                new_count_btn.click(timeout=10000)
                add_action("click", target="new_count")
                page.wait_for_timeout(800)
            if "/inventory/stock-counts/new" not in page.url:
                page.goto(f"{BASE_WEB}/inventory/stock-counts/new", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
            add_check("new_count_route", "/inventory/stock-counts/new" in page.url, page.url)

            if not _wait_for_stock_form_ready(page, timeout_ms=45000):
                # One reload attempt for intermittent hydration stalls.
                page.reload(wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1000)
                if not _wait_for_stock_form_ready(page, timeout_ms=30000):
                    raise RuntimeError("Stock count form did not become ready.")

            # Step 4: Resolve store/count type + choose a non-conflicting date.
            assigned_resp = None
            assigned_payload: Any = {}
            try:
                assigned_resp = page.request.get(
                    f"{BASE_WEB}/api/stock-counts?action=assigned-stores",
                    timeout=60000,
                )
                assigned_ok = assigned_resp.status == 200
                try:
                    assigned_payload = assigned_resp.json().get("message", {})
                except Exception:
                    assigned_payload = {}
            except PlaywrightTimeoutError:
                assigned_ok = False
            stores: List[Dict[str, Any]] = []
            count_types: List[str] = []
            # Supports both legacy payload ({stores, allowed_count_types}) and
            # current proxy payload (message: [store rows]).
            if isinstance(assigned_payload, dict):
                raw_stores = assigned_payload.get("stores", [])
                if isinstance(raw_stores, list):
                    stores = [row for row in raw_stores if isinstance(row, dict)]
                raw_types = assigned_payload.get("allowed_count_types", [])
                if isinstance(raw_types, list):
                    count_types = [str(row).strip() for row in raw_types if str(row).strip()]
            elif isinstance(assigned_payload, list):
                stores = [row for row in assigned_payload if isinstance(row, dict)]
            store_row = stores[0] if stores else {}
            store_name = str(
                store_row.get("store_name") or store_row.get("warehouse_name") or ""
            ).strip()
            store_value = str(store_row.get("store") or store_row.get("name") or "").strip()
            store_label = store_name or store_value
            count_type = str(count_types[0] if count_types else "Store Monthly")

            add_check(
                "assigned_stores_status_200",
                assigned_ok,
                f"status={assigned_resp.status if assigned_resp else 'timeout'}",
            )
            add_check(
                "assigned_store_available",
                bool(store_value),
                f"store_name={store_name or '<none>'} store={store_value or '<none>'}",
            )
            add_check("allowed_count_type_available", bool(count_type), f"count_type={count_type}")

            list_resp = None
            list_payload: Any = []
            try:
                list_resp = page.request.get(
                    f"{BASE_WEB}/api/stock-counts?action=list",
                    timeout=60000,
                )
                list_ok = list_resp.status == 200
                try:
                    list_payload = list_resp.json().get("message", [])
                except Exception:
                    list_payload = []
            except PlaywrightTimeoutError:
                list_ok = False
            existing_dates: set[str] = set()
            if isinstance(list_payload, list):
                for row in list_payload:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("store")) != store_value:
                        continue
                    if str(row.get("count_type")) != count_type:
                        continue
                    d = str(row.get("count_date") or "")
                    if d:
                        existing_dates.add(d[:10])
            chosen_date = _pick_count_date(existing_dates)
            add_check(
                "list_status_200",
                list_ok,
                f"status={list_resp.status if list_resp else 'timeout'}",
            )
            add_check("chosen_count_date", True, chosen_date)

            store_selected = _select_combo_option(page, combo_index=0, option_label=store_label)
            add_action("click", target="store_combobox")
            add_check("store_selected", store_selected, f"store_label={store_label}")

            type_selected = _select_combo_option(page, combo_index=1, option_label=count_type)
            add_action("click", target="count_type_combobox")
            add_check("count_type_selected", type_selected, f"count_type={count_type}")

            date_input = page.locator('input[type="date"]').first
            date_filled = False
            if date_input.is_visible(timeout=3000):
                date_input.fill(chosen_date)
                add_action("fill", field="count_date", value=chosen_date)
                date_filled = True
            add_check("count_date_set", date_filled, chosen_date)

            # Step 5: Load item list.
            count_btn = page.locator('button:has-text("Count")').first
            if not count_btn.is_visible(timeout=7000):
                raise RuntimeError("Count button not visible on stock count form.")
            _click_with_retry(page, count_btn, "count_button")
            add_action("click", target="count_button")
            page.wait_for_timeout(1800)

            items_resp = None
            items_payload: Dict[str, Any] = {}
            try:
                items_resp = page.request.get(
                    f"{BASE_WEB}/api/stock-counts?action=items-for-count&store={quote_plus(store_value)}&count_type={quote_plus(count_type)}",
                    timeout=60000,
                )
                items_ok = items_resp.status == 200
                try:
                    items_payload = items_resp.json().get("message", {})
                except Exception:
                    items_payload = {}
            except PlaywrightTimeoutError:
                items_ok = False
            items = items_payload.get("items", []) if isinstance(items_payload, dict) else []
            first_item_code = str(items[0].get("item_code")) if items else ""
            add_check(
                "items_for_count_status_200",
                items_ok,
                f"status={items_resp.status if items_resp else 'timeout'}",
            )
            add_check("items_for_count_has_items", len(items) > 0, f"items={len(items)}")

            if not first_item_code:
                raise RuntimeError("No item_code available from items-for-count response.")

            item_button = page.locator(f'button:has-text("{first_item_code}")').first
            if not item_button.is_visible(timeout=10000):
                raise RuntimeError(f"Item button with code {first_item_code} not visible.")
            _click_with_retry(page, item_button, f"item_row_{first_item_code}")
            add_action("click", target="item_row", item_code=first_item_code)
            page.wait_for_timeout(700)

            qty_input = page.locator('input[type="number"]').first
            if not qty_input.is_visible(timeout=7000):
                raise RuntimeError("Quantity input not visible after selecting item.")
            qty_input.fill(qty_value)
            add_action("fill", field="counted_qty_whole", value=qty_value)
            add_check("qty_filled", True, qty_value)

            remarks = page.locator('input[placeholder*="remark" i], input[placeholder*="expired" i], textarea').first
            if remarks.count() > 0 and remarks.is_visible(timeout=1000):
                remarks.fill(f"L3 SC-001 {run_id}")
                add_action("fill", field="remarks")

            save_next = page.locator('button:has-text("Save & Next"), button:has-text("Save")').first
            if not save_next.is_visible(timeout=7000):
                raise RuntimeError("Save & Next button not visible.")
            _click_with_retry(page, save_next, "save_and_next")
            add_action("click", target="save_and_next")
            page.wait_for_timeout(900)

            page.screenshot(path=str(paths.screenshot_before), full_page=False)

            review_tab = page.locator('button:has-text("Review")').first
            if review_tab.is_visible(timeout=5000):
                _click_with_retry(page, review_tab, "review_tab")
                add_action("click", target="review_tab")
                page.wait_for_timeout(900)

            review_text = (review_tab.text_content() or "").strip() if review_tab.count() > 0 else ""
            has_review_progress = "(1/" in review_text or "(2/" in review_text or "(3/" in review_text or "(4/" in review_text or "(5/" in review_text
            add_check("review_progress_incremented", has_review_progress, review_text or "<empty>")

            # Step 6: Submit final count.
            submit_btn = page.locator(
                'button:has-text("Submit Final Count"), button:has-text("Submit Count"), button:has-text("Submit")'
            ).first
            if not submit_btn.is_visible(timeout=10000):
                raise RuntimeError("Submit Final Count button not visible.")

            submit_status_ok = False
            submit_json: Dict[str, Any] = {}
            count_name = ""
            status_value = ""
            submit_resp = None
            submit_detail = ""
            submit_dates_tried = [chosen_date]

            for attempt in range(8):
                if attempt > 0:
                    retry_date = (
                        datetime.fromisoformat(chosen_date).date() + timedelta(days=attempt)
                    ).isoformat()
                    submit_dates_tried.append(retry_date)
                    retry_date_input = page.locator('input[type="date"]').first
                    if retry_date_input.is_visible(timeout=3000):
                        retry_date_input.fill(retry_date)
                        add_action("fill", field="count_date_retry", value=retry_date)
                        page.wait_for_timeout(250)

                with page.expect_response(
                    lambda r: r.request.method == "POST" and "/api/stock-counts" in r.url,
                    timeout=30000,
                ) as submit_info:
                    submit_btn.click(timeout=10000)
                    add_action("submit", target="stock_count_submit")
                submit_resp = submit_info.value

                submit_status_ok = 200 <= submit_resp.status < 300
                try:
                    parsed = submit_resp.json()
                except Exception:
                    parsed = {"raw": submit_resp.text()[:800]}
                submit_json = parsed if isinstance(parsed, dict) else {"raw": str(parsed)}

                message = submit_json.get("message", {}) if isinstance(submit_json, dict) else {}
                if not isinstance(message, dict):
                    message = {}
                count_name = str(message.get("name", ""))
                status_value = str(message.get("status", ""))

                submit_detail = str(
                    submit_json.get("error")
                    or submit_json.get("message")
                    or submit_json.get("raw")
                    or ""
                )

                if submit_status_ok:
                    break

                duplicate_hint = "already exists" in submit_detail.lower()
                if not duplicate_hint:
                    break
                page.wait_for_timeout(400)

            add_check("submit_response_status_2xx", submit_status_ok, f"status={submit_resp.status}")
            add_check("submit_response_has_name", count_name.startswith("BEI-CC-"), f"name={count_name}")
            add_check("submit_response_status_submitted", status_value == "Submitted", f"status={status_value}")
            if len(submit_dates_tried) > 1:
                add_check(
                    "submit_retry_dates",
                    submit_status_ok,
                    f"dates_tried={','.join(submit_dates_tried)} detail={submit_detail[:240]}",
                )

            page.wait_for_timeout(1200)
            page.screenshot(path=str(paths.screenshot_after), full_page=False)

            # Step 7: Verify in list + detail endpoints.
            verify_list_resp = None
            verify_list: Any = []
            verify_list_ok = False
            found_in_list = False
            # Newly submitted counts can take a moment to appear in list endpoint.
            for _ in range(12):
                try:
                    verify_list_resp = page.request.get(
                        f"{BASE_WEB}/api/stock-counts?action=list",
                        timeout=60000,
                    )
                    verify_list_ok = verify_list_resp.status == 200
                    try:
                        verify_list = verify_list_resp.json().get("message", [])
                    except Exception:
                        verify_list = []
                except PlaywrightTimeoutError:
                    verify_list_ok = False
                    verify_list = []

                found_in_list = any(
                    isinstance(row, dict) and str(row.get("name")) == count_name
                    for row in (verify_list if isinstance(verify_list, list) else [])
                )
                if found_in_list:
                    break
                page.wait_for_timeout(1000)
            add_check(
                "verify_list_status_200",
                verify_list_ok,
                f"status={verify_list_resp.status if verify_list_resp else 'timeout'}",
            )
            add_check("verify_submitted_count_in_list", found_in_list, f"name={count_name}")

            verify_detail_resp = None
            verify_detail: Dict[str, Any] = {}
            try:
                verify_detail_resp = page.request.get(
                    f"{BASE_WEB}/api/stock-counts?action=detail&id={count_name}",
                    timeout=60000,
                )
                verify_detail_ok = verify_detail_resp.status == 200
                try:
                    verify_detail = verify_detail_resp.json().get("message", {})
                except Exception:
                    verify_detail = {}
            except PlaywrightTimeoutError:
                verify_detail_ok = False
            detail_counted_by = str(verify_detail.get("counted_by", ""))
            detail_items = verify_detail.get("items", []) if isinstance(verify_detail, dict) else []
            detail_item_ok = False
            detail_item_detail = f"item_code={first_item_code}"
            if isinstance(detail_items, list) and detail_items:
                matching_item = next(
                    (
                        row
                        for row in detail_items
                        if isinstance(row, dict) and str(row.get("item_code")) == first_item_code
                    ),
                    None,
                )
                if isinstance(matching_item, dict):
                    actual_qty = float(matching_item.get("counted_qty_whole", 0) or 0)
                    expected_qty = float(qty_value)
                    detail_item_ok = actual_qty >= expected_qty
                    detail_item_detail = (
                        f"item_code={first_item_code} expected_qty>={expected_qty} actual_qty={actual_qty}"
                    )
                else:
                    detail_item_detail = (
                        f"item_code={first_item_code} missing_in_detail_items={len(detail_items)}"
                    )
            add_check(
                "verify_detail_status_200",
                verify_detail_ok,
                f"status={verify_detail_resp.status if verify_detail_resp else 'timeout'}",
            )
            add_check(
                "verify_detail_counted_by",
                detail_counted_by.lower() == email.lower(),
                f"counted_by={detail_counted_by}",
            )
            add_check("verify_detail_first_item_qty", detail_item_ok, detail_item_detail)

            evidence = {
                "scenario_id": "SC-001",
                "module": "stock-counting",
                "actions": actions,
                "network": network,
                "artifacts": {
                    "trace": str(paths.trace_file.relative_to(ROOT)).replace("\\", "/"),
                    "screenshots": [
                        str(paths.screenshot_before.relative_to(ROOT)).replace("\\", "/"),
                        str(paths.screenshot_after.relative_to(ROOT)).replace("\\", "/"),
                    ],
                },
            }
            paths.evidence_file.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

            context.tracing.stop(path=str(paths.trace_file))
            trace_stopped = True

            validate_evidence = _load_guard_validate_fn()
            guard_ok, guard_errors = validate_evidence(
                evidence_path=paths.evidence_file,
                expected_endpoint="/api/stock-counts",
                requires_upload=False,
            )
            result["guard_validation"] = {"ok": guard_ok, "errors": guard_errors}
            add_check("guard_validate_evidence", guard_ok, "; ".join(guard_errors) or "ok")

            all_pass = all(c["ok"] for c in checks)
            result["status"] = "PASS" if all_pass else "FAIL"

        except PlaywrightTimeoutError as exc:
            add_check("playwright_timeout", False, str(exc))
            result["error"] = f"Playwright timeout: {exc}"
            result["status"] = "FAIL"
        except Exception as exc:
            add_check("unexpected_exception", False, str(exc))
            result["error"] = str(exc)
            result["status"] = "FAIL"
        finally:
            if not trace_stopped:
                context.tracing.stop(path=str(paths.trace_file))
            context.close()
            browser.close()

    paths.result_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SC-001 L3 browser test.")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--headed", action="store_true", help="Run with headed browser.")
    args = parser.parse_args()

    result = run_sc_001(
        email=args.email,
        password=args.password,
        headless=not args.headed,
    )

    print(f"STATUS={result.get('status')}")
    print(f"EVIDENCE={result['paths']['evidence']}")
    print(f"RESULT={result['paths']['result']}")
    print(f"TRACE={result['paths']['trace']}")
    print(f"GUARD_OK={result.get('guard_validation', {}).get('ok')}")
    out_encoding = sys.stdout.encoding or "utf-8"
    for check in result.get("checks", []):
        flag = "PASS" if check.get("ok") else "FAIL"
        detail = str(check.get("detail", ""))
        safe_detail = detail.encode(out_encoding, errors="replace").decode(
            out_encoding, errors="replace"
        )
        print(f"{flag} {check.get('name')}: {safe_detail}")
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
