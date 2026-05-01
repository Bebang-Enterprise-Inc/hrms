"""S225 narrow-sweep launcher — runs s209-all-stores.spec.ts against ONLY the
9 stores that failed or were skipped in sweep-v8 (2026-04-30).

The 9 stores:
  6 fails:
    - SM MARIKINA — backend WR not produced (silent dispatch fail under User None)
    - STA. LUCIA EAST GRAND MALL — accept-delivery-button 30s timeout
    - THE GRID ROCKWELL — accept-delivery-button 30s timeout
    - THE TERMINAL — accept-delivery-button 30s timeout
    - UP TOWN MALL BGC — accept-delivery-button 30s timeout
    - VISTA MALL TAGUIG — accept-delivery-button 30s timeout
  3 skipped:
    - AYALA EVO CITY (KNOWN: precondition-blocked — no orderable items in master)
    - ROBINSONS PLACE DASMARINAS (likely consecutive-fail abort)
    - XENTROMALL MONTALBAN (likely consecutive-fail abort, sweep position 49)

This script wraps the existing scripts/s212_launch_sweep.py with two extras:
  1. S209_STORES_FILTER env (pipe-separated store names) → spec generates
     only those test() blocks.
  2. E2E_FRESH_LOGIN=1 + E2E_MAX_AUTH_AGE_MS=300000 → forces fresh Playwright
     login per fixture (5-min cache window) so the User None / session-cookie
     bug from sweep-v8 doesn't recur on the narrow run.

Use:
    doppler run --project bei-erp --config dev -- python scripts/s225_launch_fails_only.py

Optional flags:
    --output-dir PATH (default: output/l3/s225/sweep-narrow-v9)
    --bei-tasks PATH  (default: F:/Dropbox/Projects/bei-tasks-s225-...)

The narrow spec runs ~9 tests in ~10 minutes vs ~50 minutes for full 49-store sweep.
Successful close-out: 9/9 pass with no User None Sentry events in the run window.
"""
from __future__ import annotations
import argparse
import os
import pathlib
import subprocess
import sys

# 9 stores — keep stable for re-run idempotency
NARROW_STORES = [
    # 6 sweep-v8 fails:
    "SM MARIKINA - BEBANG SM MARIKINA INC.",
    "STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.",
    "THE GRID ROCKWELL - TASTECARTEL CORP.",
    "THE TERMINAL - BEBANG STARMALL ALABANG INC.",
    "UP TOWN MALL BGC - DMD HOLDINGS INC.",
    "VISTA MALL TAGUIG - TRICERN FOOD CORP.",
    # 3 sweep-v8 skipped:
    "AYALA EVO CITY - BEBANG MEGA INC.",
    "ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.",
    "XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.",
]

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_BEI_TASKS = (
    "F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard"
)
DEFAULT_OUTPUT = ROOT / "output" / "l3" / "s225" / "sweep-narrow-v9"


def main() -> int:
    parser = argparse.ArgumentParser(description="S225 narrow sweep launcher (9 stores)")
    parser.add_argument("--bei-tasks", default=DEFAULT_BEI_TASKS, help="bei-tasks worktree path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT), help="evidence output dir")
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Compose env: store filter + fresh-login + auth-age cap
    env = os.environ.copy()
    env["S209_STORES_FILTER"] = "|".join(NARROW_STORES)
    env["E2E_FRESH_LOGIN"] = "1"
    env["E2E_MAX_AUTH_AGE_MS"] = "300000"  # 5 min cache cap (in case fresh-login disabled later)
    env["EVIDENCE_ROOT"] = str(output_dir)
    env["S209_EVIDENCE_ROOT"] = str(output_dir)
    env["BEI_ERP_ROOT"] = str(ROOT)

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "s212_launch_sweep.py"),
        "--spec", "tests/e2e/specs/s209-all-stores.spec.ts",
        "--log", str(output_dir / "sweep_full_run.log"),
        "--pid-file", str(output_dir / "sweep.pid"),
        "--ledger", str(output_dir / "sweep_ledger.json"),
        "--decision-log", str(output_dir / "monitor_decisions.log"),
        "--bei-tasks", args.bei_tasks,
        "--kill-same-fingerprint", "5",  # narrower threshold; 9 stores total so abort fast on cluster
    ]

    print(f"[s225-narrow] Launching {len(NARROW_STORES)}-store sweep")
    print(f"[s225-narrow] Output: {output_dir}")
    print(f"[s225-narrow] S209_STORES_FILTER pipe-set:")
    for s in NARROW_STORES:
        print(f"  - {s}")
    print(f"[s225-narrow] Fresh-login: ENABLED (E2E_FRESH_LOGIN=1, E2E_MAX_AUTH_AGE_MS=300000)")
    print()

    proc = subprocess.run(cmd, env=env, cwd=str(ROOT))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
