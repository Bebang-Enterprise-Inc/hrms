"""verify_phase4.py — S255 Phase 4 gate."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def fail(m): print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)
def ok(m): print(f"[OK]   {m}")


def main():
    log_path = ROOT / "output" / "s255" / "dedup_cleanup_log.json"
    if not log_path.exists(): fail(f"missing {log_path}")
    log = json.loads(log_path.read_text(encoding="utf-8"))

    if log["normalization_fn"] != "invNoVariants_": fail(f"normalization_fn={log['normalization_fn']!r}, expected 'invNoVariants_'")
    ok(f"normalization_fn = invNoVariants_")

    soa = log["tabs"].get("Suppliers SOA", {})
    if soa.get("rows_deleted", 0) < 12: fail(f"SOA rows_deleted = {soa.get('rows_deleted')}, < 12 plan target")
    ok(f"Suppliers SOA: {soa['rows_deleted']} dupes deleted (>= 12)")

    if soa.get("rows_still_to_delete", -1) != 0: fail(f"SOA still has {soa.get('rows_still_to_delete')} deletable dupes after pass")
    ok(f"Suppliers SOA: 0 deletable Denise-PP dupes remain")

    pp = log["tabs"].get("Payment Plan", {})
    if pp.get("rows_still_to_delete", -1) != 0: fail(f"PP still has {pp.get('rows_still_to_delete')} deletable dupes")
    ok(f"Payment Plan: 0 deletable Denise-PP dupes remain")

    print("\n[PASS] Phase 4 gate — dedup cleanup successful")


if __name__ == "__main__":
    main()
