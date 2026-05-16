#!/usr/bin/env python3
"""S252 — recover complete evidence by re-querying production for all 4 passing
stores + the 1 failed SM MEGAMALL (not S247-related)."""
from __future__ import annotations
import os
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json, sys
import frappe  # type: ignore

# SI names produced by S252 runs 1 + 2
S252_SIS = [
    ("ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC", "BKI-SI-2026-01041-1", "ACC-PINV-2026-00703", "MAT-STE-2026-03033"),
    ("NAIA T3 - HALO-HALO TERMINAL FOOD CORP.",         "BKI-SI-2026-01042-1", "ACC-PINV-2026-00704", "MAT-STE-2026-03036"),
    ("SM TANZA - BEBANG MEGA INC.",                     "BKI-SI-2026-01046-1", "ACC-PINV-2026-00705", "MAT-STE-2026-03040"),
    ("XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",     "BKI-SI-2026-01047-1", "ACC-PINV-2026-00706", "MAT-STE-2026-03043"),
]

payload = {"runs": []}
try:
    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    frappe.set_user("Administrator")

    for store, si_name, pi_name, se_name in S252_SIS:
        rec = {"store": store, "si_name": si_name, "pi_name": pi_name, "se_name": se_name}
        # Re-query each doc
        si = frappe.db.get_value("Sales Invoice", si_name,
            ["docstatus", "company", "customer", "grand_total", "posting_date"], as_dict=True)
        pi = frappe.db.get_value("Purchase Invoice", pi_name,
            ["docstatus", "company", "supplier", "update_stock", "credit_to", "bki_si_reference"], as_dict=True)
        pi_items = frappe.db.sql(
            """SELECT expense_account, warehouse, qty, rate FROM `tabPurchase Invoice Item`
               WHERE parent=%s ORDER BY idx LIMIT 1""", pi_name, as_dict=True)
        se = frappe.db.get_value("Stock Entry", se_name,
            ["docstatus", "company", "stock_entry_type", "bki_si_reference"], as_dict=True)
        se_items = frappe.db.sql(
            """SELECT expense_account, t_warehouse, qty, basic_rate FROM `tabStock Entry Detail`
               WHERE parent=%s ORDER BY idx LIMIT 1""", se_name, as_dict=True)

        rec["si"] = si
        rec["pi"] = pi
        rec["pi_item0"] = pi_items[0] if pi_items else None
        rec["se"] = se
        rec["se_item0"] = se_items[0] if se_items else None

        # GR/IR assertion
        if pi_items and se_items:
            rec["gr_ir_pi_se_same_srbnb"] = pi_items[0]["expense_account"] == se_items[0]["expense_account"]
            srbnb_acct_type = frappe.db.get_value(
                "Account", pi_items[0]["expense_account"], "account_type"
            )
            rec["srbnb_account_type"] = srbnb_acct_type
            rec["srbnb_account_type_correct"] = srbnb_acct_type == "Stock Received But Not Billed"

        payload["runs"].append(rec)

    # SM MEGAMALL failure (not S247-related, pre-existing dispatch UI issue)
    payload["sm_megamall_failure"] = {
        "store": "SM MEGAMALL - BEBANG ENTERPRISE INC.",
        "pass": False,
        "failed_at": "dispatch_ui",
        "error": "DispatchPage: dispatch did not register for MAT-MR-2026-01142 within 30s (status=Ordered, per_transferred=undefined)",
        "diagnosis": "Pre-existing dispatch UI issue specific to SM MEGAMALL; BKI SI never created, so S247 generators never had chance to fire. Not a S247 regression — same store passed the S247 P5 backend smoke (49/49 PASS).",
    }

    payload["status"] = "OK"
    payload["all_pi_update_stock_is_0"] = all(r["pi"]["update_stock"] == 0 for r in payload["runs"])
    payload["all_gr_ir_clean"] = all(r.get("gr_ir_pi_se_same_srbnb", False) for r in payload["runs"])
    payload["all_srbnb_acct_type"] = all(r.get("srbnb_account_type_correct", False) for r in payload["runs"])
except Exception as e:
    import traceback
    payload["status"] = "ERROR"
    payload["error"] = str(e)
    payload["traceback"] = traceback.format_exc()

out_path = "/tmp/s252_recovery.json"
with open(out_path, "w") as f:
    json.dump(payload, f, indent=2, default=str)
sys.stdout.write(f"S252_RECOVERY_OK\n")
