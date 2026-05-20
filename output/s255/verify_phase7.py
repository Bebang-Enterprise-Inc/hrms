"""verify_phase7.py — S255 Phase 7 gate."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def fail(m): print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)
def ok(m): print(f"[OK]   {m}")


def main():
    src = V39_PATH.read_text(encoding="utf-8")
    if "const payment_plan_mirror_disabled = false" not in src:
        fail("v3.9 missing 'const payment_plan_mirror_disabled = false'")
    ok("v3.9 has payment_plan_mirror_disabled constant (default false)")
    if "if (payment_plan_mirror_disabled) {\n    return { mirror_disabled: true" not in src:
        fail("mirrorDenisePaymentPlanTab_ missing early-exit")
    ok("mirrorDenisePaymentPlanTab_ has early-exit on flag=true")
    if "payment_plan_mirror_disabled\n    ? ['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany', 'Payment Plan']" not in src:
        fail("syncStatusFieldsFromFPM_ missing conditional Payment Plan inclusion")
    ok("syncStatusFieldsFromFPM_ adds 'Payment Plan' to iteration when flag=true")

    rb = ROOT / "output" / "s255" / "payment_plan_cutover_runbook.md"
    if not rb.exists(): fail(f"missing {rb}")
    content = rb.read_text(encoding="utf-8")
    for marker in ("Pre-cutover state", "Post-cutover state", "Cutover procedure", "Rollback"):
        if marker not in content: fail(f"runbook missing section: {marker}")
    ok("cutover runbook has all 4 required sections")

    print("\n[PASS] Phase 7 gate — status sync wiring complete (mirror default ON; cutover ready)")


if __name__ == "__main__":
    main()
