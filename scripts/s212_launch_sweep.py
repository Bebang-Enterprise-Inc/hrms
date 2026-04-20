#!/usr/bin/env python3
"""S212 sweep launcher — runs npx playwright + sweep monitor in parallel.

Spawns `npx playwright test <spec>` in the bei-tasks repo, captures its
PID to `--pid-file`, then runs `s212_sweep_monitor.py` pointed at the
same PID + log + ledger. Waits for Playwright to exit (or for the
monitor to kill it) and propagates the exit code.

USAGE:

  python scripts/s212_launch_sweep.py \\
      --spec tests/e2e/specs/s209-all-stores.spec.ts \\
      --log output/l3/s212/sweep_full_run.log \\
      --pid-file output/l3/s212/sweep.pid \\
      --ledger output/l3/s212/sweep_ledger.json \\
      --decision-log output/l3/s212/monitor_decisions.log \\
      --kill-same-fingerprint 3 \\
      --kill-pass-rate-below 0.5 \\
      --kill-pass-rate-after-n 10 \\
      [--bei-tasks F:/Dropbox/Projects/bei-tasks]

Env vars expected by the spec (pass-through, not set here):
  FRAPPE_API_KEY, FRAPPE_API_SECRET, BEI_ERP_ROOT, S209_EVIDENCE_ROOT,
  EVIDENCE_ROOT
"""
from __future__ import annotations
import argparse
import os
import pathlib
import signal
import subprocess
import sys
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MONITOR_SCRIPT = REPO_ROOT / "scripts" / "s212_sweep_monitor.py"


def main() -> int:
	ap = argparse.ArgumentParser()
	ap.add_argument("--spec", required=True,
		help="Playwright spec path relative to bei-tasks repo")
	ap.add_argument("--log", required=True, type=pathlib.Path)
	ap.add_argument("--pid-file", required=True, type=pathlib.Path)
	ap.add_argument("--ledger", required=True, type=pathlib.Path)
	ap.add_argument("--decision-log", required=True, type=pathlib.Path)
	ap.add_argument("--bei-tasks", type=pathlib.Path,
		default=pathlib.Path("F:/Dropbox/Projects/bei-tasks"))
	ap.add_argument("--kill-same-fingerprint", type=int, default=3)
	ap.add_argument("--kill-pass-rate-below", type=float, default=0.5)
	ap.add_argument("--kill-pass-rate-after-n", type=int, default=10)
	ap.add_argument("--timeout", type=int, default=600000,
		help="Playwright per-test timeout ms")
	ap.add_argument("--retries", type=int, default=0)
	ap.add_argument("--monitor-only", action="store_true",
		help="Do NOT spawn playwright — just run the monitor against an existing log/pid")
	args = ap.parse_args()

	args.log.parent.mkdir(parents=True, exist_ok=True)
	args.pid_file.parent.mkdir(parents=True, exist_ok=True)
	args.decision_log.parent.mkdir(parents=True, exist_ok=True)

	playwright_proc: subprocess.Popen | None = None
	if not args.monitor_only:
		# Open the log file for append
		log_fh = args.log.open("a", encoding="utf-8", buffering=1)
		log_fh.write(
			f"\n[{time.strftime('%Y-%m-%dT%H:%M:%S')}] S212 LAUNCHER starting "
			f"spec={args.spec}\n"
		)
		log_fh.flush()

		popen_kwargs: dict = {
			"cwd": str(args.bei_tasks),
			"stdout": log_fh,
			"stderr": subprocess.STDOUT,
		}
		if sys.platform == "win32":
			popen_kwargs["creationflags"] = (
				subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000  # CREATE_NO_WINDOW
			)
		else:
			popen_kwargs["start_new_session"] = True

		cmd = [
			"npx", "playwright", "test", args.spec,
			"--reporter=line",
			f"--timeout={args.timeout}",
			f"--retries={args.retries}",
		]
		playwright_proc = subprocess.Popen(cmd, **popen_kwargs)
		args.pid_file.write_text(str(playwright_proc.pid), encoding="utf-8")
		print(f"[S212] Playwright pid={playwright_proc.pid} logged to {args.log}")

	# Spawn monitor (runs until Playwright exits OR monitor decides to kill)
	monitor_cmd = [
		sys.executable, str(MONITOR_SCRIPT),
		"--log", str(args.log),
		"--pid-file", str(args.pid_file),
		"--ledger", str(args.ledger),
		"--decision-log", str(args.decision_log),
		"--kill-same-fingerprint", str(args.kill_same_fingerprint),
		"--kill-pass-rate-below", str(args.kill_pass_rate_below),
		"--kill-pass-rate-after-n", str(args.kill_pass_rate_after_n),
	]
	mon_kwargs: dict = {}
	if sys.platform == "win32":
		mon_kwargs["creationflags"] = 0x08000000
	monitor_proc = subprocess.Popen(monitor_cmd, **mon_kwargs)
	print(f"[S212] Monitor pid={monitor_proc.pid}")

	# Wait for Playwright
	exit_code = 0
	if playwright_proc:
		exit_code = playwright_proc.wait()
		print(f"[S212] Playwright exit code={exit_code}")

	# Stop monitor — it might still be tailing
	try:
		monitor_proc.terminate()
	except Exception:
		pass
	try:
		monitor_proc.wait(timeout=10)
	except Exception:
		try:
			monitor_proc.kill()
		except Exception:
			pass

	return exit_code


if __name__ == "__main__":
	sys.exit(main())
