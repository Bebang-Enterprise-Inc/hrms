#!/usr/bin/env python3
"""Diag — force rebuild_tree then report BKI's lft ranges."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175" / "diagnostics"

PAYLOAD = r'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
out["pre_rebuild_bki_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt) FROM `tabAccount` WHERE company=%s", "Bebang Kitchen Inc.")[0]
out["pre_rebuild_tih_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt) FROM `tabAccount` WHERE company=%s", "Triple I Holdings")[0]

# Before rebuild, try to insert a dummy account
import traceback
try:
    # Find BKI's largest lft
    bki_max = frappe.db.sql("SELECT MAX(rgt) FROM `tabAccount` WHERE company=%s", "Bebang Kitchen Inc.")[0][0] or 0
    out["bki_max_rgt"] = bki_max
    # What other companies have accounts at lft > bki_max?
    out["above_bki_max"] = frappe.db.sql("""
        SELECT company, COUNT(*), MIN(lft), MAX(rgt)
        FROM `tabAccount` WHERE lft > %s GROUP BY company
    """, bki_max, as_list=True)
except Exception as e:
    out["_err"] = str(e)

# Now try rebuild
from frappe.utils.nestedset import rebuild_tree
try:
    rebuild_tree("Account", "parent_account")
    frappe.db.commit()
    out["rebuild_ok"] = True
except Exception as e:
    out["rebuild_ok"] = False
    out["rebuild_error"] = str(e)
    out["rebuild_tb"] = traceback.format_exc()

out["post_rebuild_bki_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt) FROM `tabAccount` WHERE company=%s", "Bebang Kitchen Inc.")[0]
out["post_rebuild_tih_range"] = frappe.db.sql("SELECT MIN(lft), MAX(rgt) FROM `tabAccount` WHERE company=%s", "Triple I Holdings")[0]

# Try to simulate the validator: pick a fresh lft for a new BKI root
bki_max_rgt_post = out["post_rebuild_bki_range"][1] or 0
# max rgt globally
global_max = frappe.db.sql("SELECT MAX(rgt) FROM `tabAccount`")[0][0] or 0
out["global_max_rgt"] = global_max
# Simulated new lft would be global_max + 1
sim_lft = global_max + 1
sim_rgt = global_max + 2
# Who's an ancestor (lft < sim AND rgt > sim) in a different company?
containing = frappe.db.sql("""
    SELECT name, company, lft, rgt FROM `tabAccount`
    WHERE lft < %s AND rgt > %s AND company != %s
    ORDER BY lft DESC LIMIT 5
""", (sim_lft, sim_rgt, "Bebang Kitchen Inc."), as_dict=True)
out["sim_insert_containers"] = containing

# Does rebuild actually do what we think?
# Check if BKI accounts got non-zero lft/rgt after rebuild
zeros = frappe.db.sql("SELECT COUNT(*) FROM `tabAccount` WHERE company=%s AND lft=0", "Bebang Kitchen Inc.")[0][0]
out["bki_zero_lft_count"] = zeros

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
'''

payload_path = OUT / "_diag_rebuild_payload.py"
payload_path.write_text(PAYLOAD, encoding="utf-8")
stdout, stderr, status = run_on_frappe(payload_path, tag="diag_rebuild")
if status != "Success":
    print(stderr); sys.exit(1)
raw = stdout.split("DIAG_START", 1)[1].split("DIAG_END", 1)[0].strip()
data = json.loads(raw)
(OUT / "rebuild_test.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
print(json.dumps(data, indent=2, default=str))
