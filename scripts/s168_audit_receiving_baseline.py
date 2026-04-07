"""S168 Phase 0.4 — BEI Store Receiving baseline snapshot.

Counts BEI Store Receiving records by status and how many already have a
stock_entry link. Used as the before-snapshot for Phase 4 verification.
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
OUTPUT_DIR = os.path.join(
	os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
	"output",
	"s168",
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

INNER_SCRIPT = r'''
from __future__ import annotations
import json, os
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
]:
    os.makedirs(d, exist_ok=True)
import frappe  # type: ignore
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

result = {}
result["total"] = frappe.db.count("BEI Store Receiving")
result["by_status"] = frappe.db.sql(
    """SELECT status, COUNT(*) AS n
       FROM `tabBEI Store Receiving`
       GROUP BY status
       ORDER BY n DESC""",
    as_dict=True,
)
# stock_entry link presence (only if column exists)
try:
    result["with_stock_entry"] = frappe.db.sql(
        """SELECT COUNT(*) AS n FROM `tabBEI Store Receiving`
           WHERE stock_entry IS NOT NULL AND stock_entry != ''""",
        as_dict=True,
    )[0]["n"]
except Exception as e:
    result["with_stock_entry_error"] = str(e)

# Existing custom fields on BEI Store Receiving (so Phase 1 knows what's there)
result["existing_custom_fields"] = frappe.db.sql(
    """SELECT fieldname, fieldtype, options
       FROM `tabCustom Field`
       WHERE dt='BEI Store Receiving'
       ORDER BY idx""",
    as_dict=True,
)
print("S168_RECEIVING_BASELINE_BEGIN")
print(json.dumps(result, default=str))
print("S168_RECEIVING_BASELINE_END")
'''


def main() -> int:
	encoded = base64.b64encode(INNER_SCRIPT.encode()).decode()
	commands = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		"if [ -z \"$BACKEND\" ]; then echo 'ERROR: no frappe_backend container'; exit 2; fi",
		f"echo '{encoded}' | base64 -d > /tmp/s168_receiving_baseline.py",
		"docker cp /tmp/s168_receiving_baseline.py $BACKEND:/tmp/s168_receiving_baseline.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s168_receiving_baseline.py",
	]
	ssm = boto3.client("ssm", region_name=REGION)
	print("Sending SSM command (s168_audit_receiving_baseline)...", flush=True)
	resp = ssm.send_command(
		InstanceIds=[INSTANCE_ID],
		DocumentName="AWS-RunShellScript",
		Parameters={"commands": commands, "executionTimeout": ["600"]},
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
			if "S168_RECEIVING_BASELINE_BEGIN" not in stdout:
				print("STDOUT:\n" + stdout[-4000:])
				print("STDERR:\n" + stderr[-2000:])
				return 2
			begin = stdout.index("S168_RECEIVING_BASELINE_BEGIN") + len("S168_RECEIVING_BASELINE_BEGIN")
			end = stdout.index("S168_RECEIVING_BASELINE_END")
			report = json.loads(stdout[begin:end].strip())
			out = os.path.join(OUTPUT_DIR, "receiving_flow_baseline.json")
			with open(out, "w", encoding="utf-8") as f:
				json.dump(report, f, indent=2, default=str)
			print(f"  wrote {out}")
			return 0
	print("Timed out waiting for command")
	return 3


if __name__ == "__main__":
	sys.exit(main())
