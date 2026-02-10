"""
Click-Path Synthetic Monitor — Tests ACTUAL user journeys on my.bebang.ph.

Navigates through sidebar → pages → forms the way real users do.
Catches bugs that URL-based tests miss (wrong router.push targets,
broken client-side navigation, missing Link hrefs).

Used by:
  - GitHub Actions synthetic monitoring (every 30 min, business hours)
  - Manual QA: python tests/e2e/click_path_test.py --json

Environment variables:
  STAFF_PASSWORD  — override default test password
  BASE_URL        — override default https://my.bebang.ph
"""

import json
import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Page

BASE_URL = os.environ.get("BASE_URL", "https://my.bebang.ph")
STAFF_EMAIL = "test.staff@bebang.ph"
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "BeiTest2026!")


def login(page: Page, email: str, password: str) -> bool:
    """Login and return True if successful."""
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    time.sleep(6)
    page.wait_for_load_state("networkidle")
    cookies = {c["name"]: c["value"] for c in page.context.cookies()}
    return "bei_auth" in cookies or "sid" in cookies


def check_no_404(page: Page) -> bool:
    """Check page is not showing a 404."""
    content = page.content()[:3000].lower()
    if "this page could not be found" in content:
        return False
    if "<h1>404</h1>" in content:
        return False
    return True


def click_sidebar_item(page: Page, text: str) -> bool:
    """Click a sidebar menu item by visible text."""
    try:
        sidebar_toggle = page.locator(
            '[data-testid="sidebar-toggle"], button:has(svg.lucide-panel-left)'
        ).first
        if sidebar_toggle.is_visible():
            sidebar_toggle.click()
            time.sleep(0.5)

        item = page.locator(f'a:has-text("{text}"), button:has-text("{text}")').first
        if item.is_visible(timeout=3000):
            item.click()
            time.sleep(3)
            page.wait_for_load_state("networkidle")

            try:
                overlay = page.locator('[data-state="open"][data-sidebar="sidebar"]')
                if overlay.is_visible(timeout=1000):
                    page.keyboard.press("Escape")
                    time.sleep(0.5)
            except Exception:
                pass

            return True
    except Exception:
        pass
    return False


def flow_punch(page: Page, sd: str) -> list:
    """Sidebar → Remote Punch → Punch In form."""
    results = []
    page.goto(f"{BASE_URL}/dashboard")
    time.sleep(3)

    clicked = click_sidebar_item(page, "Remote Punch")
    page.screenshot(path=f"{sd}/CP_punch_01_sidebar.png")
    url = page.url
    no404 = check_no_404(page)
    results.append({
        "step": "P1", "action": "Click 'Remote Punch' in sidebar",
        "passed": clicked and no404 and "attendance/punch" in url,
        "url": url, "has_404": not no404,
    })
    if not no404:
        return results

    punch_btn = page.locator('button:has-text("Punch In"), a:has-text("Punch In")').first
    btn_visible = punch_btn.is_visible(timeout=5000) if punch_btn else False
    if btn_visible:
        punch_btn.click(timeout=10000)
        time.sleep(3)
        page.wait_for_load_state("networkidle")

    page.screenshot(path=f"{sd}/CP_punch_02_after_click.png")
    url = page.url
    no404 = check_no_404(page)
    results.append({
        "step": "P2", "action": "Click 'Punch In' button",
        "passed": btn_visible and no404 and "punch" in url,
        "url": url, "has_404": not no404,
    })
    return results


def flow_ob(page: Page, sd: str) -> list:
    """Sidebar → Official Business."""
    results = []
    page.goto(f"{BASE_URL}/dashboard")
    time.sleep(3)

    clicked = click_sidebar_item(page, "Official Business")
    page.screenshot(path=f"{sd}/CP_ob_01_sidebar.png")
    url = page.url
    no404 = check_no_404(page)
    results.append({
        "step": "O1", "action": "Click 'Official Business' in sidebar",
        "passed": clicked and no404, "url": url, "has_404": not no404,
    })
    return results


def flow_leave(page: Page, sd: str) -> list:
    """Sidebar → Leave → Apply button."""
    results = []
    page.goto(f"{BASE_URL}/dashboard")
    time.sleep(3)

    clicked = click_sidebar_item(page, "Leave")
    page.screenshot(path=f"{sd}/CP_leave_01_sidebar.png")
    url = page.url
    no404 = check_no_404(page)
    results.append({
        "step": "L1", "action": "Click 'Leave' in sidebar",
        "passed": clicked and no404 and "hr/leave" in url,
        "url": url, "has_404": not no404,
    })
    return results


def flow_dashboard(page: Page, sd: str) -> list:
    """Verify dashboard loads without errors."""
    results = []
    page.goto(f"{BASE_URL}/dashboard")
    time.sleep(5)
    page.screenshot(path=f"{sd}/CP_dashboard_01.png")
    no404 = check_no_404(page)
    has_content = "dashboard" in page.url
    results.append({
        "step": "D1", "action": "Dashboard loads",
        "passed": no404 and has_content, "url": page.url, "has_404": not no404,
    })
    return results


FLOWS = {
    "dashboard": flow_dashboard,
    "punch": flow_punch,
    "ob": flow_ob,
    "leave": flow_leave,
}


def run_click_paths(flow_name: str = None, output_json: bool = False) -> bool:
    sd = os.environ.get("SCREENSHOTS_DIR", "test-results/click_path")
    os.makedirs(sd, exist_ok=True)

    flows_to_run = {flow_name: FLOWS[flow_name]} if flow_name else FLOWS
    all_results = {}
    total_pass = 0
    total_fail = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            geolocation={"latitude": 14.5547, "longitude": 121.0244},
            permissions=["geolocation"],
        )
        page = context.new_page()

        logged_in = login(page, STAFF_EMAIL, STAFF_PASSWORD)
        if not logged_in:
            print("LOGIN FAILED - cannot run click path tests")
            browser.close()
            if output_json:
                print(json.dumps({"test": "click_path", "error": "login_failed"}, indent=2))
            return False

        print(f"\n{'='*60}")
        print(f"  CLICK-PATH SYNTHETIC MONITOR")
        print(f"  URL: {BASE_URL}")
        print(f"  User: {STAFF_EMAIL}")
        print(f"  Flows: {', '.join(flows_to_run.keys())}")
        print(f"  Time: {datetime.now().isoformat()}")
        print(f"{'='*60}\n")

        for name, flow_fn in flows_to_run.items():
            results = flow_fn(page, sd)
            all_results[name] = results

            for r in results:
                icon = "PASS" if r["passed"] else "FAIL"
                print(f"  {icon}  [{r['step']}] {r['action']}")
                if r.get("has_404"):
                    print(f"         ^^^ 404 DETECTED at {r.get('url', '?')}")
                if r["passed"]:
                    total_pass += 1
                else:
                    total_fail += 1
            print()

        browser.close()

    total = total_pass + total_fail
    rate = (total_pass / total * 100) if total else 0

    print(f"{'='*60}")
    print(f"  RESULTS: {total_pass}/{total} ({rate:.0f}%)")
    if total_fail > 0:
        print(f"  {total_fail} FAILURES - users will hit broken navigation!")
    print(f"{'='*60}\n")

    if output_json:
        output = {
            "test": "click_path",
            "run_date": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total": total,
            "passed": total_pass,
            "failed": total_fail,
            "pass_rate": rate,
            "flows": all_results,
        }
        path = os.path.join(sd, f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"  JSON: {path}\n")

    return total_fail == 0


if __name__ == "__main__":
    flow = None
    output_json = False

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--json":
            output_json = True
        elif arg == "--flow" and i + 1 < len(args):
            flow = args[i + 1]

    success = run_click_paths(flow_name=flow, output_json=output_json)
    sys.exit(0 if success else 1)
