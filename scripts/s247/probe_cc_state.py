#!/usr/bin/env python3
"""Probe Cost Center state for the 4 BEI-Enterprise stores."""
from __future__ import annotations

import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json, sys
import frappe  # type: ignore

TARGETS = [
    "ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC.",
    "SM MANILA - BEBANG ENTERPRISE INC.",
    "SM MEGAMALL - BEBANG ENTERPRISE INC.",
    "SM SOUTHMALL - BEBANG ENTERPRISE INC.",
]

payload = {"stores": []}
try:
    frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
    frappe.connect()
    frappe.set_user("Administrator")

    for c in TARGETS:
        r = {"company": c}
        abbr = frappe.db.get_value("Company", c, "abbr")
        r["abbr"] = abbr
        # All CCs for this Company
        ccs = frappe.db.sql(
            """SELECT name, cost_center_name, is_group, parent_cost_center, lft, rgt
               FROM `tabCost Center` WHERE company = %s ORDER BY lft""",
            c, as_dict=True,
        )
        r["cost_center_count"] = len(ccs)
        r["cost_centers"] = ccs
        # Comparison: a working store (ARANETA) CC tree
        payload["stores"].append(r)

    # Reference: ARANETA's CC tree for comparison
    aranetac_ccs = frappe.db.sql(
        """SELECT name, cost_center_name, is_group, parent_cost_center, lft, rgt
           FROM `tabCost Center` WHERE company = %s ORDER BY lft""",
        "ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC", as_dict=True,
    )
    payload["reference_aranetac_cc_tree"] = aranetac_ccs

except Exception as e:
    import traceback
    payload["status"] = "ERROR"
    payload["fatal_error"] = str(e)
    payload["traceback"] = traceback.format_exc()

with open("/tmp/s247_cc_probe.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, default=str)
sys.stdout.write("S247_CC_PROBE_OK\n")
