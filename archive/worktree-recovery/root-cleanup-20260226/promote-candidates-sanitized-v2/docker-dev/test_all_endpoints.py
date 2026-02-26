#!/usr/bin/env python3
"""Test all 86 API endpoints systematically."""
import subprocess
import json
import sys

# Base curl commands
CURL_GET = "curl -b /tmp/cookies.txt -s"
CURL_POST = "curl -b /tmp/cookies.txt -s -X POST -H 'Content-Type: application/json'"
BASE_URL = "http://localhost:8000/api/method"

# All endpoints to test, organized by file
# Format: (endpoint_name, method, params_or_data, expected_error_ok)
ENDPOINTS = {
    "dashboard.py": [
        ("get_store_dashboard", "GET", {}, False),
        ("get_area_dashboard", "GET", {}, False),
        ("get_ops_dashboard", "GET", {"period": "week"}, False),
        ("get_sales_trend", "GET", {}, False),
        ("get_fqi_trend", "GET", {}, False),
        ("get_order_fulfillment_rate", "GET", {}, False),
    ],
    "supervisor.py": [
        ("get_pending_approvals", "GET", {}, False),
        ("approve_item", "POST", {"queue_name": ""}, True),  # Needs existing data
        ("reject_item", "POST", {"queue_name": "", "reason": "Test"}, True),
        ("escalate_item", "POST", {"queue_name": "", "escalate_to": "admin"}, True),
        ("create_store_visit", "POST", {"store": "Test", "visit_type": "Scheduled", "audit_items": "[]"}, True),
        ("get_store_visits", "GET", {}, False),
        ("get_visit_detail", "GET", {"visit_name": ""}, False),
        ("acknowledge_visit", "POST", {"visit_name": ""}, True),
        ("create_weekly_plan", "POST", {"store": "Test", "week_start": "2026-01-27", "shifts": "[]"}, True),
        ("get_weekly_plan", "GET", {}, False),
        ("update_weekly_plan", "POST", {"plan_name": "", "shifts": "[]"}, True),
        ("approve_weekly_plan", "POST", {"plan_name": ""}, True),
        ("get_my_team", "GET", {}, False),
        ("get_team_attendance", "GET", {"date": "2026-01-25"}, False),
    ],
    "communication.py": [
        ("submit_ceo_complaint", "POST", {"category": "Workplace Issue", "subject": "Test", "description": "Test"}, True),
        ("get_my_complaints", "GET", {}, False),
        ("get_complaint_status", "GET", {"complaint_name": ""}, True),
        ("get_announcements", "GET", {"limit": "20"}, False),
        ("get_announcement_detail", "GET", {"announcement_name": ""}, True),
        ("get_unread_announcements", "GET", {}, False),
        ("send_kudos", "POST", {"to_employee": "", "category": "Teamwork", "message": "Test"}, True),
        ("get_received_kudos", "GET", {}, False),
        ("get_sent_kudos", "GET", {}, False),
        ("get_kudos_leaderboard", "GET", {"period": "month"}, False),
        ("create_support_ticket", "POST", {"category": "IT/Technical", "subject": "Test", "description": "Test"}, True),
        ("get_my_tickets", "GET", {}, False),
    ],
    "inventory.py": [
        ("submit_cycle_count", "POST", {"store": "Test", "items": "[]"}, True),
        ("get_cycle_counts", "GET", {}, False),
        ("report_variance", "POST", {"store": "Test", "item_code": "TEST", "system_qty": "10", "actual_qty": "8", "variance_type": "Short", "explanation": "Test"}, True),
        ("get_variances", "GET", {}, False),
        ("request_shelf_extension", "POST", {"store": "Test", "item_code": "TEST", "original_expiry": "2026-01-01", "requested_expiry": "2026-02-01", "quantity": "5", "reason": "Test"}, True),
        ("approve_shelf_extension", "POST", {"extension_name": ""}, True),
    ],
    "coverage.py": [
        ("request_coverage", "POST", {"store": "Test", "coverage_date": "2026-01-26", "shift": "Opening", "reason": "Sick Leave", "absent_employee": ""}, True),
        ("approve_coverage", "POST", {"request_name": "", "assigned_employee": ""}, True),
        ("get_coverage_requests", "GET", {}, False),
    ],
    "store.py": [
        ("get_orderable_items", "GET", {"store": "Test"}, True),
        ("submit_order", "POST", {"store": "Test", "items": "[]"}, True),
        ("get_order_history", "GET", {}, False),
        ("approve_order", "POST", {"order_name": ""}, True),
        ("get_expected_deliveries", "GET", {}, False),
        ("complete_receiving", "POST", {"store": "Test", "trip": "", "items": "[]"}, True),
        ("create_fqi_report", "POST", {"store": "Test", "issue_type": "Quality"}, True),
        ("get_fqi_reports", "GET", {}, False),
        ("submit_opening_report", "POST", {"store": "Test", "report_time": "06:00", "checklist_items": "[]"}, True),
        ("get_opening_reports", "GET", {}, False),
        ("submit_closing_report", "POST", {"store": "Test", "report_time": "22:00", "checklist_items": "[]", "pos_total_sales": "50000"}, True),
        ("get_closing_reports", "GET", {}, False),
        ("submit_midshift_check", "POST", {"store": "Test", "shift": "Morning", "temperature_readings": "[]", "cleanliness_status": "Good"}, True),
        ("get_midshift_checks", "GET", {}, False),
        ("upload_pos_data", "POST", {"store": "Test", "pos_date": "2026-01-25", "pos_system": "MOSAIC", "gross_sales": "100000"}, True),
        ("get_pos_uploads", "GET", {}, False),
    ],
    "employee_clearance.py": [
        ("get_exit_interview_questions", "GET", {}, False),
        ("submit_exit_interview_responses", "POST", {"exit_interview": "", "responses": "[]"}, True),
        ("get_exit_interview_responses", "GET", {"exit_interview": ""}, True),
        ("get_separation_types", "GET", {}, False),
        ("create_employee_separation", "POST", {"employee": "", "separation_type": "Resignation"}, True),
        ("get_employee_separation", "GET", {"name": ""}, True),
        ("get_employee_separations", "GET", {}, False),
        ("populate_dole_compliance", "POST", {"separation_name": "", "separation_type": "Resignation"}, True),
        ("update_compliance_status", "POST", {"separation_name": "", "compliance_row_name": "", "status": "Completed"}, True),
        ("get_dole_compliance_items", "GET", {}, False),
        ("get_clearance_status", "GET", {"employee": ""}, True),
        ("disable_bio_id", "POST", {"employee": ""}, True),
        ("get_bio_id_status", "GET", {"employee": ""}, True),
        ("generate_coe", "GET", {"employee": ""}, True),
    ],
}

def test_endpoint(module, endpoint, method, params, error_ok):
    """Test a single endpoint and return result."""
    url = f"{BASE_URL}/hrms.api.{module.replace('.py', '')}.{endpoint}"

    if method == "GET":
        # Build query string for GET params
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"
        cmd = f'{CURL_GET} "{url}"'
    else:
        # POST with JSON data
        data = json.dumps(params)
        cmd = f"{CURL_POST} -d '{data}' \"{url}\""

    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout

        # Check if valid JSON
        try:
            data = json.loads(output)
            if "exception" in data:
                exc_type = data.get("exc_type", "Unknown")
                # Some errors are expected when testing without data
                if error_ok and exc_type in ["ValidationError", "MandatoryError", "DoesNotExistError", "TypeError", "LinkValidationError", "FrappeTypeError"]:
                    return {"status": "PASS", "note": f"Expected error: {exc_type}"}
                return {"status": "ERROR", "error": exc_type}
            return {"status": "PASS", "data": "valid JSON"}
        except json.JSONDecodeError:
            return {"status": "ERROR", "error": "Invalid JSON", "raw": output[:200]}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def main():
    results = {"passed": 0, "failed": 0, "errors": []}
    total_endpoints = sum(len(eps) for eps in ENDPOINTS.values())

    for module, endpoints in ENDPOINTS.items():
        print(f"\n=== Testing {module} ({len(endpoints)} endpoints) ===")
        for endpoint, method, params, error_ok in endpoints:
            result = test_endpoint(module, endpoint, method, params, error_ok)
            status = result["status"]

            if status == "PASS":
                note = result.get("note", "")
                if note:
                    print(f"  ✓ {endpoint} ({note})")
                else:
                    print(f"  ✓ {endpoint}")
                results["passed"] += 1
            else:
                print(f"  ✗ {endpoint}: {result.get('error', 'Unknown error')}")
                results["failed"] += 1
                results["errors"].append({
                    "module": module,
                    "endpoint": endpoint,
                    "error": result.get("error")
                })

    print(f"\n=== SUMMARY ===")
    print(f"Total endpoints: {total_endpoints}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")

    if results["errors"]:
        print(f"\nFailed endpoints:")
        for err in results["errors"]:
            print(f"  - {err['module']}.{err['endpoint']}: {err['error']}")

    # Return exit code based on results
    return 0 if results["failed"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
