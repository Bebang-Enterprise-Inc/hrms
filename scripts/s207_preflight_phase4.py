"""S207 P4-T1 — Phase 4 preflight: abort if any Draft Salary Slip has Monthly frequency.

Frappe refuses to validate Draft slips whose Structure later changes frequency.
Abort BEFORE Phase 4 Structures UPDATE if any such Draft exists so payroll team
can clean up first.
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
draft_slips = frappe.db.sql(
    "SELECT name, employee, employee_name, payroll_frequency, start_date, end_date, docstatus "
    "FROM `tabSalary Slip` WHERE docstatus=0 AND payroll_frequency='Monthly' "
    "ORDER BY start_date DESC LIMIT 50",
    as_dict=True,
)
print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "draft_monthly_slip_count": len(draft_slips),
    "blocking_slips": [
        {"name": d["name"], "employee": d["employee"], "payroll_frequency": d["payroll_frequency"]}
        for d in draft_slips
    ],
}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "preflight" / "phase4_draft_check.json"
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
    if result["draft_monthly_slip_count"] > 0:
        print(f"[STOP] {result['draft_monthly_slip_count']} Draft Salary Slips with Monthly frequency exist.")
        print("  Phase 4 cannot proceed — coordinate with payroll team to submit or delete these drafts first.")
        for s in result["blocking_slips"][:10]:
            print(f"    {s['name']} (employee={s['employee']})")
        return 2  # distinct exit code for payroll-coordination stop
    print("[OK] Zero Draft Monthly slips. Phase 4 may proceed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
