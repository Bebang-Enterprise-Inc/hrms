#!/usr/bin/env python3
"""S233 v3 A14: conditionally backfill BFI2 entity_category.

Reads output/s233/verification/bfi2_state_pre.json. If
entity_category not in {Head Office, Holding Company, Franchisor, Commissary},
sets it to "Holding Company" via frappe.db.set_value (no full save — avoids
re-firing auto_provision_company hook).

Idempotent — re-running after backfill is a no-op.
"""
from __future__ import annotations
import json, pathlib, sys

PREAMBLE = """\
import os, sys, json, traceback
for d in (
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
):
    os.makedirs(d, exist_ok=True)
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

def _emit(payload):
    print("---S233-BACKFILL-START---")
    print(json.dumps(payload, indent=2, default=str))
    print("---S233-BACKFILL-END---")
"""

BACKFILL = PREAMBLE + """
ALLOWED = {"Head Office", "Holding Company", "Franchisor", "Commissary"}
RECOMMENDED = "Holding Company"
result = {}
try:
    pre = frappe.db.get_value(
        "Company", "BEBANG FT INC.",
        ["entity_category", "is_group"], as_dict=True,
    )
    result["pre"] = pre
    if not pre:
        result["error"] = "BFI2 not found"
    elif pre.get("entity_category") in ALLOWED:
        result["action"] = "noop"
        result["reason"] = f"entity_category already {pre['entity_category']!r}, in allowed set"
    else:
        # Direct SQL set_value — does NOT re-fire auto_provision_company hook
        # (avoids the S231 chart-of-accounts importer trap if doc_save was used)
        frappe.db.set_value("Company", "BEBANG FT INC.", "entity_category", RECOMMENDED)
        frappe.db.commit()
        result["action"] = "backfilled"
        result["from"] = pre.get("entity_category")
        result["to"] = RECOMMENDED
    # Re-probe for evidence
    post = frappe.db.get_value(
        "Company", "BEBANG FT INC.",
        ["entity_category", "is_group"], as_dict=True,
    )
    result["post"] = post
    result["entity_category_in_allowed_set"] = post.get("entity_category") in ALLOWED
    result["is_group_correct"] = post.get("is_group") == 1
except Exception as e:
    result["error"] = str(e)
    result["traceback"] = traceback.format_exc()

_emit(result)
frappe.destroy()
"""


def main() -> int:
    REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        from s231_ssm_helper import run_in_container
    except ImportError:
        print("ERROR: s231_ssm_helper not found; expected at scripts/s231_ssm_helper.py", file=sys.stderr)
        return 1

    stdout = run_in_container(BACKFILL, timeout=120)
    if "---S233-BACKFILL-START---" not in stdout:
        print("ERROR: backfill output missing markers:\n" + stdout[-2000:], file=sys.stderr)
        return 2
    s = stdout.split("---S233-BACKFILL-START---", 1)[1].split("---S233-BACKFILL-END---", 1)[0].strip()
    data = json.loads(s)
    out_path = REPO_ROOT / "output" / "s233" / "verification" / "bfi2_state_after.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, default=str))
    print(json.dumps(data, indent=2, default=str))
    if data.get("error"):
        return 1
    if not (data.get("entity_category_in_allowed_set") and data.get("is_group_correct")):
        print("FAIL: post-state still not canonical", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
