#!/usr/bin/env python3
"""
L1 API endpoint runner.

Reads docs/testing/ROUTE_REGISTRY.md and performs endpoint checks by module.
Writes standardized run artifact JSON under output/l1/runs/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
ROUTE_REGISTRY = ROOT / "docs" / "testing" / "ROUTE_REGISTRY.md"
BASE_HQ = "https://hq.bebang.ph"
DEFAULT_PASSWORD = "BeiTest2026!"


SECTION_TO_MODULE = {
    "Home & Profile": "home-profile",
    "Store Operations": "store-ops",
    "Inventory": "inventory",
    "Receiving": "receiving",
    "HR Self-Service": "hr",
    "Expenses": "expense",
    "Communication": "communication",
    "Supervisor Tools": "supervisor",
    "Maintenance & Projects": "maintenance",
    "Warehouse": "warehouse",
    "Commissary": "commissary",
    "Procurement (HQ User only)": "procurement",
    "Stock Counting (External Auditor, Store Staff, Warehouse)": "stock-counting",
    "Finance & Accounting (HQ User only)": "finance",
    "Tasks & Projects": "tasks-projects",
    "Analytics": "analytics",
    "Employee Clearance": "employee-clearance",
    "Recruitment": "recruitment",
    "Onboarding": "onboarding",
}

ROLE_TO_EMAIL = {
    "test.crew1": "test.crew1@bebang.ph",
    "test.staff": "test.staff@bebang.ph",
    "test.supervisor": "test.supervisor@bebang.ph",
    "test.area": "test.area@bebang.ph",
    "test.hr": "test.hr@bebang.ph",
    "test.projects": "test.projects@bebang.ph",
    "test.projects.staff": "test.projects.staff@bebang.ph",
    "test.warehouse": "test.warehouse@bebang.ph",
    "test.commissary": "test.commissary@bebang.ph",
    # Fallback for "(no test account)" in route registry.
    "hq_user_fallback": "test.hr@bebang.ph",
}

# Minimal fallback payloads to reduce false failures on strict POST endpoints.
ENDPOINT_PAYLOAD_HINTS: dict[str, dict[str, Any]] = {
    "hrms.api.store.submit_opening_report": {
        "store": "Market Market - BK",
        "checklist_items": [],
        "notes": "L1 smoke check",
    },
    "hrms.api.store.submit_bank_deposit": {"store": "TEST-STORE-BGC - BEI", "deposits": [], "photos": []},
    "hrms.api.store.upload_pos_data": {
        "store": "TEST-STORE-BGC - BEI",
        "pos_date": "2026-02-25",
        "pos_system": "Mosaic",
        "discount_report": "",
        "transaction_report": "",
        "product_mix": "",
        "daily_sales_revenue": "",
        "sales_summary": "",
    },
    "hrms.api.payroll.submit_leave_application": {
        "leave_type": "Vacation Leave",
        "from_date": "2026-03-15",
        "to_date": "2026-03-15",
        "reason": "L1 smoke check",
    },
    "hrms.api.submit_leave_application": {
        "leave_type": "Vacation Leave",
        "from_date": "2026-03-15",
        "to_date": "2026-03-15",
        "reason": "L1 smoke check",
    },
    "hrms.api.coverage.submit_coverage_request": {
        "store": "TEST-STORE-BGC - BEI",
        "coverage_date": "2026-03-15",
        "shift": "Opening",
        "reason": "L1 smoke check",
        "absent_employee": "TEST-CREW-001",
    },
    "hrms.api.coverage.request_coverage": {
        "store": "TEST-STORE-BGC - BEI",
        "coverage_date": "2026-03-15",
        "shift": "Opening",
        "reason": "L1 smoke check",
        "absent_employee": "TEST-CREW-001",
    },
    "hrms.api.expense.submit_expense": {
        "manual_vendor": "L1 Vendor",
        "manual_description": "L1 smoke",
        "manual_amount": 10.5,
        "manual_date": "2026-02-25",
        "receipt_photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgY8rN8gAAAAASUVORK5CYII=",
    },
    "hrms.api.communication.send_kudos": {
        "to_employee": "TEST-STAFF-001",
        "category": "Teamwork",
        "message": "L1 smoke",
    },
    "hrms.api.communication.submit_complaint": {
        "category": "Operations",
        "subject": "L1 smoke",
        "description": "L1 smoke complaint payload",
    },
    "hrms.api.communication.submit_ceo_complaint": {
        "category": "Operations",
        "subject": "L1 smoke",
        "description": "L1 smoke complaint payload",
    },
    "hrms.api.communication.create_support_ticket": {
        "category": "IT",
        "subject": "L1 smoke",
        "description": "L1 smoke support payload",
    },
    "hrms.api.projects.assign_maintenance_request": {"request_id": "BEI-MR-00001", "assigned_to": "test.projects.staff@bebang.ph"},
    "hrms.api.projects.update_maintenance_status": {"request_id": "BEI-MR-00001", "status": "In Progress"},
    "hrms.api.projects.record_maintenance_completion": {
        "request_id": "BEI-MR-00001",
        "completion_date": "2026-02-25",
        "technician_name": "L1 Tech",
        "work_description": "L1 smoke completion",
        "resolution_status": "Resolved",
    },
    "hrms.api.inventory.submit_cycle_count_v2": {
        "store": "Market Market - BK",
        "count_date": "2026-02-25",
        "count_type": "Store Monthly",
        "items": [],
    },
    "hrms.api.inventory.get_cycle_count": {
        "name": "BEI-CC-00001",
    },
    "hrms.api.shift_tracking.punch_in": {
        "latitude": 14.5547,
        "longitude": 121.0244,
        "accuracy": 5,
        "selfie_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgY8rN8gAAAAASUVORK5CYII=",
    },
    "hrms.api.shift_tracking.punch_out": {"latitude": 14.5547, "longitude": 121.0244, "accuracy": 5},
}


@dataclass
class RouteEntry:
    module: str
    section: str
    feature: str
    route: str
    test_role: str
    endpoint: str


def _norm_role(raw: str) -> str:
    role = raw.strip().strip("`").lower()
    role = role.replace(" ", "")
    role = role.replace("(", "").replace(")", "")
    if role in {"notestaccount", "no test account", ""}:
        return "hq_user_fallback"
    if role in {"notmapped", "unmapped", "-"}:
        return "unmapped_role"
    return role


def _parse_registry(path: Path) -> list[RouteEntry]:
    text = path.read_text(encoding="utf-8")
    section = ""
    entries: list[RouteEntry] = []
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            section = heading.group(1).strip()
            continue

        if not line.startswith("|"):
            continue
        if "---" in line or "Feature" in line:
            continue

        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 4:
            continue

        feature, route, test_role, endpoint = parts[:4]
        endpoint = endpoint.strip("`")
        route = route.strip("`")
        if endpoint in {"-", ""}:
            continue

        module = SECTION_TO_MODULE.get(section)
        if not module:
            continue

        entries.append(
            RouteEntry(
                module=module,
                section=section,
                feature=feature,
                route=route,
                test_role=_norm_role(test_role),
                endpoint=endpoint,
            )
        )
    return entries


def _endpoint_method(endpoint: str) -> str:
    tail = endpoint.split(".")[-1].lower()
    get_like = (
        tail.startswith("get_")
        or tail.startswith("list_")
        or tail.startswith("fetch_")
        or tail.startswith("search_")
        or tail.startswith("validate_")
        or tail.startswith("check_")
    )
    return "GET" if get_like else "POST"


def _login(email: str, password: str = DEFAULT_PASSWORD) -> requests.Session:
    s = requests.Session()
    resp = s.post(
        f"{BASE_HQ}/api/method/login",
        data={"usr": email, "pwd": password},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: HTTP {resp.status_code}")
    return s


def _run_endpoint(
    session: requests.Session,
    endpoint: str,
    method: str,
) -> tuple[int, str, str, float]:
    url = f"{BASE_HQ}/api/method/{endpoint}"
    data = ENDPOINT_PAYLOAD_HINTS.get(endpoint, {})
    started = time.time()
    try:
        if method == "GET":
            resp = session.get(url, params=data, timeout=30)
        else:
            resp = session.post(url, json=data, timeout=30)
        elapsed_ms = (time.time() - started) * 1000.0
        if 200 <= resp.status_code < 300:
            status = "PASS"
        elif 400 <= resp.status_code < 500:
            # L1 focuses on endpoint liveness/no-crash; validation/rbac 4xx is not backend crash.
            status = "WARN"
        else:
            status = "FAIL"
        body_snippet = (resp.text or "")[:280].replace("\n", " ")
        return resp.status_code, status, body_snippet, elapsed_ms
    except Exception as exc:
        elapsed_ms = (time.time() - started) * 1000.0
        return 0, "FAIL", f"{type(exc).__name__}: {exc}", elapsed_ms


def _collect_targets(entries: list[RouteEntry], module: str) -> list[RouteEntry]:
    if module == "all":
        return entries
    return [e for e in entries if e.module == module]


def _available_modules(entries: list[RouteEntry]) -> list[str]:
    return sorted({e.module for e in entries})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run L1 API checks from ROUTE_REGISTRY.")
    parser.add_argument("--module", default="all", help="Module key from route registry or 'all'.")
    parser.add_argument("--list", action="store_true", help="List available modules and exit.")
    args = parser.parse_args()

    if not ROUTE_REGISTRY.exists():
        print(f"Missing route registry: {ROUTE_REGISTRY}")
        return 2

    entries = _parse_registry(ROUTE_REGISTRY)
    modules = _available_modules(entries)

    if args.list:
        print("L1 modules:")
        for module in modules:
            count = len([e for e in entries if e.module == module])
            print(f"- {module:14} endpoints={count}")
        return 0

    if args.module != "all" and args.module not in modules:
        print(f"Unknown module: {args.module}")
        print(f"Available: {', '.join(modules)}")
        return 2

    targets = _collect_targets(entries, args.module)
    if not targets:
        print(f"No endpoints found for module={args.module}")
        return 2

    sessions: dict[str, requests.Session] = {}
    run_rows: list[dict[str, Any]] = []
    hard_fail = False

    for row in targets:
        email = ROLE_TO_EMAIL.get(row.test_role)
        if not email:
            status = "WARN"
            run_rows.append(
                {
                    "module": row.module,
                    "feature": row.feature,
                    "endpoint": row.endpoint,
                    "role": row.test_role,
                    "method": _endpoint_method(row.endpoint),
                    "status_code": 0,
                    "status": status,
                    "ok": False,
                    "detail": f"No mapped account for role '{row.test_role}' (skipped).",
                    "elapsed_ms": 0,
                }
            )
            continue

        if row.test_role not in sessions:
            try:
                sessions[row.test_role] = _login(email=email)
            except Exception as exc:
                hard_fail = True
                run_rows.append(
                    {
                        "module": row.module,
                        "feature": row.feature,
                        "endpoint": row.endpoint,
                        "role": row.test_role,
                        "method": _endpoint_method(row.endpoint),
                        "status_code": 0,
                        "status": "FAIL",
                        "ok": False,
                        "detail": f"Login failed for {email}: {exc}",
                        "elapsed_ms": 0,
                    }
                )
                continue

        method = _endpoint_method(row.endpoint)
        status_code, status, detail, elapsed_ms = _run_endpoint(
            session=sessions[row.test_role],
            endpoint=row.endpoint,
            method=method,
        )
        if status == "FAIL":
            hard_fail = True
        run_rows.append(
            {
                "module": row.module,
                "feature": row.feature,
                "endpoint": row.endpoint,
                "role": row.test_role,
                "method": method,
                "status_code": status_code,
                "status": status,
                "ok": status == "PASS",
                "detail": detail,
                "elapsed_ms": int(elapsed_ms),
            }
        )
        print(f"{status:5} [{status_code:3}] {row.module:12} {row.endpoint}")

    module_summary: dict[str, dict[str, int]] = {}
    for module in _available_modules(targets):
        rows = [r for r in run_rows if r["module"] == module]
        passed = len([r for r in rows if r["status"] == "PASS"])
        warned = len([r for r in rows if r["status"] == "WARN"])
        failed = len([r for r in rows if r["status"] == "FAIL"])
        module_summary[module] = {"total": len(rows), "passed": passed, "warned": warned, "failed": failed}

    out_dir = ROOT / "output" / "l1" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_file = out_dir / f"l1_run_{stamp}.json"

    payload = {
        "ran_at": datetime.now().isoformat(),
        "requested_module": args.module,
        "route_registry": str(ROUTE_REGISTRY.relative_to(ROOT)).replace("\\", "/"),
        "base_hq": BASE_HQ,
        "summary": {
            "total": len(run_rows),
            "passed": len([r for r in run_rows if r["status"] == "PASS"]),
            "warned": len([r for r in run_rows if r["status"] == "WARN"]),
            "failed": len([r for r in run_rows if r["status"] == "FAIL"]),
            "by_module": module_summary,
        },
        "results": run_rows,
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"RESULT_FILE={out_file.relative_to(ROOT)}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
