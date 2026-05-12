#!/usr/bin/env python3
"""Investigate why SE generator didn't fire after sweep run."""
from __future__ import annotations
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json, sys
import frappe  # type: ignore

payload = {}
try:
    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    frappe.set_user("Administrator")

    # 1. Check what's registered in doc_events for Sales Invoice
    hooks = frappe.get_hooks("doc_events") or {}
    si_hooks = hooks.get("Sales Invoice", {}) or {}
    payload["si_on_submit_hooks"] = list(si_hooks.get("on_submit", []) or [])
    payload["si_on_cancel_hooks"] = list(si_hooks.get("on_cancel", []) or [])
    se_hooks = hooks.get("Stock Entry", {}) or {}
    payload["se_validate_hooks"] = list(se_hooks.get("validate", []) or [])

    # 2. Check Custom Field exists
    payload["se_bki_si_reference_field_exists"] = frappe.get_meta("Stock Entry").has_field(
        "bki_si_reference"
    )

    # 3. BEI Settings toggles
    settings = frappe.get_single("BEI Settings")
    payload["enable_bki_store_pi_generator"] = getattr(settings, "enable_bki_store_pi_generator", "FIELD_MISSING")
    payload["enable_bki_store_stock_entry_generator"] = getattr(
        settings, "enable_bki_store_stock_entry_generator", "FIELD_MISSING"
    )
    payload["bki_sales_naming_series"] = getattr(settings, "bki_sales_naming_series", None)

    # 4. Last 10 minutes of error log for SE generator
    errs = frappe.db.sql(
        """SELECT name, method, error, creation FROM `tabError Log`
           WHERE creation >= NOW() - INTERVAL 10 MINUTE
             AND (method LIKE '%%S247%%' OR error LIKE '%%S247%%' OR error LIKE '%%bki_store_stock_entry%%')
           ORDER BY creation DESC LIMIT 5""",
        as_dict=True,
    )
    payload["recent_se_errors"] = [
        {"name": e["name"], "method": e["method"], "creation": str(e["creation"]),
         "preview": (e["error"] or "")[:500]}
        for e in errs
    ]

    # 5. Try importing the module to see if it loads
    try:
        from hrms.api.bki_store_stock_entry_generator import maybe_generate_store_stock_entry
        payload["module_imports_ok"] = True
        import inspect
        payload["module_source_snippet"] = inspect.getsource(maybe_generate_store_stock_entry)[:1000]
    except Exception as ie:
        payload["module_imports_ok"] = False
        payload["module_import_error"] = str(ie)[:300]

    # 6. Did any SE get created in last 10 min with our test SI references?
    recent_ses = frappe.db.sql(
        """SELECT name, bki_si_reference, company, docstatus, creation
           FROM `tabStock Entry`
           WHERE creation >= NOW() - INTERVAL 30 MINUTE
             AND bki_si_reference IS NOT NULL AND bki_si_reference != ''
           ORDER BY creation DESC LIMIT 5""",
        as_dict=True,
    )
    payload["recent_ses_with_si_ref"] = [
        {"name": s["name"], "si_ref": s["bki_si_reference"], "company": s["company"],
         "docstatus": s["docstatus"], "creation": str(s["creation"])}
        for s in recent_ses
    ]

except Exception as e:
    import traceback
    payload["status"] = "ERROR"
    payload["fatal_error"] = str(e)
    payload["traceback"] = traceback.format_exc()

with open("/tmp/s247_se_diag.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, default=str)
sys.stdout.write("OK\n")
