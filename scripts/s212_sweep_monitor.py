#!/usr/bin/env python3
"""S212 sweep monitor — kill-on-defect daemon for Playwright sweeps.

Watches a Playwright log file + test ledger and kills the sweep PID when:

  (a) Same error FINGERPRINT bucket reaches >= `--kill-same-fingerprint`
      within a rolling window (default: whole log), OR
  (b) Pass rate drops below `--kill-pass-rate-below` after at least
      `--kill-pass-rate-after-n` tests have COMPLETED.

The monitor exists because S209 wasted ~60 wall-clock minutes on R2 + R3
rounds after it was already obvious that 14/49 orders were failing with
the same MR-missing fingerprint. A monitor with semantic bucket-based
kill — not just Playwright's built-in max-failures — prevents that class
of time waste.

USAGE:

  python scripts/s212_sweep_monitor.py \\
      --log output/l3/s212/sweep_full_run.log \\
      --pid-file output/l3/s212/sweep.pid \\
      --ledger output/l3/s212/sweep_ledger.json \\
      --decision-log output/l3/s212/monitor_decisions.log \\
      --kill-same-fingerprint 3 \\
      --kill-pass-rate-below 0.5 \\
      --kill-pass-rate-after-n 10 \\
      [--poll-interval 2.0] \\
      [--dry-run]

In dry-run, the monitor logs the SIGTERM decision but does NOT kill the
PID — used by the Phase 4 test harness.
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

# Typical Playwright error surface from the S209 sweep log:
#   "  Error: Material Request for order BEI-ORD-2026-00340 did not appear within 30s"
#   "  Error: expect(received).toBe(expected) // SI.items[0].qty"
# Extract the payload after `Error:` up to the first `    at ` frame or EOL.
FINGERPRINT_EXTRACT = re.compile(r"Error:\s*(.+?)(?:\s+at\s+|$)", re.DOTALL)

# Normalize doc names so different order/MR/WR/SI bucket together
DOCNAME_PATTERNS = [
	(re.compile(r"BEI-ORD-\d{4}-\d{5}"), "<ORDER>"),
	(re.compile(r"MAT-MR-\d{4}-\d{5}"), "<MR>"),
	(re.compile(r"MAT-STE-\d{4}-\d{5}"), "<SE>"),
	(re.compile(r"BEI-WHR-\d{4}-\d{5}"), "<WR>"),
	(re.compile(r"ACC-SINV-\d{4}-\d{5}"), "<SI>"),
	# Numeric ids in between also differ per test run
	(re.compile(r"\b\d{10,}\b"), "<TS>"),
]


def fingerprint(error_line: str) -> str:
	"""Normalize an error line to a fingerprint suitable for bucket counting."""
	m = FINGERPRINT_EXTRACT.search(error_line)
	raw = (m.group(1) if m else error_line).strip()[:300]
	for pat, repl in DOCNAME_PATTERNS:
		raw = pat.sub(repl, raw)
	# Collapse runs of whitespace
	raw = re.sub(r"\s+", " ", raw).strip()
	return raw


# Result line heuristics — Playwright's default reporter emits lines like
#   "  ✓  1 [chromium] › tests/e2e/specs/s209-all-stores.spec.ts:27:9 › 49-store sweep › SM TANZA"
#   "  ✘  2 [chromium] › tests/e2e/specs/s209-all-stores.spec.ts:27:9 › 49-store sweep › XYZ"
#   "  -  3 [chromium] › tests/e2e/specs/s209-all-stores.spec.ts:27:9 › 49-store sweep › SKIPPED"
# We can also look for "passed", "failed", "skipped" summary tokens.
RESULT_PASS = re.compile(r"^\s*✓\s+\d+")
RESULT_FAIL = re.compile(r"^\s*✘\s+\d+")
RESULT_SKIP = re.compile(r"^\s*[-~]\s+\d+")


# ---------------------------------------------------------------------------
# Kill
# ---------------------------------------------------------------------------

def kill_sweep_pid(pid: int, reason: str, decision_log: pathlib.Path, dry_run: bool = False) -> None:
	"""SIGTERM a PID + its process tree on Unix / taskkill /T on Windows."""
	line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] KILL pid={pid} reason={reason}" + (" [DRY-RUN]" if dry_run else "")
	decision_log.parent.mkdir(parents=True, exist_ok=True)
	with decision_log.open("a", encoding="utf-8") as f:
		f.write(line + "\n")
	print(line, file=sys.stderr)
	if dry_run:
		return
	if sys.platform == "win32":
		# /T kills the tree (Chromium children too); /F forces termination
		subprocess.run(
			["taskkill", "/PID", str(pid), "/T", "/F"],
			check=False,
			capture_output=True,
			creationflags=0x08000000,
		)
	else:
		# Negative PID => process group (npx + node + chromium)
		try:
			os.killpg(os.getpgid(pid), signal.SIGTERM)
		except (ProcessLookupError, PermissionError):
			try:
				os.kill(pid, signal.SIGTERM)
			except ProcessLookupError:
				pass


# ---------------------------------------------------------------------------
# State + main loop
# ---------------------------------------------------------------------------

@dataclass
class MonitorState:
	buckets: Counter = field(default_factory=Counter)
	completed_tests: int = 0  # passes + fails (not skips)
	passes: int = 0
	fails: int = 0
	decision_made: bool = False
	last_ledger_size: int = 0


def tail_and_classify(
	state: MonitorState,
	log_path: pathlib.Path,
	position: int,
) -> tuple[int, list[str]]:
	"""Read any new bytes since `position`; update state; return (new_pos, new_lines)."""
	if not log_path.exists():
		return position, []
	size = log_path.stat().st_size
	if size < position:
		# Log rotated or truncated
		position = 0
	if size == position:
		return position, []
	with log_path.open("rb") as f:
		f.seek(position)
		chunk = f.read(size - position)
	try:
		text = chunk.decode("utf-8", errors="replace")
	except Exception:
		text = chunk.decode("latin-1", errors="replace")
	lines = text.splitlines()
	for line in lines:
		if RESULT_PASS.match(line):
			state.completed_tests += 1
			state.passes += 1
		elif RESULT_FAIL.match(line):
			state.completed_tests += 1
			state.fails += 1
		elif "Error:" in line:
			fp = fingerprint(line)
			if fp:
				state.buckets[fp] += 1
	return size, lines


def ingest_ledger(state: MonitorState, ledger_path: Optional[pathlib.Path]) -> None:
	"""Best-effort ledger read — used to cross-check pass count when log is unreliable."""
	if not ledger_path or not ledger_path.exists():
		return
	try:
		entries = json.loads(ledger_path.read_text(encoding="utf-8"))
	except Exception:
		return
	if not isinstance(entries, list):
		return
	# Count unique stores with an SI-create entry
	si_stores = {
		e.get("payload", {}).get("store")
		for e in entries
		if isinstance(e, dict) and e.get("kind") == "si-create"
	}
	si_stores.discard(None)
	# Prefer ledger pass count when it exceeds log-derived pass count
	if len(si_stores) > state.passes:
		state.passes = len(si_stores)


def evaluate_kill(
	state: MonitorState,
	kill_same_fingerprint: int,
	kill_pass_rate_below: float,
	kill_pass_rate_after_n: int,
	decision_log: pathlib.Path,
) -> Optional[str]:
	"""Return a reason string if a kill is warranted, else None."""
	# Rule A: same-fingerprint bucket threshold
	if state.buckets:
		top_fp, top_ct = state.buckets.most_common(1)[0]
		if top_ct >= kill_same_fingerprint:
			return (
				f"same-fingerprint={top_ct} >= {kill_same_fingerprint} | "
				f"fp={top_fp[:180]}"
			)
	# Rule B: pass-rate floor after N completed tests
	if state.completed_tests >= kill_pass_rate_after_n:
		pr = state.passes / max(state.completed_tests, 1)
		if pr < kill_pass_rate_below:
			return (
				f"pass-rate={pr:.3f} < {kill_pass_rate_below} after "
				f"{state.completed_tests} tests (passes={state.passes}, fails={state.fails})"
			)
	return None


def log_periodic_status(state: MonitorState, decision_log: pathlib.Path) -> None:
	decision_log.parent.mkdir(parents=True, exist_ok=True)
	with decision_log.open("a", encoding="utf-8") as f:
		top = state.buckets.most_common(3)
		f.write(
			f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] STATUS completed={state.completed_tests} "
			f"passes={state.passes} fails={state.fails} top_buckets={top}\n"
		)


def pid_alive(pid: int) -> bool:
	if sys.platform == "win32":
		# Use tasklist
		r = subprocess.run(
			["tasklist", "/FI", f"PID eq {pid}"],
			capture_output=True, text=True, check=False,
			creationflags=0x08000000,
		)
		return str(pid) in (r.stdout or "")
	try:
		os.kill(pid, 0)
		return True
	except ProcessLookupError:
		return False
	except PermissionError:
		return True


def read_pid_file(pid_file: pathlib.Path) -> Optional[int]:
	if not pid_file.exists():
		return None
	try:
		return int(pid_file.read_text().strip())
	except Exception:
		return None


def main() -> int:
	ap = argparse.ArgumentParser()
	ap.add_argument("--log", required=True, type=pathlib.Path)
	ap.add_argument("--pid-file", required=True, type=pathlib.Path)
	ap.add_argument("--ledger", type=pathlib.Path)
	ap.add_argument("--decision-log", required=True, type=pathlib.Path)
	ap.add_argument("--kill-same-fingerprint", type=int, default=3)
	ap.add_argument("--kill-pass-rate-below", type=float, default=0.5)
	ap.add_argument("--kill-pass-rate-after-n", type=int, default=10)
	ap.add_argument("--poll-interval", type=float, default=2.0)
	ap.add_argument("--status-interval", type=float, default=30.0)
	ap.add_argument("--dry-run", action="store_true",
		help="Log kill decision but do not actually SIGTERM")
	ap.add_argument("--once", action="store_true",
		help="Single pass (used by test harness)")
	args = ap.parse_args()

	state = MonitorState()
	position = 0
	last_status_at = 0.0

	args.decision_log.parent.mkdir(parents=True, exist_ok=True)
	with args.decision_log.open("a", encoding="utf-8") as f:
		f.write(
			f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] MONITOR START "
			f"kill-same-fp={args.kill_same_fingerprint} "
			f"kill-pass-rate-below={args.kill_pass_rate_below} "
			f"kill-after-n={args.kill_pass_rate_after_n} "
			f"dry-run={args.dry_run}\n"
		)

	while True:
		position, _ = tail_and_classify(state, args.log, position)
		ingest_ledger(state, args.ledger)

		reason = evaluate_kill(
			state,
			args.kill_same_fingerprint,
			args.kill_pass_rate_below,
			args.kill_pass_rate_after_n,
			args.decision_log,
		)
		if reason and not state.decision_made:
			pid = read_pid_file(args.pid_file)
			if pid is None:
				# PID file not yet written — don't kill, just note it
				with args.decision_log.open("a", encoding="utf-8") as f:
					f.write(
						f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] WOULD-KILL (no pid yet) "
						f"reason={reason}\n"
					)
			else:
				kill_sweep_pid(pid, reason, args.decision_log, dry_run=args.dry_run)
				state.decision_made = True
				if args.dry_run or args.once:
					return 0

		# Periodic status line
		now = time.time()
		if now - last_status_at >= args.status_interval:
			log_periodic_status(state, args.decision_log)
			last_status_at = now

		if args.once:
			# Single-pass mode for unit test
			return 0

		# Terminate if the watched PID is no longer alive
		pid = read_pid_file(args.pid_file)
		if pid is not None and not pid_alive(pid):
			with args.decision_log.open("a", encoding="utf-8") as f:
				f.write(
					f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] MONITOR EXIT "
					f"pid={pid} no-longer-alive completed={state.completed_tests} "
					f"passes={state.passes} fails={state.fails}\n"
				)
			return 0

		time.sleep(args.poll_interval)


if __name__ == "__main__":
	sys.exit(main())
