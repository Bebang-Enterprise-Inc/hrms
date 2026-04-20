"""S207 — Restore Salary Structures from the P4-T2 backup.

Usage:
    python scripts/s207_restore_salary_structures.py [--backup <path>]

Reads ``output/s207/backups/salary_structures_before.json`` (or --backup path)
and restores each Structure's ``payroll_frequency`` to the value recorded at
backup time. Safe to run multiple times (idempotent).

Manual invocation only — not part of the regular Phase 4 flow. Use this if the
Phase 4 bulk-edit introduces an unexpected failure and you need to roll back
before the S207 PR merges.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from s207_ssm_helper import run_via_ssm, extract_result_json


def build_restore_script(structures: list[dict]) -> str:
    # Serialize the restore payload inside the remote Python script so the
    # executing container doesn't need local file access to the backup JSON.
    payload = json.dumps([
        {"name": s["name"], "payroll_frequency": s["payroll_frequency"]}
        for s in structures
    ])
    return f"""
import json
restore = json.loads({json.dumps(payload)})
for row in restore:
    frappe.db.sql(
        "UPDATE `tabSalary Structure` SET payroll_frequency=%s WHERE name=%s",
        (row["payroll_frequency"], row["name"]),
    )
frappe.db.commit()  # nosemgrep: frappe-manual-commit -- restore batch commit
print("===RESULT_JSON_BEGIN===")
print(json.dumps({{"restored": len(restore)}}))
print("===RESULT_JSON_END===")
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--backup",
        default=str(REPO / "output" / "s207" / "backups" / "salary_structures_before.json"),
        help="Path to the Phase 4 backup JSON",
    )
    args = ap.parse_args()
    backup = Path(args.backup)
    if not backup.exists():
        print(f"[ERROR] Backup not found: {backup}")
        return 1
    data = json.loads(backup.read_text(encoding="utf-8"))
    structures = data.get("structures", [])
    if not structures:
        print("[ERROR] Backup contains zero Structures — nothing to restore")
        return 1
    script = build_restore_script(structures)
    rc, stdout, stderr = run_via_ssm(script, timeout_seconds=180)
    if rc != 0:
        print(f"[ERROR] SSM rc={rc}\n{stderr[:1500]}")
        return rc
    result = extract_result_json(stdout)
    print(f"[OK] Restored {result.get('restored', 0) if result else 'unknown'} Structures from {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
