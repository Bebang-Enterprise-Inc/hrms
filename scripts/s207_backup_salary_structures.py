"""S207 P4-T2 — Pre-touch backup of all active Salary Structures.

Writes ``output/s207/backups/salary_structures_before.json`` so the restore
script can put the frequency back if Phase 4 fails.
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
rows = frappe.db.sql(
    "SELECT name, payroll_frequency, company, is_active, modified "
    "FROM `tabSalary Structure` WHERE is_active='Yes' ORDER BY name",
    as_dict=True,
)
print("===RESULT_JSON_BEGIN===")
print(json.dumps({"structures": rows}, indent=2, default=str))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    out = REPO / "output" / "s207" / "backups" / "salary_structures_before.json"
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
    print(f"[OK] Backed up {len(result['structures'])} active Salary Structures to {out}")
    for s in result["structures"]:
        print(f"  {s['name']}: {s['payroll_frequency']} (company={s['company']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
