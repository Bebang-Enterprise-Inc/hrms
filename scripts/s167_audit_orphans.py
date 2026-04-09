"""S167 AUDIT: verify Phase 6 rollback claims from L3_FINAL_REPORT_REDO.md.

Runs inside the Frappe backend container. Emits a JSON blob between
S167_AUDIT_BEGIN / S167_AUDIT_END markers so the driver can parse it.

Checks:
  1. Department PCF funds (should NOT exist post-rollback)
  2. PCF-TEST-STORE-BGC - BEI store fund (should EXIST, is_enabled=1)
  3. TEST-STORE-BGC - BEI warehouse (should EXIST, not disabled, not group)
  4. Test employee departments restored
  5. Specific batches 00003/00004/00005 (should NOT exist)
  6. Specific expenses 00081..00090 (should NOT exist)
  7. Orphan BEI PCF Batch Item rows
  8. BEI Expense Request rows with dangling pcf_batch
"""

from __future__ import annotations

import json
import os
import sys
import traceback

for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe  # type: ignore

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

report = {"ok": True, "checks": {}, "errors": []}


def _safe(key, fn):
    try:
        report["checks"][key] = fn()
    except Exception as e:
        report["ok"] = False
        report["errors"].append({"check": key, "error": str(e), "tb": traceback.format_exc()})


FUND_DT = "BEI Petty Cash Fund"


def dept_funds():
    rows = frappe.db.sql(
        f"""
        SELECT name, fund_type, is_enabled, department, store, fund_label, fund_amount, current_balance
        FROM `tab{FUND_DT}`
        WHERE fund_type='Department'
        """,
        as_dict=True,
    )
    all_funds = frappe.db.sql(
        f"""
        SELECT name, fund_type, is_enabled, department, store, fund_label
        FROM `tab{FUND_DT}`
        ORDER BY fund_type, name
        """,
        as_dict=True,
    )
    target_names = ["PCF-HR and Admin", "PCF-Supply Chain", "PCF-Commissary"]
    existing_targets = [r for r in all_funds if r["name"] in target_names]
    return {
        "all_funds_count": len(all_funds),
        "all_funds": all_funds,
        "dept_funds": rows,
        "dept_funds_remaining_count": len(rows),
        "target_dept_funds_found": existing_targets,
    }


def store_fund():
    name = "PCF-TEST-STORE-BGC - BEI"
    if not frappe.db.exists(FUND_DT, name):
        # search alternatives
        alts = frappe.db.sql(
            f"""SELECT name, fund_type, is_enabled, store, fund_label
                FROM `tab{FUND_DT}`
                WHERE name LIKE '%TEST-STORE-BGC%' OR store LIKE '%TEST-STORE-BGC%'""",
            as_dict=True,
        )
        return {"exists": False, "alternatives": alts}
    doc = frappe.db.get_value(
        FUND_DT,
        name,
        ["name", "fund_type", "is_enabled", "store", "department", "current_balance", "fund_amount"],
        as_dict=True,
    )
    return {"exists": True, "doc": doc}


def warehouse():
    name = "TEST-STORE-BGC - BEI"
    if not frappe.db.exists("Warehouse", name):
        return {"exists": False}
    doc = frappe.db.get_value(
        "Warehouse",
        name,
        ["name", "disabled", "is_group", "parent_warehouse", "company"],
        as_dict=True,
    )
    return {"exists": True, "doc": doc}


def employees():
    results = {}
    for emp in ["TEST-HR-001", "TEST-COMMISSARY-001", "TEST-WAREHOUSE-001"]:
        if frappe.db.exists("Employee", emp):
            results[emp] = frappe.db.get_value(
                "Employee", emp, ["name", "department", "status", "employee_name"], as_dict=True
            )
        else:
            results[emp] = None
    return results


def batches():
    targets = ["BEI-PCF-2026-00003", "BEI-PCF-2026-00004", "BEI-PCF-2026-00005"]
    existing = []
    for b in targets:
        if frappe.db.exists("BEI PCF Batch", b):
            existing.append(
                frappe.db.get_value(
                    "BEI PCF Batch",
                    b,
                    ["name", "status", "pcf_fund", "docstatus"],
                    as_dict=True,
                )
            )
    # also recent 48h
    recent = frappe.db.sql(
        """
        SELECT name, status, pcf_fund, docstatus, creation
        FROM `tabBEI PCF Batch`
        WHERE creation >= NOW() - INTERVAL 48 HOUR
        ORDER BY creation DESC
        """,
        as_dict=True,
    )
    all_recent = frappe.db.sql(
        """
        SELECT name, status, pcf_fund, docstatus, creation
        FROM `tabBEI PCF Batch`
        ORDER BY creation DESC
        LIMIT 20
        """,
        as_dict=True,
    )
    recent = {"48h": recent, "last_20_all_time": all_recent}
    return {"targets_still_existing": existing, "recent_48h": recent}


def expenses():
    targets = [f"BEI-EXP-2026-{i:05d}" for i in range(81, 91)]
    existing = []
    for e in targets:
        if frappe.db.exists("BEI Expense Request", e):
            existing.append(
                frappe.db.get_value(
                    "BEI Expense Request",
                    e,
                    ["name", "status", "pcf_batch", "pcf_fund", "docstatus", "manual_amount"],
                    as_dict=True,
                )
            )
    recent = frappe.db.sql(
        """
        SELECT name, status, pcf_batch, pcf_fund, docstatus, manual_amount, creation
        FROM `tabBEI Expense Request`
        WHERE creation >= NOW() - INTERVAL 48 HOUR
        ORDER BY creation DESC
        """,
        as_dict=True,
    )
    return {"targets_still_existing": existing, "recent_48h": recent}


def orphan_batch_items():
    rows = frappe.db.sql(
        """
        SELECT bi.name, bi.parent
        FROM `tabBEI PCF Batch Item` bi
        LEFT JOIN `tabBEI PCF Batch` b ON b.name = bi.parent
        WHERE b.name IS NULL
        LIMIT 50
        """,
        as_dict=True,
    )
    return {"count": len(rows), "sample": rows}


def dangling_pcf_batch_refs():
    rows = frappe.db.sql(
        """
        SELECT e.name, e.pcf_batch
        FROM `tabBEI Expense Request` e
        LEFT JOIN `tabBEI PCF Batch` b ON b.name = e.pcf_batch
        WHERE e.pcf_batch IS NOT NULL AND e.pcf_batch != '' AND b.name IS NULL
        LIMIT 50
        """,
        as_dict=True,
    )
    return {"count": len(rows), "sample": rows}


_safe("dept_funds", dept_funds)
_safe("store_fund", store_fund)
_safe("warehouse", warehouse)
_safe("employees", employees)
_safe("batches", batches)
_safe("expenses", expenses)
_safe("orphan_batch_items", orphan_batch_items)
_safe("dangling_pcf_batch_refs", dangling_pcf_batch_refs)

print("S167_AUDIT_BEGIN")
print(json.dumps(report, indent=2, default=str))
print("S167_AUDIT_END")
sys.exit(0)
