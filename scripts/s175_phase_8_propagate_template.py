#!/usr/bin/env python3
"""S175 Phase 8 — Propagate MASTER_SALES_TEMPLATE to the remaining 37 companies.

Already done in Phase 2: BKI, BEI, BFC.
Remaining: JV, Managed Franchise, Triple I Holdings, DMD Holdings, + 33 store corps.

For companies with parent_company=TIH, use ignore_root_company_validation.
For BFC and other standalone companies, direct insert works.

Some companies (JV, MF, TIH) have corrupted 4000000 SALES (wrong root_type or
self-parent). Apply the same corruption fixups as Phase 2 before templating.

This script is idempotent — ensure_account matches existing and only creates
missing rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe  # noqa: E402
from s175_master_coa_template import MASTER_SALES_TEMPLATE  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175"

TEMPLATE_JSON = json.dumps(MASTER_SALES_TEMPLATE)

PAYLOAD = r'''
#!/usr/bin/env python3
import os, json, sys, traceback
for d in ["/home/frappe/logs","/home/frappe/frappe-bench/logs","/home/frappe/frappe-bench/hq.bebang.ph/logs","/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")
frappe.local.flags.ignore_root_company_validation = True

TEMPLATE = json.loads(__TEMPLATE_JSON__)
SKIP = {"Bebang Enterprise Inc.", "Bebang Kitchen Inc.", "BEBANG FRANCHISE CORP."}

# Get all companies
all_companies = frappe.get_all("Company", pluck="name")
targets = [c for c in all_companies if c not in SKIP]

results = {"targets": targets, "per_company": {}}

def ensure_account(company, number, name, parent_number, is_group, root_type, account_type, rep):
    if parent_number is None:
        parent_name = None
    else:
        parent_name = frappe.db.get_value(
            "Account", {"company": company, "account_number": parent_number}, "name"
        )
        if not parent_name:
            raise RuntimeError(f"Parent {parent_number} not found on {company}")

    existing = frappe.db.sql(
        "SELECT name, account_name, is_group, root_type, parent_account "
        "FROM `tabAccount` WHERE company=%s AND account_number=%s",
        (company, number), as_dict=True,
    )

    if existing:
        ex = existing[0]
        if int(ex["is_group"]) != int(is_group):
            # For the is_group=1 template rows on companies that have them as posting:
            # convert via SQL if 0 GL entries
            gl = frappe.db.sql("SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s", ex["name"])[0][0]
            if gl == 0:
                frappe.db.sql("UPDATE `tabAccount` SET is_group=%s WHERE name=%s", (is_group, ex["name"]))
                rep["is_group_fixed"].append(number)
            else:
                raise RuntimeError(f"HB-5: {ex['name']} is_group={ex['is_group']}, expected {is_group}, has {gl} GL entries")
        if ex["root_type"] != root_type:
            frappe.db.sql("UPDATE `tabAccount` SET root_type=%s WHERE name=%s", (root_type, ex["name"]))
            rep["root_type_fixed"].append(number)
        if ex["parent_account"] != parent_name:
            # Check self-cycle
            if ex["parent_account"] == ex["name"]:
                frappe.db.sql("UPDATE `tabAccount` SET parent_account=%s WHERE name=%s", (parent_name, ex["name"]))
                rep["reparented"].append(number)
            else:
                frappe.db.sql("UPDATE `tabAccount` SET parent_account=%s WHERE name=%s", (parent_name, ex["name"]))
                rep["reparented"].append(number)
        if account_type and not is_group:
            cur = frappe.db.get_value("Account", ex["name"], "account_type")
            if cur != account_type:
                frappe.db.sql("UPDATE `tabAccount` SET account_type=%s WHERE name=%s", (account_type, ex["name"]))
        if ex["account_name"] != name:
            frappe.db.sql("UPDATE `tabAccount` SET account_name=%s WHERE name=%s", (name, ex["name"]))
            rep["name_fixed"].append(number)
        rep["matched"].append(number)
        return ex["name"]

    acct = frappe.new_doc("Account")
    acct.company = company
    acct.account_number = number
    acct.account_name = name
    acct.parent_account = parent_name
    acct.is_group = is_group
    acct.root_type = root_type
    if account_type:
        acct.account_type = account_type
    acct.flags.ignore_root_company_validation = True
    acct.flags.ignore_mandatory = True
    acct.insert(ignore_permissions=True, ignore_mandatory=True)
    rep["created"].append(number)
    return acct.name

for company in targets:
    rep = {"created": [], "matched": [], "reparented": [], "root_type_fixed": [],
           "is_group_fixed": [], "name_fixed": [], "errors": []}

    # Pre-fixup: if 4000000 SALES exists on this company with self-parent, clear it
    root_4000 = frappe.db.sql("""
        SELECT name, parent_account, is_group, root_type FROM `tabAccount`
        WHERE company=%s AND account_number='4000000'
    """, company, as_dict=True)
    if root_4000:
        r = root_4000[0]
        if r["parent_account"] == r["name"]:
            frappe.db.sql("UPDATE `tabAccount` SET parent_account=NULL WHERE name=%s", r["name"])
            rep["pre_fixup"] = "cleared self-parent"
        # Also clear parent if it points backwards (e.g., SALES under FRANCHISE INCOME as on JV)
        # We'll let ensure_account reparent to NULL (root_number is None for 4000000)

    try:
        for number, name, parent_number, is_group, root_type, account_type in TEMPLATE:
            try:
                ensure_account(company, number, name, parent_number, is_group, root_type, account_type, rep)
                frappe.db.commit()
            except Exception as inner:
                rep["errors"].append({"number": number, "error": str(inner)[:200]})
                frappe.db.rollback()
    except Exception as e:
        rep["fatal"] = str(e)
        rep["traceback"] = traceback.format_exc()

    results["per_company"][company] = {
        "created": len(rep["created"]),
        "matched": len(rep["matched"]),
        "reparented": len(rep["reparented"]),
        "root_type_fixed": len(rep["root_type_fixed"]),
        "is_group_fixed": len(rep["is_group_fixed"]),
        "name_fixed": len(rep["name_fixed"]),
        "errors_count": len(rep["errors"]),
        "first_error": rep["errors"][0] if rep["errors"] else None,
        "pre_fixup": rep.get("pre_fixup"),
    }

# Final: how many companies have all 27 template accounts now?
results["final_counts"] = {}
for company in targets:
    count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAccount`
        WHERE company=%s AND account_number IN ('4000000','4000100','4000110','4000120','4000121','4000122','4000123',
            '4000200','4000210','4000220','4000221','4000222','4000230','4000231','4000232','4000233','4000234','4000235',
            '4000900','4000901','4000902','4000903','4000904','4000905','4000906','4000907','4000908')
    """, company)[0][0]
    results["final_counts"][company] = count

print("S175_P8_JSON_START")
print(json.dumps(results, default=str))
print("S175_P8_JSON_END")
frappe.destroy()
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload = PAYLOAD.replace("__TEMPLATE_JSON__", json.dumps(TEMPLATE_JSON))
    payload_path = OUT / "_phase8_payload.py"
    payload_path.write_text(payload, encoding="utf-8")

    stdout, stderr, status = run_on_frappe(payload_path, tag="phase8_propagate", timeout_seconds=1800)
    if status != "Success":
        print(stderr[-3000:]); sys.exit(1)

    raw = stdout.split("S175_P8_JSON_START", 1)[1].split("S175_P8_JSON_END", 1)[0].strip()
    result = json.loads(raw)

    (OUT / "phase8_per_company_verification.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print(f"Target companies: {len(result['targets'])}")
    print()
    print("Per-company results:")
    incomplete = []
    for comp in result["targets"]:
        r = result["per_company"][comp]
        count = result["final_counts"][comp]
        marker = "OK " if count == 27 else "!! "
        if count != 27:
            incomplete.append((comp, count))
        print(f"  {marker}{comp}: created={r['created']} matched={r['matched']} "
              f"errors={r['errors_count']} post_template_count={count}/27")

    print()
    print(f"Companies with complete template: {sum(1 for c in result['targets'] if result['final_counts'][c]==27)}/{len(result['targets'])}")

    if incomplete:
        print(f"\nIncomplete ({len(incomplete)}):")
        for comp, count in incomplete[:10]:
            r = result["per_company"][comp]
            print(f"  {comp}: {count}/27, first_error={r.get('first_error')}")
        sys.exit(2)
    print("PHASE8 OK")


if __name__ == "__main__":
    main()
