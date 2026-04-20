"""S207 P0-T2 — Verify Frappe accepts Bimonthly as a payroll_frequency value.

Confirms the Select enum includes 'Bimonthly' BEFORE Phase 4 tries to UPDATE
Structures. If the live site doesn't accept 'Bimonthly', Phase 4 must STOP.
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
meta = frappe.get_meta("Salary Structure")
field = meta.get_field("payroll_frequency")
options = []
if field and field.options:
    options = [o.strip() for o in field.options.splitlines() if o.strip()]

# Live distinct values currently in use
distinct = [r[0] for r in frappe.db.sql(
    "SELECT DISTINCT payroll_frequency FROM `tabSalary Structure`"
)]

print("===RESULT_JSON_BEGIN===")
print(json.dumps({
    "payroll_frequency_enum_options": options,
    "bimonthly_accepted": "Bimonthly" in options,
    "distinct_values_in_use": distinct,
}, indent=2))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "preflight" / "frappe_bimonthly_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, stdout, stderr = run_via_ssm(SCRIPT, timeout_seconds=180)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    if not result:
        print(f"[ERROR] Could not parse RESULT_JSON:\n{stdout[:1500]}")
        return 1
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not result["bimonthly_accepted"]:
        print(f"[FAIL] 'Bimonthly' NOT in Frappe enum — options: {result['payroll_frequency_enum_options']}")
        return 1
    print(f"[OK] Bimonthly accepted. Current distinct values: {result['distinct_values_in_use']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
