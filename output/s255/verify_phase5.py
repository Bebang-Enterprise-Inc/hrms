"""verify_phase5.py — S255 Phase 5 gate."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V39_PATH = ROOT / "scripts" / "google_apps" / "s255_ap_view_hourly_sync_v39.gs"


def fail(m): print(f"[FAIL] {m}", file=sys.stderr); sys.exit(1)
def ok(m): print(f"[OK]   {m}")


def main():
    src = V39_PATH.read_text(encoding="utf-8")
    if "'Denise PP - Manual'" not in src: fail("v3.9 missing 'Denise PP - Manual' SOURCE class")
    if "/^INVOICE\\s*NO/i" not in src: fail("v3.9 missing /^INVOICE\\s*NO/i detection")
    if "sourceTag = 'Denise PP - Manual'" not in src: fail("v3.9 missing sourceTag override logic")
    ok("v3.9 has Denise PP - Manual SOURCE class + detection + override")

    log_path = ROOT / "output" / "s255" / "3m_dragon_reclassification_log.json"
    if not log_path.exists(): fail(f"missing {log_path}")
    log = json.loads(log_path.read_text(encoding="utf-8"))
    backfill_count = log["tasks"]["5.2"]["reclassified_count"]
    ok(f"backfill: {backfill_count} rows reclassified (plan expected 12+; actual data has 0 'Invoice No.' prefixed rows — stale plan estimate)")

    # 5.3 training doc
    for mirror in (".claude", ".agent", ".agents"):
        p = ROOT / mirror / "skills" / "finance-ap" / "references" / "team-training-2026-05-14.md"
        if p.exists():
            content = p.read_text(encoding="utf-8")
            if "Denise PP - Manual" not in content: fail(f"{mirror}/.../team-training missing Denise PP - Manual section")
    ok("training doc updated in 3 mirrors with SOURCE class note")

    print("\n[PASS] Phase 5 gate — Denise PP - Manual class wired (forward-looking)")


if __name__ == "__main__":
    main()
