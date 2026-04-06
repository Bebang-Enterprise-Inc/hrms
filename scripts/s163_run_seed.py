"""Run scripts/s163_seed_item_groups.py on the Frappe container via SSM.

Captures output between S163_SEED_REPORT_BEGIN/END markers and writes it
to output/s163/seed_evidence.json.
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
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(HERE, "s163_seed_item_groups.py")
OUTPUT_DIR = os.path.join(os.path.dirname(HERE), "output", "s163")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main() -> int:
	with open(SCRIPT_PATH, encoding="utf-8") as f:
		encoded = base64.b64encode(f.read().encode()).decode()
	commands = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		"if [ -z \"$BACKEND\" ]; then echo 'ERROR: no frappe_backend container'; exit 2; fi",
		f"echo '{encoded}' | base64 -d > /tmp/s163_seed.py",
		"docker cp /tmp/s163_seed.py $BACKEND:/tmp/s163_seed.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s163_seed.py",
	]
	ssm = boto3.client("ssm", region_name=REGION)
	print("Sending SSM command...", flush=True)
	resp = ssm.send_command(
		InstanceIds=[INSTANCE_ID],
		DocumentName="AWS-RunShellScript",
		Parameters={"commands": commands, "executionTimeout": ["600"]},
	)
	command_id = resp["Command"]["CommandId"]
	print(f"Command ID: {command_id}", flush=True)

	for _ in range(40):
		time.sleep(8)
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
				print(stderr[-2000:])
			if "S163_SEED_REPORT_BEGIN" not in stdout:
				return 2
			begin = stdout.index("S163_SEED_REPORT_BEGIN") + len("S163_SEED_REPORT_BEGIN")
			end = stdout.index("S163_SEED_REPORT_END")
			report = json.loads(stdout[begin:end].strip())
			with open(os.path.join(OUTPUT_DIR, "seed_evidence.json"), "w", encoding="utf-8") as f:
				json.dump(report, f, indent=2, default=str)
			print(f"\nWrote output/s163/seed_evidence.json")
			return 0 if report.get("ok") else 1
	print("Timed out")
	return 3


if __name__ == "__main__":
	sys.exit(main())
