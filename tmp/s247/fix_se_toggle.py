#!/usr/bin/env python3
"""Set enable_bki_store_stock_entry_generator=1 on BEI Settings.

The doctype JSON default=1 doesn't auto-apply to existing Single rows.
"""
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
    settings = frappe.get_single("BEI Settings")
    payload["before"] = {
        "pi_toggle": getattr(settings, "enable_bki_store_pi_generator", None),
        "se_toggle": getattr(settings, "enable_bki_store_stock_entry_generator", None),
    }
    settings.enable_bki_store_stock_entry_generator = 1
    if getattr(settings, "enable_bki_store_pi_generator", None) != 1:
        settings.enable_bki_store_pi_generator = 1
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    payload["after"] = {
        "pi_toggle": settings.enable_bki_store_pi_generator,
        "se_toggle": settings.enable_bki_store_stock_entry_generator,
    }
    payload["status"] = "OK"
except Exception as e:
    import traceback
    payload["status"] = "ERROR"
    payload["error"] = str(e)
    payload["traceback"] = traceback.format_exc()
with open("/tmp/s247_toggle_fix.json", "w") as f:
    json.dump(payload, f, indent=2, default=str)
sys.stdout.write("DONE\n")
