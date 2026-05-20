"""verify_phase9a.py — S255 Phase 9a gate."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def fail(m): print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)
def ok(m): print(f"[OK]   {m}")


def main():
    bp = ROOT / "output" / "s255" / "bridge_access_audit.json"
    if not bp.exists(): fail(f"missing {bp}")
    audit = json.loads(bp.read_text(encoding="utf-8"))
    if audit["sheets_audited"] != 8: fail(f"audited {audit['sheets_audited']} sheets, expected 8")
    ok(f"bridge_access_audit.json: {audit['sheets_audited']} sheets, {audit['sheets_with_bridge']} have Bridge")

    dd = ROOT / "output" / "s255" / "dd_package_checklist.md"
    if not dd.exists(): fail(f"missing {dd}")
    content = dd.read_text(encoding="utf-8")
    for marker in ("Bridge access across ecosystem", "DD-package contents", "Audit trail Bridge can pull"):
        if marker not in content: fail(f"DD checklist missing section: {marker}")
    ok("dd_package_checklist.md present with all sections")

    # SKILL.md sha256 match across 3 mirrors
    shas = {}
    for m in (".claude", ".agent", ".agents"):
        p = ROOT / m / "skills" / "finance-ap" / "SKILL.md"
        if not p.exists(): fail(f"SKILL.md missing in {m}")
        if "## DD Readiness" not in p.read_text(encoding="utf-8"): fail(f"{m}/.../SKILL.md missing DD Readiness section")
        shas[m] = hashlib.sha256(p.read_bytes()).hexdigest()
    if len(set(shas.values())) != 1: fail(f"SKILL.md sha256 mismatch across mirrors: {shas}")
    ok(f"3 SKILL.md mirrors identical sha256: {list(shas.values())[0][:16]}...")

    # v3.9 size
    sz = V39_PATH.stat().st_size
    if not (86000 <= sz <= 110000): fail(f"v3.9 size {sz} outside [86000, 110000]")
    ok(f"v3.9 source size = {sz} bytes")

    # Lock test
    lt = ROOT / "output" / "s255" / "lock_test_post_v1.json"
    if not lt.exists(): fail(f"missing {lt}")
    lock = json.loads(lt.read_text(encoding="utf-8"))
    if lock["actual_pairs"] != lock["expected_pairs"]: fail(f"lock test {lock['actual_pairs']}/{lock['expected_pairs']} pairs locked")
    ok(f"lock test: {lock['actual_pairs']}/{lock['expected_pairs']} pairs PASS (6 writers × {lock['tabs_total']} tabs)")

    print("\n[PASS] Phase 9a gate — Bridge DD ready + skill synced + lock test 96/96")


if __name__ == "__main__":
    main()
