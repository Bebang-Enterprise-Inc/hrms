"""S168 Phase 0.3 — Audit BKI Sales Taxes and Charges Templates.

Lists every Sales Taxes and Charges Template for Bebang Kitchen Inc. and dumps
the row structure for any candidate "BKI Output VAT 12% Sales" template so
Phase 5.2 knows whether to create it or reuse it.
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

COMPANY = "Bebang Kitchen Inc."
templates = frappe.db.sql(
    """SELECT name, title, disabled, is_default
       FROM `tabSales Taxes and Charges Template`
       WHERE company=%s
       ORDER BY name""",
    (COMPANY,),
    as_dict=True,
)
detail = []
for t in templates:
    rows = frappe.db.sql(
        """SELECT charge_type, account_head, rate, description, included_in_print_rate
           FROM `tabSales Taxes and Charges`
           WHERE parent=%s
           ORDER BY idx""",
        (t["name"],),
        as_dict=True,
    )
    detail.append({"template": t, "rows": rows})

result = {
    "company": COMPANY,
    "template_count": len(templates),
    "templates": detail,
    "candidate_match": [
        d for d in detail
        if "VAT" in (d["template"]["title"] or "").upper()
        or "OUTPUT" in (d["template"]["title"] or "").upper()
    ],
}
print("S168_VAT_TEMPLATE_BEGIN")
print(json.dumps(result, default=str))
print("S168_VAT_TEMPLATE_END")
'''


def main() -> int:
	encoded = base64.b64encode(INNER_SCRIPT.encode()).decode()
	commands = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		"if [ -z \"$BACKEND\" ]; then echo 'ERROR: no frappe_backend container'; exit 2; fi",
		f"echo '{encoded}' | base64 -d > /tmp/s168_vat_template.py",
		"docker cp /tmp/s168_vat_template.py $BACKEND:/tmp/s168_vat_template.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s168_vat_template.py",
	]
	ssm = boto3.client("ssm", region_name=REGION)
	print("Sending SSM command (s168_audit_vat_template)...", flush=True)
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
			if "S168_VAT_TEMPLATE_BEGIN" not in stdout:
				print("STDOUT:\n" + stdout[-4000:])
				print("STDERR:\n" + stderr[-2000:])
				return 2
			begin = stdout.index("S168_VAT_TEMPLATE_BEGIN") + len("S168_VAT_TEMPLATE_BEGIN")
			end = stdout.index("S168_VAT_TEMPLATE_END")
			report = json.loads(stdout[begin:end].strip())
			out = os.path.join(OUTPUT_DIR, "vat_template_audit.json")
			with open(out, "w", encoding="utf-8") as f:
				json.dump(report, f, indent=2, default=str)
			print(f"  wrote {out}")
			return 0
	print("Timed out waiting for command")
	return 3


if __name__ == "__main__":
	sys.exit(main())
