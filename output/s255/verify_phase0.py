"""verify_phase0.py — S255 Phase 0 gate.

Per the plan v1.1 ## Verify Script Assertions section:
- baseline_sha.txt exists + matches origin/production
- script_source_backup_v38.gs exists, size in [85000, 95000] bytes
- cloud_scheduler_pause_log.json shows paused: true
- baseline_state.json has keys for 18 tabs
- S255_SURFACE_OWNERSHIP_MATRIX.csv has >= 10 data rows
- 3 SKILL.md mirrors have "Bridge" section (>= 5 grep hits each)

Exits 0 on PASS, non-zero on FAIL.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "s255"


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"[OK]   {msg}")


# Assertion 1: baseline_sha.txt
p = OUT / "baseline_sha.txt"
if not p.exists():
    fail(f"missing {p}")
expected = p.read_text(encoding="utf-8").strip()
actual = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "origin/production"], text=True).strip()
if expected != actual:
    fail(f"baseline_sha {expected!r} != origin/production {actual!r}")
ok(f"baseline_sha matches origin/production = {expected[:10]}")

# Assertion 2: script_source_backup_v38.gs size
p = OUT / "script_source_backup_v38.gs"
if not p.exists():
    fail(f"missing {p}")
sz = p.stat().st_size
if not (85000 <= sz <= 95000):
    fail(f"backup size {sz} not in [85000, 95000]")
ok(f"backup size {sz} bytes in [85000, 95000]")

# Assertion 3: cloud_scheduler_pause_log.json shows paused: true
p = OUT / "cloud_scheduler_pause_log.json"
if not p.exists():
    fail(f"missing {p}")
data = json.loads(p.read_text(encoding="utf-8"))
if not data.get("paused"):
    fail(f"pause log paused != true; got {data.get('paused')!r}")
ok(f"scheduler paused: job={data.get('job_name')}, state={data.get('current_state')}")

# Assertion 4: baseline_state.json has 18 tabs
p = OUT / "baseline_state.json"
if not p.exists():
    fail(f"missing {p}")
data = json.loads(p.read_text(encoding="utf-8"))
if data.get("tab_count") != 18:
    fail(f"baseline_state has {data.get('tab_count')} tabs, expected 18")
tab_names = {t["name"] for t in data["tabs"]}
required = {"Suppliers SOA", "Head Office", "CAPEX", "Payment Plan"}
missing = required - tab_names
if missing:
    fail(f"baseline_state missing tabs: {missing}")
ok(f"AP Master baseline has 18 tabs incl. all entry tabs")

# Assertion 5: S255_SURFACE_OWNERSHIP_MATRIX.csv has >= 10 data rows
p = OUT / "S255_SURFACE_OWNERSHIP_MATRIX.csv"
if not p.exists():
    fail(f"missing {p}")
lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
data_rows = len(lines) - 1  # minus header
if data_rows < 10:
    fail(f"ownership matrix has {data_rows} data rows, < 10")
ok(f"ownership matrix has {data_rows} data rows")

# Assertion 6: 3 SKILL.md mirrors have Bridge section
total_bridge_hits = 0
for mirror in [".claude", ".agent", ".agents"]:
    p = ROOT / mirror / "skills" / "finance-ap" / "SKILL.md"
    if not p.exists():
        fail(f"missing skill file: {p}")
    content = p.read_text(encoding="utf-8")
    hits = len(re.findall(r"bridge", content, re.IGNORECASE))
    if hits < 5:
        fail(f"{mirror}/.../SKILL.md has {hits} Bridge mentions, < 5")
    total_bridge_hits += hits
    ok(f"{mirror}/skills/finance-ap/SKILL.md: {hits} Bridge mentions")
ok(f"total Bridge mentions across 3 mirrors: {total_bridge_hits}")

# Optional: Denise PP baseline + Bridge domain check
p = OUT / "denise_pp_baseline.json"
if p.exists():
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("bridge_user_present"):
        ok(f"Denise PP has Bridge-domain ACL: {data.get('bridge_emails_on_acl')}")
    else:
        fail(f"Denise PP has NO Bridge-domain user; drift requires Phase 8 review")

print("\n[PASS] Phase 0 gate — all assertions met")
