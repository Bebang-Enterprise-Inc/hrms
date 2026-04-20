#!/usr/bin/env python3
"""S212 Phase 4 exit-gate test — proves the monitor kills on both triggers.

Writes two synthetic Playwright logs to a temp dir and invokes
scripts/s212_sweep_monitor.py in `--dry-run --once` mode. Asserts the
monitor_decisions.log file emits a KILL line for each trigger class.

Rule A — same-fingerprint bucket >= 3:
  Emit 3 lines of "Error: SI.items[0].qty expected 8 received 10"
  (normalized fingerprint identical across 3 different SI docnames).

Rule B — pass-rate below threshold after N completed tests:
  Emit 12 result lines: 3 passes + 9 fails => 0.25 pass rate after 12,
  which is below 0.5 after the 10-test warmup.

Each scenario uses an isolated log / pid-file / decision-log so their
state doesn't cross-contaminate.
"""
from __future__ import annotations
import pathlib
import subprocess
import sys
import tempfile


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MONITOR = REPO_ROOT / "scripts" / "s212_sweep_monitor.py"


def _run_monitor(log: pathlib.Path, pid_file: pathlib.Path, decision_log: pathlib.Path):
	cmd = [
		sys.executable, str(MONITOR),
		"--log", str(log),
		"--pid-file", str(pid_file),
		"--decision-log", str(decision_log),
		"--kill-same-fingerprint", "3",
		"--kill-pass-rate-below", "0.5",
		"--kill-pass-rate-after-n", "10",
		"--dry-run",
		"--once",
	]
	r = subprocess.run(cmd, capture_output=True, text=True,
		creationflags=0x08000000 if sys.platform == "win32" else 0)
	if r.returncode != 0:
		print(r.stdout)
		print(r.stderr, file=sys.stderr)
		raise SystemExit(f"monitor failed (exit={r.returncode})")


def _scenario_same_fingerprint(tmp: pathlib.Path) -> None:
	log = tmp / "fp_same.log"
	pid_file = tmp / "fp_same.pid"
	decision_log = tmp / "fp_same_decision.log"
	pid_file.write_text("12345", encoding="utf-8")
	log.write_text(
		"running 1 tests\n"
		"  1) [chromium] › s209-all-stores.spec.ts › 49-store sweep › STORE_A\n"
		"     Error: SI.items[0].qty expected 8 received 10 at ACC-SINV-2026-00101\n"
		"       at Object.fn (specs/s209-all-stores.spec.ts:42:5)\n"
		"  2) [chromium] › s209-all-stores.spec.ts › 49-store sweep › STORE_B\n"
		"     Error: SI.items[0].qty expected 8 received 10 at ACC-SINV-2026-00102\n"
		"       at Object.fn (specs/s209-all-stores.spec.ts:42:5)\n"
		"  3) [chromium] › s209-all-stores.spec.ts › 49-store sweep › STORE_C\n"
		"     Error: SI.items[0].qty expected 8 received 10 at ACC-SINV-2026-00103\n"
		"       at Object.fn (specs/s209-all-stores.spec.ts:42:5)\n",
		encoding="utf-8",
	)
	_run_monitor(log, pid_file, decision_log)
	contents = decision_log.read_text(encoding="utf-8")
	if "KILL pid=12345" not in contents:
		raise SystemExit(f"scenario A (same-fingerprint) did not emit KILL:\n{contents}")
	if "same-fingerprint=" not in contents:
		raise SystemExit(f"scenario A missing fingerprint reason:\n{contents}")
	print("[OK] Scenario A — same-fingerprint kill triggered")


def _scenario_pass_rate(tmp: pathlib.Path) -> None:
	log = tmp / "pr_low.log"
	pid_file = tmp / "pr_low.pid"
	decision_log = tmp / "pr_low_decision.log"
	pid_file.write_text("54321", encoding="utf-8")
	# 3 unique-fingerprint failures so rule A never triggers (buckets have count 1 each);
	# 9 total fails + 3 passes => 12 completed, 0.25 pass rate
	lines = []
	for i in range(3):
		lines.append(f"  ✓  {i+1} [chromium] › 49-store sweep › PASS_{i}")
	for i in range(9):
		lines.append(f"  ✘  {i+4} [chromium] › 49-store sweep › FAIL_{i}")
		# Each failure gets a UNIQUE fingerprint so bucket stays at 1
		lines.append(f"     Error: failure variant_{i} at some location")
		lines.append(f"       at Object.fn (specs/s209-all-stores.spec.ts:42:5)")
	log.write_text("\n".join(lines) + "\n", encoding="utf-8")
	_run_monitor(log, pid_file, decision_log)
	contents = decision_log.read_text(encoding="utf-8")
	if "KILL pid=54321" not in contents:
		raise SystemExit(f"scenario B (pass-rate) did not emit KILL:\n{contents}")
	if "pass-rate=" not in contents:
		raise SystemExit(f"scenario B missing pass-rate reason:\n{contents}")
	print("[OK] Scenario B — pass-rate-below kill triggered")


def main() -> int:
	with tempfile.TemporaryDirectory(prefix="s212_mon_test_") as t:
		tmp = pathlib.Path(t)
		_scenario_same_fingerprint(tmp)
		_scenario_pass_rate(tmp)
	print("[S212] Monitor dry-run tests PASSED for both triggers.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
