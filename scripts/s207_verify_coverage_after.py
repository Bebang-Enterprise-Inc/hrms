"""S207 P6-T4 — Post-seed coverage verification.

Re-runs the P0-T1 coverage algorithm and confirms every in-scope Company now
has all 4 S206 records (Due From account + Due To account + internal Customer
+ internal Supplier).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

SCRIPT = r"""
import json

companies = frappe.db.sql(
    "SELECT name, abbr FROM `tabCompany` "
    "WHERE entity_category='Store' AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant')) "
    "ORDER BY name",
    as_dict=True,
)

def complete_for(co):
    has_due_from = bool(frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE company=%s AND is_group=0 "
        "AND name LIKE '1104200 - DUE FROM GROUP ENTITIES%%' LIMIT 1",
        (co["name"],),
    ))
    has_due_to = bool(frappe.db.sql(
        "SELECT name FROM `tabAccount` WHERE company=%s AND is_group=0 "
        "AND name LIKE '2104200 - DUE TO GROUP ENTITIES%%' LIMIT 1",
        (co["name"],),
    ))
    has_customer = frappe.db.exists(
        "Customer",
        {"represents_company": co["name"], "is_internal_customer": 1},
    )
    has_supplier = frappe.db.exists(
        "Supplier",
        {"represents_company": co["name"], "is_internal_supplier": 1},
    )
    return {
        "complete": all([has_due_from, has_due_to, has_customer, has_supplier]),
        "has_due_from": bool(has_due_from),
        "has_due_to": bool(has_due_to),
        "has_customer": bool(has_customer),
        "has_supplier": bool(has_supplier),
    }

details = []
complete_count = 0
for co in companies:
    status = complete_for(co)
    if status["complete"]:
        complete_count += 1
    else:
        details.append({"company": co["name"], "abbr": co["abbr"], **status})

print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "total_stores": len(companies),
    "complete_count": complete_count,
    "incomplete_count": len(companies) - complete_count,
    "incomplete_details": details,
}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "evidence" / "coverage_after.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, stdout, stderr = run_via_ssm(SCRIPT, timeout_seconds=300)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Unparseable stdout:\n{stdout[:1500]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[OK] Coverage: {result['complete_count']}/{result['total_stores']} complete")
    if result["incomplete_count"] > 0:
        print(f"[FAIL] {result['incomplete_count']} incomplete:")
        for d in result["incomplete_details"]:
            print(f"  {d['company']}: due_from={d['has_due_from']}, due_to={d['has_due_to']}, customer={d['has_customer']}, supplier={d['has_supplier']}")
        return 1
    print(f"[OK] All {result['total_stores']} stores have full S206 COA coverage. Phase 6 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
