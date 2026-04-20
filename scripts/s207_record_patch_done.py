"""Record s207_labor_allocation_log_bimonthly in tabPatch Log so future migrates skip it.

Workaround for the deploy-script bug: `bench migrate` uses `hrms.bebang.ph` but
the real site is `hq.bebang.ph`, so migrate failed and the patch never ran.
The schema repair in s207_check_migration_errors.py did the ALTERs manually;
this script tells Frappe the patch is done so nothing retries it.
"""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

SCRIPT = r"""
import json
patch_name = "hrms.patches.v16_0.s207_labor_allocation_log_bimonthly"
existing = frappe.db.get_value("Patch Log", {"patch": patch_name}, "name")
action = None
if existing:
    action = "existed"
else:
    doc = frappe.get_doc({"doctype": "Patch Log", "patch": patch_name})
    doc.insert(ignore_permissions=True)
    action = f"inserted as {doc.name}"

frappe.db.commit()
print("===RESULT_JSON_BEGIN===")
print(json.dumps({"patch": patch_name, "action": action}))
print("===RESULT_JSON_END===")
"""


def main():
    rc, out, err = run_via_ssm(SCRIPT, timeout_seconds=90)
    if rc != 0:
        print(f"[ERR] {rc}\n{err[:1500]}")
        return rc
    res = extract_result_json(out)
    print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
