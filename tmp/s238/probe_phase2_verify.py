#!/usr/bin/env python3
"""Phase 2 verification probe — check state of Supplier + Custom Fields."""
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)

import json
import sys
import frappe  # type: ignore

frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()

out = {
    "trade_supplier_exists": bool(frappe.db.exists("Supplier", "BEBANG KITCHEN INC. - Trade")),
    "existing_bki_suppliers": frappe.db.sql(
        """SELECT name, supplier_name, is_internal_supplier FROM `tabSupplier`
           WHERE UPPER(name) LIKE '%KITCHEN%' OR UPPER(supplier_name) LIKE '%KITCHEN%'""",
        as_dict=True,
    ),
    "si_ref_field_exists": bool(frappe.db.exists(
        "Custom Field", {"dt": "Purchase Invoice", "fieldname": "bki_si_reference"})),
    "toggle_field_exists": bool(frappe.db.exists(
        "Custom Field", {"dt": "BEI Settings", "fieldname": "enable_bki_store_pi_generator"})),
}

# Toggle value
settings = frappe.get_single("BEI Settings")
out["toggle_value"] = settings.get("enable_bki_store_pi_generator")

with open("/tmp/s238_p2_verify.json", "w") as f:
    json.dump(out, f, indent=2, default=str)
print("S238_P2_VERIFY_OK path=/tmp/s238_p2_verify.json")
