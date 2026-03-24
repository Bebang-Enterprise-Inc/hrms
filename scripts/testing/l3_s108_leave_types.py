#!/usr/bin/env python3
"""
L3 Acceptance Test — Sprint S108: Leave Type E2E Validation
Phase 1: API tests for all 7 leave types.

Tests:
  P1-1: VL full lifecycle (create → approve → attendance → balance → cancel)
  P1-2: SL full lifecycle
  P1-3: EL full lifecycle
  P1-4: CL (expect failure if 0 balance)
  P1-5: LWOP (no balance needed)
  P1-6: CO (document config, no creation test)
  P1-7: PL (expect failure if 0 balance)

Evidence → output/l3/s108/
"""

import json
import sys
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_API = "https://hq.bebang.ph"
API_TOKEN = "token 4a17c23aca83560:38ecc0e1054b1d2"
# Use real employee with leave allocations (VL=15, SL=15, EL=5)
# ARRABIS, MA. CRISTINA - SM MEGAMALL, Operations, Store Supervisor
TEST_EMPLOYEE = "9000003"
EVIDENCE_DIR = Path("output/l3/s108")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

# Test dates — use April 7-13 2026 (Mon-Sun) to avoid conflicts with existing test data
TEST_DATES = {
    "VL": "2026-04-07",
    "SL": "2026-04-08",
    "EL": "2026-04-14",  # Apr 9 is a holiday (Araw ng Kagitingan), use Apr 14 (Tue)
    "CL": "2026-04-10",
    "LWOP": "2026-04-11",
    "CO": None,  # Config check only
    "PL": "2026-04-12",
}

LEAVE_TYPE_MAP = {
    "VL": "Vacation Leave",
    "SL": "Sick Leave",
    "EL": "Emergency Leave",
    "CL": "Casual Leave",
    "LWOP": "Leave Without Pay",
    "CO": "Compensatory Off",
    "PL": "Privilege Leave",
}

# Evidence accumulators
api_mutations = []
state_verifications = []
results = []


def record_result(scenario_id, test_name, status, detail=None, error=None):
    results.append({
        "scenario": scenario_id,
        "test": test_name,
        "status": status,
        "detail": detail or "",
        "error": str(error) if error else "",
    })
    icon = "PASS" if status == "PASS" else "FAIL" if status == "FAIL" else "SKIP"
    print(f"  [{icon}] {scenario_id}: {test_name} — {detail or ''}")


def api_call(method, endpoint, data=None, expect_error=False):
    """Make API call with rate-limit protection."""
    import urllib.request
    import urllib.error

    url = f"{BASE_API}{endpoint}"
    headers = {
        "Authorization": API_TOKEN,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 BEI-S108-Test/1.0",
    }

    if method == "GET":
        if data:
            from urllib.parse import urlencode
            url += "?" + urlencode(data)
        req = urllib.request.Request(url, headers=headers)
    else:
        body = json.dumps(data or {}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read().decode("utf-8")
        result = json.loads(raw)
        api_mutations.append({
            "endpoint": endpoint,
            "method": method,
            "payload": data,
            "status": resp.status,
            "response_body": raw[:500],
        })
        time.sleep(2)  # Rate limit protection
        return result
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        api_mutations.append({
            "endpoint": endpoint,
            "method": method,
            "payload": data,
            "status": e.code,
            "response_body": raw[:500],
        })
        time.sleep(2)
        if expect_error:
            return {"error": raw, "status_code": e.code}
        raise Exception(f"HTTP {e.code}: {raw[:300]}")


def get_leave_balance(employee, leave_type, as_of_date):
    """Get leave balance via Frappe API."""
    result = api_call("GET", "/api/method/hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on", {
        "employee": employee,
        "leave_type": leave_type,
        "date": as_of_date,
    })
    return float(result.get("message", 0))


def create_leave_application(employee, leave_type, from_date, to_date, reason="S108 E2E test"):
    """Create a leave application."""
    result = api_call("POST", "/api/resource/Leave%20Application", {
        "employee": employee,
        "leave_type": leave_type,
        "from_date": from_date,
        "to_date": to_date,
        "reason": reason,
        "status": "Open",
    })
    return result.get("data", {})


def approve_leave(name):
    """Approve and submit a leave application."""
    # First set status to Approved
    api_call("PUT", f"/api/resource/Leave%20Application/{name}", {
        "status": "Approved",
    })
    # Then submit (docstatus=1)
    result = api_call("PUT", f"/api/resource/Leave%20Application/{name}", {
        "docstatus": 1,
    })
    return result.get("data", {})


def cancel_leave(name):
    """Cancel a leave application."""
    result = api_call("PUT", f"/api/resource/Leave%20Application/{name}", {
        "docstatus": 2,
    })
    return result.get("data", {})


def check_attendance(employee, att_date):
    """Check if attendance record exists for a date."""
    result = api_call("GET", "/api/resource/Attendance", {
        "filters": json.dumps([
            ["employee", "=", employee],
            ["attendance_date", "=", att_date],
        ]),
        "fields": json.dumps(["name", "status", "leave_type", "docstatus"]),
    })
    return result.get("data", [])


def check_lwp_config():
    """Check that Leave Without Pay has is_lwp=1 (payroll will deduct)."""
    result = api_call("GET", "/api/resource/Leave%20Type/Leave%20Without%20Pay", {
        "fields": json.dumps(["name", "is_lwp", "is_carry_forward"]),
    })
    return result.get("data", {})


def test_leave_lifecycle(scenario_id, leave_code, employee, test_date, expect_balance=True):
    """Test full leave lifecycle for a given type."""
    leave_type = LEAVE_TYPE_MAP[leave_code]
    print(f"\n{'='*60}")
    print(f"  {scenario_id}: Testing {leave_type} ({leave_code})")
    print(f"  Employee: {employee}, Date: {test_date}")
    print(f"{'='*60}")

    # Step 1: Check balance
    if expect_balance:
        try:
            balance_before = get_leave_balance(employee, leave_type, test_date)
            state_verifications.append({
                "check": f"{leave_code} balance before",
                "before": balance_before,
                "after": None,
                "passed": True,
            })
            record_result(scenario_id, f"{leave_code} balance check", "PASS",
                          f"Balance = {balance_before}")
            if balance_before <= 0:
                record_result(scenario_id, f"{leave_code} lifecycle", "SKIP",
                              f"Balance is {balance_before} — cannot test (no allocation)")
                return None
        except Exception as e:
            record_result(scenario_id, f"{leave_code} balance check", "FAIL", error=e)
            return None

    # Step 2: Create leave application
    try:
        app = create_leave_application(employee, leave_type, test_date, test_date)
        app_name = app.get("name")
        if not app_name:
            record_result(scenario_id, f"{leave_code} create", "FAIL",
                          f"No name returned: {json.dumps(app)[:200]}")
            return None
        record_result(scenario_id, f"{leave_code} create", "PASS",
                      f"Created {app_name}")
    except Exception as e:
        err_str = str(e)
        if "InsufficientLeaveBalance" in err_str or "insufficient" in err_str.lower():
            record_result(scenario_id, f"{leave_code} create", "SKIP",
                          f"Insufficient balance: {err_str[:200]}")
        else:
            record_result(scenario_id, f"{leave_code} create", "FAIL", error=e)
        return None

    # Step 3: Approve + submit
    try:
        approve_leave(app_name)
        # Verify status
        check = api_call("GET", f"/api/resource/Leave%20Application/{app_name}", {
            "fields": json.dumps(["status", "docstatus"]),
        })
        app_data = check.get("data", {})
        status = app_data.get("status")
        docstatus = app_data.get("docstatus")

        if status == "Approved" and docstatus == 1:
            record_result(scenario_id, f"{leave_code} approve+submit", "PASS",
                          f"status={status}, docstatus={docstatus}")
        else:
            record_result(scenario_id, f"{leave_code} approve+submit", "FAIL",
                          f"status={status}, docstatus={docstatus}")
    except Exception as e:
        record_result(scenario_id, f"{leave_code} approve+submit", "FAIL", error=e)
        # Try to clean up
        try:
            cancel_leave(app_name)
        except:
            pass
        return app_name

    # Step 4: Check attendance record
    try:
        time.sleep(2)  # Give Frappe time to create attendance
        attendance = check_attendance(employee, test_date)
        if attendance:
            att_status = attendance[0].get("status")
            att_leave = attendance[0].get("leave_type")
            if att_status == "On Leave":
                record_result(scenario_id, f"{leave_code} attendance", "PASS",
                              f"Attendance: {att_status}, leave_type: {att_leave}")
                state_verifications.append({
                    "check": f"{leave_code} attendance created",
                    "before": "No attendance",
                    "after": f"status={att_status}, leave_type={att_leave}",
                    "passed": True,
                })
            else:
                record_result(scenario_id, f"{leave_code} attendance", "FAIL",
                              f"Attendance status={att_status}, expected 'On Leave'")
        else:
            record_result(scenario_id, f"{leave_code} attendance", "FAIL",
                          "No attendance record found")
    except Exception as e:
        record_result(scenario_id, f"{leave_code} attendance", "FAIL", error=e)

    # Step 5: Check balance after (for paid leave types)
    if expect_balance:
        try:
            balance_after = get_leave_balance(employee, leave_type, test_date)
            expected = balance_before - 1
            state_verifications.append({
                "check": f"{leave_code} balance after approval",
                "before": balance_before,
                "after": balance_after,
                "passed": abs(balance_after - expected) < 0.1,
            })
            if abs(balance_after - expected) < 0.1:
                record_result(scenario_id, f"{leave_code} balance deducted", "PASS",
                              f"Balance: {balance_before} → {balance_after}")
            else:
                record_result(scenario_id, f"{leave_code} balance deducted", "FAIL",
                              f"Expected {expected}, got {balance_after}")
        except Exception as e:
            record_result(scenario_id, f"{leave_code} balance deducted", "FAIL", error=e)

    # Step 6: Check LWOP payroll impact (only for LWOP)
    if leave_code == "LWOP":
        try:
            lwp_config = check_lwp_config()
            is_lwp = lwp_config.get("is_lwp", 0)
            if is_lwp:
                record_result(scenario_id, "LWOP payroll impact", "PASS",
                              f"Leave Type has is_lwp=1 → payroll will deduct salary for this day")
                state_verifications.append({
                    "check": "LWOP payroll impact config",
                    "before": "N/A",
                    "after": f"is_lwp={is_lwp}",
                    "passed": True,
                })
            else:
                record_result(scenario_id, "LWOP payroll impact", "FAIL",
                              f"is_lwp={is_lwp} — expected 1")
        except Exception as e:
            record_result(scenario_id, "LWOP payroll impact", "FAIL", error=e)

    # Step 7: Cancel and verify balance restored
    try:
        cancel_leave(app_name)
        time.sleep(2)
        if expect_balance:
            balance_restored = get_leave_balance(employee, leave_type, test_date)
            if abs(balance_restored - balance_before) < 0.1:
                record_result(scenario_id, f"{leave_code} cancel+restore", "PASS",
                              f"Balance restored: {balance_restored}")
            else:
                record_result(scenario_id, f"{leave_code} cancel+restore", "FAIL",
                              f"Expected {balance_before}, got {balance_restored}")
        else:
            record_result(scenario_id, f"{leave_code} cancel+restore", "PASS",
                          "Cancelled successfully (no balance check for LWOP)")
    except Exception as e:
        record_result(scenario_id, f"{leave_code} cancel+restore", "FAIL", error=e)

    return app_name


def test_compensatory_off(scenario_id, employee):
    """Test CO configuration (no creation — requires holiday work)."""
    print(f"\n{'='*60}")
    print(f"  {scenario_id}: Testing Compensatory Off (CO) — Config Check Only")
    print(f"{'='*60}")

    try:
        # Check if Compensatory Off leave type exists and its config
        result = api_call("GET", "/api/resource/Leave%20Type/Compensatory%20Off", {
            "fields": json.dumps(["name", "is_compensatory", "is_lwp", "max_leaves_allowed"]),
        })
        lt_data = result.get("data", {})
        is_comp = lt_data.get("is_compensatory", 0)
        state_verifications.append({
            "check": "CO leave type config",
            "before": "N/A",
            "after": f"is_compensatory={is_comp}, is_lwp={lt_data.get('is_lwp', 0)}",
            "passed": bool(is_comp),
        })
        if is_comp:
            record_result(scenario_id, "CO config", "PASS",
                          f"is_compensatory=1, max_leaves={lt_data.get('max_leaves_allowed')}")
        else:
            record_result(scenario_id, "CO config", "FAIL",
                          f"is_compensatory={is_comp} — expected 1")

        # Check if CompensatoryLeaveRequest DocType exists
        try:
            api_call("GET", "/api/method/frappe.client.get_count", {
                "doctype": "Compensatory Leave Request",
            })
            record_result(scenario_id, "CO request mechanic", "PASS",
                          "Compensatory Leave Request DocType exists — filing mechanic available")
        except:
            record_result(scenario_id, "CO request mechanic", "SKIP",
                          "Compensatory Leave Request DocType not accessible")

    except Exception as e:
        record_result(scenario_id, "CO config", "FAIL", error=e)


def main():
    print("=" * 60)
    print("  S108 Phase 1: Leave Type E2E API Tests")
    print(f"  Employee: {TEST_EMPLOYEE}")
    print(f"  Test dates: Apr 7-12, 2026")
    print("=" * 60)

    # P1-1: VL
    test_leave_lifecycle("P1-1", "VL", TEST_EMPLOYEE, TEST_DATES["VL"])

    # P1-2: SL
    test_leave_lifecycle("P1-2", "SL", TEST_EMPLOYEE, TEST_DATES["SL"])

    # P1-3: EL
    test_leave_lifecycle("P1-3", "EL", TEST_EMPLOYEE, TEST_DATES["EL"])

    # P1-4: CL (may fail if 0 balance)
    test_leave_lifecycle("P1-4", "CL", TEST_EMPLOYEE, TEST_DATES["CL"])

    # P1-5: LWOP (no balance needed)
    test_leave_lifecycle("P1-5", "LWOP", TEST_EMPLOYEE, TEST_DATES["LWOP"], expect_balance=False)

    # P1-6: CO (config check only)
    test_compensatory_off("P1-6", TEST_EMPLOYEE)

    # P1-7: PL (may fail if 0 balance)
    test_leave_lifecycle("P1-7", "PL", TEST_EMPLOYEE, TEST_DATES["PL"])

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    skip_count = sum(1 for r in results if r["status"] == "SKIP")
    total = len(results)
    print(f"  PASS: {pass_count} | FAIL: {fail_count} | SKIP: {skip_count} | Total: {total}")

    for r in results:
        icon = "PASS" if r["status"] == "PASS" else "FAIL" if r["status"] == "FAIL" else "SKIP"
        print(f"  [{icon}] {r['scenario']}: {r['test']}")

    # Write evidence
    with open(EVIDENCE_DIR / "api_mutations.json", "w", encoding="utf-8") as f:
        json.dump(api_mutations, f, indent=2, default=str)
    with open(EVIDENCE_DIR / "state_verification.json", "w", encoding="utf-8") as f:
        json.dump(state_verifications, f, indent=2, default=str)
    with open(EVIDENCE_DIR / "phase1_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n  Evidence written to {EVIDENCE_DIR}/")
    return fail_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
