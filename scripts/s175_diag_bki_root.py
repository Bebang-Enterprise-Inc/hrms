#!/usr/bin/env python3
"""Diagnostic — understand BKI's root account structure."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175" / "diagnostics"
OUT.mkdir(parents=True, exist_ok=True)

PAYLOAD = r'''
import os, json
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

out = {}
# For BKI, BEI, BFC, TIH, MF — show lft/rgt of top 10 accounts by lft
for c in ["Bebang Kitchen Inc.","Bebang Enterprise Inc.","BEBANG FRANCHISE CORP.","Triple I Holdings","Managed Franchise"]:
    rows = frappe.db.sql("""
        SELECT name, account_name, is_group, root_type, parent_account, lft, rgt
        FROM `tabAccount` WHERE company=%s
        ORDER BY lft LIMIT 8
    """, c, as_dict=True)
    out[c] = {"first_8_by_lft": rows}
    # min and max lft/rgt
    mm = frappe.db.sql("""
        SELECT MIN(lft), MAX(rgt), COUNT(*) FROM `tabAccount` WHERE company=%s
    """, c)[0]
    out[c]["min_lft"] = mm[0]
    out[c]["max_rgt"] = mm[1]
    out[c]["count"] = mm[2]

# BKI's 4000000 ancestors via recursive parent walk
a = frappe.db.get_value("Account", {"company":"Bebang Kitchen Inc.","account_number":"4000000"}, "name")
ancestors = []
cur = a
for _ in range(20):
    if not cur: break
    row = frappe.db.sql("SELECT name, parent_account, lft, rgt, root_type, is_group FROM `tabAccount` WHERE name=%s", cur, as_dict=True)
    if not row: break
    ancestors.append(row[0])
    cur = row[0]["parent_account"]
out["bki_4000000_ancestors"] = ancestors

# Check multi-company ancestor chain via lft/rgt
if a:
    bki_4000000_lft = frappe.db.sql("SELECT lft, rgt FROM `tabAccount` WHERE name=%s", a, as_dict=True)[0]
    # Find all accounts whose lft < this.lft AND rgt > this.rgt
    containing = frappe.db.sql("""
        SELECT name, company, account_name, is_group, lft, rgt
        FROM `tabAccount`
        WHERE lft < %s AND rgt > %s
        ORDER BY lft
    """, (bki_4000000_lft["lft"], bki_4000000_lft["rgt"]), as_dict=True)
    out["bki_4000000_containing_by_lftrgt"] = containing

print("DIAG_START")
print(json.dumps(out, default=str))
print("DIAG_END")
frappe.destroy()
'''

payload_path = OUT / "_diag_bki_root_payload.py"
payload_path.write_text(PAYLOAD, encoding="utf-8")
stdout, stderr, status = run_on_frappe(payload_path, tag="diag_bki_root")
if status != "Success":
    print(stderr); sys.exit(1)
raw = stdout.split("DIAG_START", 1)[1].split("DIAG_END", 1)[0].strip()
data = json.loads(raw)
(OUT / "bki_root.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
for c, d in data.items():
    if c.startswith("bki_4000000"):
        continue
    print(f"\n=== {c} (count={d['count']} min_lft={d['min_lft']} max_rgt={d['max_rgt']}) ===")
    for r in d["first_8_by_lft"]:
        print(f"  lft={r['lft']} rgt={r['rgt']} {r['name']!r} parent={r['parent_account']!r} group={r['is_group']}")

print("\n=== BKI 4000000 ancestors ===")
for a in data["bki_4000000_ancestors"]:
    print(f"  {a}")

print("\n=== BKI 4000000 containing (by lft/rgt) ===")
for c in data.get("bki_4000000_containing_by_lftrgt", []):
    print(f"  company={c['company']} lft={c['lft']} rgt={c['rgt']} {c['name']!r}")
