"""Check Salary Slip volume in April 2026 before deciding on L3-6/L3-7."""
from __future__ import annotations
import sys, json
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json

SCRIPT = r"""
import json
first_half = frappe.db.sql(
    "SELECT name, employee, start_date, end_date, docstatus, gross_pay, company "
    "FROM `tabSalary Slip` "
    "WHERE start_date <= '2026-04-15' AND end_date >= '2026-04-01' "
    "ORDER BY docstatus DESC, employee LIMIT 10",
    as_dict=True,
)
counts_first = frappe.db.sql(
    "SELECT docstatus, COUNT(*) AS n FROM `tabSalary Slip` "
    "WHERE start_date <= '2026-04-15' AND end_date >= '2026-04-01' "
    "GROUP BY docstatus",
    as_dict=True,
)
counts_second = frappe.db.sql(
    "SELECT docstatus, COUNT(*) AS n FROM `tabSalary Slip` "
    "WHERE start_date <= '2026-04-30' AND end_date >= '2026-04-16' "
    "GROUP BY docstatus",
    as_dict=True,
)
print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "first_half_counts_by_docstatus": counts_first,
    "second_half_counts_by_docstatus": counts_second,
    "sample_first_half": first_half,
}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main():
    rc, out, err = run_via_ssm(SCRIPT, timeout_seconds=120)
    if rc != 0:
        print(err[:1500]); return rc
    res = extract_result_json(out)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
