"""Drive s163_ssm_ops.py on the Frappe container via AWS SSM, capture the
S163_SSM_REPORT JSON blob, and split it into evidence files under output/s163/.

Usage: python scripts/s163_run_ssm_ops.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s163_ssm_ops.py")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "s163")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main() -> int:
	with open(SCRIPT_PATH, encoding="utf-8") as f:
		script_src = f.read()
	encoded = base64.b64encode(script_src.encode()).decode()

	commands = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		"if [ -z \"$BACKEND\" ]; then echo 'ERROR: no frappe_backend container'; exit 2; fi",
		f"echo '{encoded}' | base64 -d > /tmp/s163_ssm_ops.py",
		"docker cp /tmp/s163_ssm_ops.py $BACKEND:/tmp/s163_ssm_ops.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s163_ssm_ops.py",
	]

	ssm = boto3.client("ssm", region_name=REGION)
	print("Sending SSM command...", flush=True)
	resp = ssm.send_command(
		InstanceIds=[INSTANCE_ID],
		DocumentName="AWS-RunShellScript",
		Parameters={"commands": commands, "executionTimeout": ["900"]},
	)
	command_id = resp["Command"]["CommandId"]
	print(f"Command ID: {command_id}", flush=True)

	for _ in range(60):
		time.sleep(10)
		inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=INSTANCE_ID)
		status = inv["Status"]
		print(f"  status: {status}", flush=True)
		if status in {"Success", "Failed", "Cancelled", "TimedOut"}:
			stdout = inv.get("StandardOutputContent") or ""
			stderr = inv.get("StandardErrorContent") or ""
			print("=" * 70)
			print("STDOUT:")
			print(stdout[-6000:])
			if stderr:
				print("STDERR:")
				print(stderr[-3000:])
			if "S163_SSM_REPORT_BEGIN" not in stdout or "S163_SSM_REPORT_END" not in stdout:
				print("\nFATAL: report markers not found")
				return 2
			begin = stdout.index("S163_SSM_REPORT_BEGIN") + len("S163_SSM_REPORT_BEGIN")
			end = stdout.index("S163_SSM_REPORT_END")
			payload = stdout[begin:end].strip()
			report = json.loads(payload)

			# Write full report
			with open(os.path.join(OUTPUT_DIR, "ssm_ops_report.json"), "w", encoding="utf-8") as f:
				json.dump(report, f, indent=2, default=str)

			# Section → file mapping
			write = {
				"migration_evidence.json": {
					"sprint": report["sprint"],
					"timestamp_utc": report["timestamp_utc"],
					"site": report["site"],
					"recipes": report.get("migration_recipes"),
					"policies": report.get("migration_policies"),
					"ok": bool(
						not report.get("migration_recipes", {}).get("errors")
						and not report.get("migration_policies", {}).get("errors")
					),
				},
				"manual_verification.json": {
					"sprint": report["sprint"],
					"timestamp_utc": report["timestamp_utc"],
					"results": report.get("manual_verification"),
				},
				"pipeline_parity_check.json": {
					"sprint": report["sprint"],
					"timestamp_utc": report["timestamp_utc"],
					"results": report.get("pipeline_parity_check"),
				},
			}
			for fname, body in write.items():
				with open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
					json.dump(body, f, indent=2, default=str)
				print(f"  wrote {fname}")

			# Merge in-flight audit into pre_migration_audit.json
			pre_path = os.path.join(OUTPUT_DIR, "pre_migration_audit.json")
			if os.path.exists(pre_path):
				with open(pre_path, encoding="utf-8") as f:
					pre = json.load(f)
			else:
				pre = {}
			pre["in_flight_orders_check"] = report.get("inflight_audit")
			pre["in_flight_orders_checked_at"] = report["timestamp_utc"]
			with open(pre_path, "w", encoding="utf-8") as f:
				json.dump(pre, f, indent=2, default=str)
			print(f"  updated pre_migration_audit.json with in-flight audit")

			return 0 if report.get("ok") else 1

	print("Timed out waiting for command")
	return 3


if __name__ == "__main__":
	sys.exit(main())
