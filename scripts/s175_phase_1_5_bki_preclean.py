#!/usr/bin/env python3
"""S175 Phase 1.5 — BKI pre-template cleanup (child-first deletion).

Per 03_CURRENT_STATE_SNAPSHOT.md Section 3, deletes 19 BKI accounts in the
correct order so the Phase 2 master template can install without collisions.

Child-first order:
- Batch A (leaves): 4000001, 4000002, 4000101, 4000200, 4000201..4000207, 4000301..4000306
- Batch B (parents): 4000100 (after 4000101), 4000300 (after 4000301..4000306)

HB-2: Re-verify 0 GL entries per account before deleting. Stop on any nonzero.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s175_ssm_runner import run_on_frappe  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output" / "s175"

PAYLOAD = r'''
#!/usr/bin/env python3
import os, json, sys, traceback
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

COMPANY = "Bebang Kitchen Inc."
# Child-first — leaves before parents
BATCH_A = ["4000001","4000002","4000101","4000200","4000201","4000202",
           "4000203","4000204","4000205","4000206","4000207",
           "4000301","4000302","4000303","4000304","4000305","4000306"]
# Parents go last
BATCH_B = ["4000100", "4000300"]

result = {"company": COMPANY, "deleted": [], "skipped_absent": [], "hb_blocked": [], "errors": []}

# Capture pre-delete snapshot
pre = frappe.db.sql("""
    SELECT name, account_number, account_name, is_group, root_type, parent_account
    FROM `tabAccount`
    WHERE company=%s AND account_number IN ({})
""".format(",".join(["%s"] * (len(BATCH_A) + len(BATCH_B)))),
    [COMPANY] + BATCH_A + BATCH_B, as_dict=True)
result["pre_snapshot"] = pre

def delete_one(num):
    acct = frappe.db.get_value(
        "Account",
        {"company": COMPANY, "account_number": num},
        "name",
    )
    if not acct:
        result["skipped_absent"].append(num)
        return
    gl = frappe.db.sql("SELECT COUNT(*) FROM `tabGL Entry` WHERE account=%s", acct)[0][0]
    if gl != 0:
        result["hb_blocked"].append({"num": num, "name": acct, "gl_entries": gl})
        raise RuntimeError(f"HB-2: {acct} has {gl} GL entries")
    # check children
    kids = frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE parent_account=%s", acct
    )
    if kids:
        result["hb_blocked"].append({"num": num, "name": acct, "children": [k[0] for k in kids]})
        raise RuntimeError(f"HB-7: {acct} still has children: {[k[0] for k in kids]}")
    frappe.delete_doc("Account", acct, force=True, ignore_permissions=True)
    result["deleted"].append({"num": num, "name": acct})

try:
    for n in BATCH_A:
        delete_one(n)
    for n in BATCH_B:
        delete_one(n)
    frappe.db.commit()
    # Rebuild nested set after bulk deletes
    from frappe.utils.nestedset import rebuild_tree
    rebuild_tree("Account", "parent_account")
    frappe.db.commit()
except Exception as e:
    result["errors"].append(str(e))
    result["traceback"] = traceback.format_exc()

# Post-state verification
result["post_4xxx"] = frappe.db.sql("""
    SELECT account_number, account_name, is_group, root_type, parent_account
    FROM `tabAccount`
    WHERE company=%s AND account_number LIKE '4%%'
    ORDER BY account_number
""", COMPANY, as_dict=True)

print("S175_PHASE15_JSON_START")
print(json.dumps(result, default=str))
print("S175_PHASE15_JSON_END")

frappe.destroy()
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload_path = OUT / "_phase15_payload.py"
    payload_path.write_text(PAYLOAD, encoding="utf-8")

    stdout, stderr, status = run_on_frappe(payload_path, tag="phase15_bki_preclean", timeout_seconds=900)
    if status != "Success":
        print(f"SSM status={status}")
        print(stderr[-2000:])
        sys.exit(1)

    raw = stdout.split("S175_PHASE15_JSON_START", 1)[1].split("S175_PHASE15_JSON_END", 1)[0].strip()
    result = json.loads(raw)

    (OUT / "phase1_5_bki_verification.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    if result.get("errors"):
        print("PHASE15 ERRORS:")
        for e in result["errors"]:
            print("  " + e)
        if result.get("hb_blocked"):
            print("HB BLOCKED:", json.dumps(result["hb_blocked"], indent=2))
        sys.exit(2)

    print("PHASE15 OK")
    print(f"  deleted: {len(result['deleted'])}")
    print(f"  skipped_absent: {len(result['skipped_absent'])} {result['skipped_absent']}")
    print(f"  post 4xxx remaining on BKI: {len(result['post_4xxx'])}")


if __name__ == "__main__":
    main()
