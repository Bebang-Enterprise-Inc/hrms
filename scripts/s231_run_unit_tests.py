#!/usr/bin/env python3
"""S231: run the 3 new unit-test modules on the live Frappe container.

Captures bench output for each module to
output/s231/verification/test_<module>.txt and a combined summary
to deploy_validation.json under "tests".
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from s231_ssm_helper import (  # noqa: E402
	AWS_REGION,
	BACKEND_CONTAINER_FILTER,
	INSTANCE_ID,
)
import base64
import time

OUT_DIR = REPO_ROOT / "output" / "s231" / "verification"


def run_bench_test(module: str, timeout: int = 600) -> dict:
	"""Invoke `bench run-tests --module hrms.tests.<module>` on the container."""
	import boto3

	ssm = boto3.client("ssm", region_name=AWS_REGION)
	cmds = [
		f"BACKEND=$(docker ps --filter name={BACKEND_CONTAINER_FILTER} --format '{{{{.ID}}}}' | head -1)",
		f"docker exec $BACKEND bench --site hq.bebang.ph run-tests --module hrms.tests.{module} 2>&1 || true",
	]
	r = ssm.send_command(
		InstanceIds=[INSTANCE_ID],
		DocumentName="AWS-RunShellScript",
		Parameters={"commands": cmds, "executionTimeout": [str(timeout)]},
	)
	cid = r["Command"]["CommandId"]
	print(f"  CommandId: {cid}", file=sys.stderr)
	deadline = time.time() + timeout + 30
	while time.time() < deadline:
		time.sleep(5)
		inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
		if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
			out = inv.get("StandardOutputContent", "")
			err = inv.get("StandardErrorContent", "")
			return {
				"status": inv["Status"],
				"stdout": out,
				"stderr": err,
				"exit_code": inv.get("ResponseCode"),
			}
	return {"status": "TIMEOUT"}


def parse_unittest_summary(stdout: str) -> dict:
	"""Extract OK / FAIL / errors counts from unittest output."""
	import re

	summary = {"ran": None, "ok": False, "failures": 0, "errors": 0, "skipped": 0}
	m = re.search(r"Ran (\d+) tests? in", stdout)
	if m:
		summary["ran"] = int(m.group(1))
	summary["ok"] = bool(re.search(r"^OK\b", stdout, re.MULTILINE)) or stdout.endswith("OK\n")
	m = re.search(r"FAILED \(.*?failures=(\d+)", stdout)
	if m:
		summary["failures"] = int(m.group(1))
	m = re.search(r"FAILED \(.*?errors=(\d+)", stdout)
	if m:
		summary["errors"] = int(m.group(1))
	m = re.search(r"FAILED \(.*?skipped=(\d+)", stdout)
	if m:
		summary["skipped"] = int(m.group(1))
	return summary


def main() -> int:
	OUT_DIR.mkdir(parents=True, exist_ok=True)
	modules = [
		"test_s231_atomicity",
		"test_s231_pricing_coupling",
		"test_s231_markup_coupling",
	]
	all_results = {}
	for module in modules:
		print(f"Running {module} ...")
		res = run_bench_test(module)
		raw_path = OUT_DIR / f"test_{module}.txt"
		raw_path.write_text(
			f"=== STDOUT ===\n{res.get('stdout', '')}\n\n=== STDERR ===\n{res.get('stderr', '')}",
			encoding="utf-8",
		)
		summary = parse_unittest_summary(res.get("stdout", "") + "\n" + res.get("stderr", ""))
		summary["ssm_status"] = res.get("status")
		summary["raw_log"] = str(raw_path)
		all_results[module] = summary
		ran = summary.get("ran")
		print(
			f"  {module}: ssm={res.get('status')} ran={ran} ok={summary['ok']} "
			f"failures={summary['failures']} errors={summary['errors']}"
		)

	combined_path = OUT_DIR / "test_results.json"
	combined_path.write_text(json.dumps(all_results, indent=2))
	print(f"\nWrote {combined_path}")

	any_fail = any(
		not s.get("ok") or s.get("failures") or s.get("errors") for s in all_results.values()
	)
	return 1 if any_fail else 0


if __name__ == "__main__":
	sys.exit(main())
