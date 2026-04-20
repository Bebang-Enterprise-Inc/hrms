"""S207 P4-T3 — Bulk UPDATE every active Salary Structure from Monthly to Bimonthly.

Uses the /frappe-bulk-edits SSM pattern. Post-update verification queries
``SELECT DISTINCT payroll_frequency FROM tabSalary Structure WHERE is_active='Yes'``
and asserts the result is ``{'Bimonthly': N}`` only.

Writes evidence to ``output/s207/evidence/salary_structure_update_report.json``.
Idempotent — re-running is a no-op.
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
# Capture before state
before = frappe.db.sql(
    "SELECT payroll_frequency, COUNT(*) AS n FROM `tabSalary Structure` "
    "WHERE is_active='Yes' GROUP BY payroll_frequency",
    as_dict=True,
)
before_dict = {r["payroll_frequency"]: int(r["n"]) for r in before}

# UPDATE
affected = frappe.db.sql(
    "UPDATE `tabSalary Structure` SET payroll_frequency='Bimonthly' "
    "WHERE is_active='Yes' AND payroll_frequency='Monthly'"
)
frappe.db.commit()  # nosemgrep: frappe-manual-commit -- intentional: batch data migration must persist

# After state
after = frappe.db.sql(
    "SELECT payroll_frequency, COUNT(*) AS n FROM `tabSalary Structure` "
    "WHERE is_active='Yes' GROUP BY payroll_frequency",
    as_dict=True,
)
after_dict = {r["payroll_frequency"]: int(r["n"]) for r in after}

# List per-structure after state for evidence
per_structure = frappe.db.sql(
    "SELECT name, payroll_frequency, company FROM `tabSalary Structure` "
    "WHERE is_active='Yes' ORDER BY name",
    as_dict=True,
)

print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "before": before_dict,
    "after": after_dict,
    "per_structure": per_structure,
    "intended_target_frequency": "Bimonthly",
}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "evidence" / "salary_structure_update_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, stdout, stderr = run_via_ssm(SCRIPT, timeout_seconds=180)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Unparseable stdout:\n{stdout[:1500]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    after = result["after"]
    # Target: every active Structure is Bimonthly (zero Monthly)
    if set(after.keys()) != {"Bimonthly"} or after.get("Monthly", 0) != 0:
        print(f"[FAIL] After update, distinct frequencies = {after}. Expected only Bimonthly.")
        return 1
    print(f"[OK] {after['Bimonthly']} active Salary Structures now Bimonthly. Before={result['before']}")
    for s in result["per_structure"]:
        print(f"  {s['name']}: {s['payroll_frequency']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
