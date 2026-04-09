#!/usr/bin/env python3
"""Diag — check Company parent/child hierarchy for BEI group."""
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
# Show all companies with parent_company
out["companies_full"] = frappe.db.sql("""
    SELECT name, abbr, parent_company, is_group, lft, rgt
    FROM `tabCompany` ORDER BY lft
""", as_dict=True)

# For BKI specifically, what's its parent/ancestors?
out["bki_row"] = frappe.db.sql("SELECT * FROM `tabCompany` WHERE name='Bebang Kitchen Inc.'", as_dict=True)
out["bei_row"] = frappe.db.sql("SELECT * FROM `tabCompany` WHERE name='Bebang Enterprise Inc.'", as_dict=True)
out["bfc_row"] = frappe.db.sql("SELECT * FROM `tabCompany` WHERE name='BEBANG FRANCHISE CORP.'", as_dict=True)

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
'''
payload_path = OUT / "_diag_company_hier_payload.py"
payload_path.write_text(PAYLOAD, encoding="utf-8")
stdout, stderr, status = run_on_frappe(payload_path, tag="diag_company_hier")
if status != "Success":
    print(stderr); sys.exit(1)
raw = stdout.split("DIAG_START", 1)[1].split("DIAG_END", 1)[0].strip()
data = json.loads(raw)
(OUT / "company_hier.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

print("=== Companies (full tree) ===")
for c in data["companies_full"]:
    print(f"  lft={c['lft']} rgt={c['rgt']} group={c['is_group']} parent={c['parent_company']!r} {c['name']}")

print("\n=== BKI row ===")
for r in data["bki_row"]:
    for k in ["name", "abbr", "parent_company", "is_group", "lft", "rgt"]:
        print(f"  {k}: {r.get(k)}")

print("\n=== BEI row ===")
for r in data["bei_row"]:
    for k in ["name", "abbr", "parent_company", "is_group", "lft", "rgt"]:
        print(f"  {k}: {r.get(k)}")

print("\n=== BFC row ===")
for r in data["bfc_row"]:
    for k in ["name", "abbr", "parent_company", "is_group", "lft", "rgt"]:
        print(f"  {k}: {r.get(k)}")
