"""Run SM MARIKINA isolated sweep N times to reproduce or rule out the v11 flake.

Each iteration runs the full happy chain for SM MARIKINA only (1 test).
- If 3/3 pass: flake was concurrent-test pollution; safe at the test-runner level
- If <3/3: reproducible race — need backend or frontend fix

Each iteration writes its own evidence dir output/l3/s225/marikina-iso-N/.
After all iterations, prints summary.
"""
from __future__ import annotations
import argparse
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_BEI_TASKS = "F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard"
STORE = "SM MARIKINA - BEBANG SM MARIKINA INC."

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--bei-tasks", default=DEFAULT_BEI_TASKS)
    args = parser.parse_args()

    results = []
    for i in range(1, args.iterations + 1):
        out_dir = ROOT / "output" / "l3" / "s225" / f"marikina-iso-{i}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Wipe playwright auth between iterations to ensure fresh login each
        auth = pathlib.Path(args.bei_tasks) / ".playwright-auth"
        if auth.exists():
            try:
                shutil.rmtree(auth)
            except Exception as e:
                print(f"[iso] could not remove .playwright-auth: {e}")

        env = os.environ.copy()
        env["S209_STORES_FILTER"] = STORE
        env["E2E_FRESH_LOGIN"] = "1"
        env["E2E_MAX_AUTH_AGE_MS"] = "300000"
        env["EVIDENCE_ROOT"] = str(out_dir)
        env["S209_EVIDENCE_ROOT"] = str(out_dir)
        env["BEI_ERP_ROOT"] = str(ROOT)

        cmd = [
            sys.executable, str(ROOT / "scripts" / "s212_launch_sweep.py"),
            "--spec", "tests/e2e/specs/s209-all-stores.spec.ts",
            "--log", str(out_dir / "sweep_full_run.log"),
            "--pid-file", str(out_dir / "sweep.pid"),
            "--ledger", str(out_dir / "sweep_ledger.json"),
            "--decision-log", str(out_dir / "monitor_decisions.log"),
            "--bei-tasks", args.bei_tasks,
            "--kill-same-fingerprint", "1",
        ]
        print(f"\n=== ITERATION {i} ===")
        print(f"output_dir: {out_dir}")
        proc = subprocess.run(cmd, env=env, cwd=str(ROOT))

        # Inspect ledger to determine pass/fail
        ledger_path = out_dir / "sweep_ledger.json"
        passed = False
        if ledger_path.exists():
            import json
            with open(ledger_path) as f:
                ledger = json.load(f)
            si_for_marikina = [e for e in ledger if e.get("kind") == "si-create" and e.get("payload", {}).get("store") == STORE]
            passed = len(si_for_marikina) > 0
        results.append({"iteration": i, "passed": passed, "exit_code": proc.returncode})
        print(f"iteration {i}: passed={passed} exit_code={proc.returncode}")

    print("\n========== SUMMARY ==========")
    for r in results:
        print(f"  iter {r['iteration']}: passed={r['passed']} exit={r['exit_code']}")
    pass_count = sum(1 for r in results if r["passed"])
    print(f"  TOTAL: {pass_count}/{len(results)} passed")
    sys.exit(0 if pass_count == len(results) else 1)


if __name__ == "__main__":
    main()
