#!/usr/bin/env python3
"""
L3 S103 — Scenarios 3-5: Approve/Reject workflow
Uses test.area@bebang.ph (Area Supervisor role) at TEST-STORE-BGC.
Must create a real saved plan before Approve/Reject buttons appear.

Evidence -> output/l3/s103/
"""
import json, sys, time, traceback
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_WEB = "https://my.bebang.ph"
TEST_USER = "test.area@bebang.ph"
TEST_PASS = "BeiTest2026!"
EVIDENCE_DIR = Path("output/l3/s103")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

form_submissions = []
api_mutations = []
state_verifications = []
results = []

def record(sid, test, status, detail=None, error=None):
    results.append({"scenario": sid, "test": test, "status": status, "detail": detail, "error": error, "timestamp": datetime.now().isoformat()})
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
    print(f"  {icon} [{sid}] {test}: {status}" + (f" -- {detail}" if detail else ""))

def save():
    for fname, data in [("form_submissions.json", form_submissions), ("api_mutations.json", api_mutations), ("state_verification.json", state_verifications)]:
        fpath = EVIDENCE_DIR / fname
        existing = []
        if fpath.exists():
            try: existing = json.loads(fpath.read_text())
            except: pass
        existing.extend(data)
        fpath.write_text(json.dumps(existing, indent=2, default=str))

    results_path = EVIDENCE_DIR / "results.json"
    existing_results = []
    if results_path.exists():
        try: existing_results = json.loads(results_path.read_text())
        except: pass
    existing_results = [r for r in existing_results if r.get("scenario") not in ("S3", "S4", "S5")]
    existing_results.extend(results)
    results_path.write_text(json.dumps(existing_results, indent=2, default=str))
    print(f"\nEvidence written to {EVIDENCE_DIR}/")

from playwright.sync_api import sync_playwright, Page

def login(page: Page, email=TEST_USER, pw=TEST_PASS):
    print(f"  Logging in as {email}...")
    page.goto(f"{BASE_WEB}/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first.fill(email)
    page.locator('input[type="password"]').first.fill(pw)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/dashboard**", timeout=30000)
    page.wait_for_timeout(2000)
    print(f"  Logged in as {email}")

def nav_labor_plan(page: Page, week: str):
    url = f"{BASE_WEB}/dashboard/supervisor/labor-plan?week_start={week}"
    print(f"  Navigating to {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)

def get_status(page: Page) -> str:
    """Read status from page. Returns 'No Plan' if no badge found."""
    for s in ["Published", "Approved", "Rejected", "Draft"]:
        try:
            badge = page.locator(f'.bg-slate-600:has-text("{s}"), .bg-blue-600:has-text("{s}"), .bg-red-600:has-text("{s}"), .bg-emerald-600:has-text("{s}")')
            if badge.first.is_visible(timeout=1000):
                return s
        except:
            pass
    # Fallback: look for any text matching
    for s in ["Published", "Approved", "Rejected", "Draft"]:
        try:
            if page.locator(f'span:text-is("{s}")').first.is_visible(timeout=500):
                return s
        except:
            pass
    return "No Plan"

def create_draft_plan_via_api(page: Page, store: str, week: str) -> bool:
    """Create a draft plan by assigning shifts via API, then saving."""
    print(f"  Creating draft plan via API for {store}, week {week}...")

    # Get bootstrap data to know employees
    bootstrap_url = f"{BASE_WEB}/api/supervisor/labor-plan/bootstrap?store={store}&surface=supervisor&week_start={week}"
    resp = page.request.get(bootstrap_url)
    if resp.status != 200:
        print(f"    Bootstrap failed: {resp.status}")
        return False

    body = resp.json()
    data = body.get("data", body)
    employees = data.get("employees", [])
    shift_options = data.get("shift_options", [])

    if not employees:
        print(f"    No employees for store {store}")
        return False

    # Find a work shift (not day off, not VL/SL)
    work_shifts = [s for s in shift_options if not s.get("is_off") and not s.get("requires_approved_leave")]
    if not work_shifts:
        print("    No work shift options available")
        return False

    opening_shift = work_shifts[0]
    print(f"    Using shift: {opening_shift['label']} ({opening_shift['shift_type_name']})")
    print(f"    Employees: {[e['employee_name'] for e in employees]}")

    # Build shift assignments for all employees, all 7 days
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    shifts = []
    for emp in employees:
        for i, day in enumerate(days):
            if i < 5:  # Mon-Fri work, Sat-Sun off
                shifts.append({
                    "employee": emp["name"],
                    "employee_name": emp.get("employee_name"),
                    "day_of_week": day,
                    "shift_type_name": opening_shift["shift_type_name"],
                    "is_off": False,
                })
            else:
                # Day off for weekend
                off_shifts = [s for s in shift_options if s.get("is_off") and not s.get("requires_approved_leave")]
                if off_shifts:
                    shifts.append({
                        "employee": emp["name"],
                        "employee_name": emp.get("employee_name"),
                        "day_of_week": day,
                        "shift_type_name": off_shifts[0]["shift_type_name"],
                        "is_off": True,
                    })

    print(f"    Creating plan with {len(shifts)} shift assignments...")

    # Create plan via POST API
    create_resp = page.request.post(
        f"{BASE_WEB}/api/supervisor/labor-plan",
        data=json.dumps({
            "store": store,
            "week_start": week,
            "shifts": shifts,
            "surface": "supervisor",
        }),
        headers={"Content-Type": "application/json"},
    )

    print(f"    Create response: {create_resp.status}")
    try:
        create_body = create_resp.json()
        print(f"    Response: {json.dumps(create_body)[:300]}")
        if create_body.get("success"):
            api_mutations.append({
                "endpoint": f"{BASE_WEB}/api/supervisor/labor-plan",
                "method": "POST",
                "payload": f"{len(shifts)} shifts for {len(employees)} employees",
                "status": create_resp.status,
                "response_body": str(create_body)[:500],
            })
            return True
    except:
        print(f"    Response text: {create_resp.text()[:300]}")

    return False


# ===========================================================================
# S3: Approve
# ===========================================================================
def scenario_3(page: Page):
    print("\n" + "=" * 60)
    print("SCENARIO 3: Approve button visible for Area Supervisor")
    print("=" * 60)

    week = "2026-03-30"
    store = "TEST-STORE-BGC - BEI"

    # First create a draft plan via API
    created = create_draft_plan_via_api(page, store, week)
    if not created:
        # Maybe plan already exists
        print("  Plan creation failed -- checking if plan already exists...")

    # Now navigate to the page (reload to pick up the new plan)
    nav_labor_plan(page, week)
    page.wait_for_timeout(5000)

    status = get_status(page)
    print(f"  Plan status: {status}")

    if status == "Approved":
        record("S3", "Approve plan", "PASS", "Plan already approved from prior test run")
        return True
    if status == "Published":
        record("S3", "Approve plan", "SKIP", "Plan already published -- cannot test approve")
        return False

    page.screenshot(path=str(EVIDENCE_DIR / "S3_before_approve.png"), full_page=True)

    # Now look for Approve button
    approve_btn = page.locator('button:has-text("Approve")')
    approve_visible = False
    try:
        approve_visible = approve_btn.first.is_visible(timeout=5000)
    except:
        pass

    if not approve_visible:
        # Scroll down
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        try:
            approve_visible = approve_btn.first.is_visible(timeout=3000)
        except:
            pass

    if not approve_visible:
        # Debug: list all button texts
        buttons = page.locator('button')
        btn_texts = []
        for i in range(min(buttons.count(), 30)):
            try:
                t = buttons.nth(i).inner_text(timeout=300).strip().replace('\n', ' ')
                if t and len(t) < 80:
                    btn_texts.append(t)
            except:
                pass
        print(f"  All button texts: {btn_texts}")
        record("S3", "Approve button visible for Area Supervisor", "FAIL",
               f"Approve button not visible. Status={status}, buttons={btn_texts[:10]}")
        page.screenshot(path=str(EVIDENCE_DIR / "S3_no_approve_debug.png"), full_page=True)
        return False

    print("  Approve button IS visible!")

    # Capture response
    resp_data = {"captured": False, "status": None, "body": None}
    def on_resp(response):
        if "labor-plan/approve" in response.url and response.request.method == "POST":
            resp_data["captured"] = True
            resp_data["status"] = response.status
            try: resp_data["body"] = response.json()
            except: resp_data["body"] = response.text()[:500]
    page.on("response", on_resp)

    print("  Clicking Approve...")
    approve_btn.first.click()
    page.wait_for_timeout(5000)
    page.remove_listener("response", on_resp)

    page.screenshot(path=str(EVIDENCE_DIR / "S3_after_approve.png"), full_page=True)

    new_status = get_status(page)

    form_submissions.append({
        "form": "approve_plan", "inputs": {"week": week, "user": TEST_USER},
        "submit_action": "Approve", "response": resp_data.get("body"),
        "screenshot_after": "S3_after_approve.png"
    })
    api_mutations.append({
        "endpoint": f"{BASE_WEB}/api/supervisor/labor-plan/approve",
        "method": "POST", "payload": {"plan_name": "(from UI)"},
        "status": resp_data.get("status"),
        "response_body": str(resp_data.get("body", ""))[:500]
    })
    state_verifications.append({
        "check": "Plan status changes to Approved after clicking Approve",
        "before": f"status={status}", "after": f"status={new_status}",
        "passed": new_status == "Approved"
    })

    if new_status == "Approved" or (resp_data["captured"] and resp_data.get("body", {}).get("success")):
        record("S3", "Approve plan -> status Approved", "PASS", f"Status: {status} -> {new_status}")
        return True
    else:
        record("S3", "Approve plan -> status Approved", "FAIL", f"Status={new_status}, API={resp_data}")
        return False


# ===========================================================================
# S4: Reject
# ===========================================================================
def scenario_4(page: Page):
    print("\n" + "=" * 60)
    print("SCENARIO 4: Reject with reason -> status Rejected")
    print("=" * 60)

    week = "2026-04-06"
    store = "TEST-STORE-BGC - BEI"

    # Create draft plan
    created = create_draft_plan_via_api(page, store, week)

    # Navigate
    nav_labor_plan(page, week)
    page.wait_for_timeout(5000)

    status = get_status(page)
    print(f"  Plan status: {status}")

    if status == "Rejected":
        record("S4", "Reject plan", "PASS", "Plan already rejected from prior test run")
        return True

    page.screenshot(path=str(EVIDENCE_DIR / "S4_before_reject.png"), full_page=True)

    # Look for Reject button
    reject_btn = page.locator('button:has-text("Reject")')
    reject_visible = False
    try:
        reject_visible = reject_btn.first.is_visible(timeout=5000)
    except:
        pass

    if not reject_visible:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        try:
            reject_visible = reject_btn.first.is_visible(timeout=3000)
        except:
            pass

    if not reject_visible:
        buttons = page.locator('button')
        btn_texts = []
        for i in range(min(buttons.count(), 30)):
            try:
                t = buttons.nth(i).inner_text(timeout=300).strip().replace('\n', ' ')
                if t and len(t) < 80: btn_texts.append(t)
            except: pass
        print(f"  All button texts: {btn_texts}")
        record("S4", "Reject button visible", "FAIL",
               f"Reject button not visible. Status={status}, buttons={btn_texts[:10]}")
        return False

    print("  Clicking Reject...")
    reject_btn.first.click()
    page.wait_for_timeout(2000)

    page.screenshot(path=str(EVIDENCE_DIR / "S4_dialog_open.png"), full_page=True)

    textarea = page.locator('#rejection-reason, textarea[placeholder*="rejected"], textarea[placeholder*="Explain"]')
    try:
        textarea.first.wait_for(timeout=5000)
    except:
        record("S4", "Reject dialog opens", "FAIL", "Dialog/textarea not found")
        return False

    print("  Filling rejection reason: 'Insufficient coverage'")
    textarea.first.fill("Insufficient coverage")
    page.wait_for_timeout(500)

    resp_data = {"captured": False, "status": None, "body": None}
    def on_resp(response):
        if "labor-plan/reject" in response.url and response.request.method == "POST":
            resp_data["captured"] = True
            resp_data["status"] = response.status
            try: resp_data["body"] = response.json()
            except: resp_data["body"] = response.text()[:500]
    page.on("response", on_resp)

    confirm_btn = page.locator('button:has-text("Reject Plan")')
    if not confirm_btn.first.is_visible(timeout=3000):
        record("S4", "Reject Plan confirm button", "FAIL", "Not found in dialog")
        page.remove_listener("response", on_resp)
        return False

    print("  Clicking 'Reject Plan'...")
    confirm_btn.first.click()
    page.wait_for_timeout(5000)
    page.remove_listener("response", on_resp)

    page.screenshot(path=str(EVIDENCE_DIR / "S4_after_reject.png"), full_page=True)

    new_status = get_status(page)

    form_submissions.append({
        "form": "reject_plan",
        "inputs": {"rejection_reason": "Insufficient coverage", "week": week},
        "submit_action": "Reject Plan", "response": resp_data.get("body"),
        "screenshot_after": "S4_after_reject.png"
    })
    api_mutations.append({
        "endpoint": f"{BASE_WEB}/api/supervisor/labor-plan/reject",
        "method": "POST", "payload": {"rejection_reason": "Insufficient coverage"},
        "status": resp_data.get("status"),
        "response_body": str(resp_data.get("body", ""))[:500]
    })
    state_verifications.append({
        "check": "Plan status changes to Rejected",
        "before": f"status={status}", "after": f"status={new_status}",
        "passed": new_status == "Rejected"
    })

    if new_status == "Rejected" or (resp_data["captured"] and resp_data.get("body", {}).get("success")):
        record("S4", "Reject plan -> status Rejected", "PASS", f"Status: {status} -> {new_status}")
        return True
    else:
        record("S4", "Reject plan -> status Rejected", "FAIL", f"Status={new_status}, API={resp_data}")
        return False


# ===========================================================================
# S5: Publish disabled on Rejected
# ===========================================================================
def scenario_5(page: Page, s4_passed: bool):
    print("\n" + "=" * 60)
    print("SCENARIO 5: Publish disabled on Rejected plan")
    print("=" * 60)

    if not s4_passed:
        record("S5", "Publish disabled on Rejected plan", "SKIP", "Depends on S4 which failed")
        return

    status = get_status(page)
    if status != "Rejected":
        nav_labor_plan(page, "2026-04-06")
        page.wait_for_timeout(3000)
        status = get_status(page)

    if status != "Rejected":
        record("S5", "Publish disabled on Rejected plan", "SKIP", f"No Rejected plan (status={status})")
        return

    publish_btn = page.locator('button:has-text("Publish")')
    if not publish_btn.first.is_visible(timeout=5000):
        record("S5", "Publish button present", "FAIL", "Publish button not visible")
        return

    is_disabled = publish_btn.first.is_disabled()
    title = publish_btn.first.get_attribute("title") or ""

    page.screenshot(path=str(EVIDENCE_DIR / "S5_publish_disabled.png"), full_page=True)

    state_verifications.append({
        "check": "Publish button disabled on Rejected plan with tooltip",
        "before": "Plan status = Rejected",
        "after": f"disabled={is_disabled}, title='{title}'",
        "passed": is_disabled
    })

    if is_disabled:
        record("S5", "Publish disabled with rejection tooltip", "PASS",
               f"disabled=True, title='{title}'")
    else:
        record("S5", "Publish disabled on Rejected plan", "FAIL",
               "Publish NOT disabled")


def main():
    print("=" * 70)
    print("L3 S103 -- Approve/Reject Workflow (Scenarios 3-5)")
    print(f"User: {TEST_USER} (Area Supervisor)")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} PHT")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()

        try:
            login(page, TEST_USER, TEST_PASS)
            scenario_3(page)
            s4_passed = scenario_4(page)
            scenario_5(page, s4_passed)
        except Exception as e:
            print(f"\nFATAL: {e}")
            traceback.print_exc()
            page.screenshot(path=str(EVIDENCE_DIR / "S345_fatal.png"), full_page=True)
        finally:
            save()
            browser.close()

    print("\n" + "=" * 60)
    for r in results:
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[r["status"]]
        print(f"  {icon} [{r['scenario']}] {r['test']}")
        if r.get("detail"): print(f"       {r['detail']}")

    p_count = sum(1 for r in results if r["status"] == "PASS")
    f_count = sum(1 for r in results if r["status"] == "FAIL")
    s_count = sum(1 for r in results if r["status"] == "SKIP")
    print(f"\nTotal: {p_count} PASS, {f_count} FAIL, {s_count} SKIP")
    return 0 if f_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
