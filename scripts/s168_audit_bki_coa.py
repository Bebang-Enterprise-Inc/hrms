"""S168 Phase 0.6 — Audit BKI Chart of Accounts.

Queries tabAccount for the BKI company over SSM and verifies the existence
(or absence) of the S168 critical accounts:

  * 2102205 OUTPUT VAT PAYABLE       (ICT-009 — current Output VAT account)
  * 4000100 WHOLESALE / B2B SALES    (ICT-008 Option C — parent group)
  * 4000101 SALES - BKI TO STORES    (ICT-008 Option C — posting child)

Writes results to output/s168/bki_coa_audit.json. Phase 1 must NOT run if
2102205 OUTPUT VAT PAYABLE is missing for BKI.

Pattern follows scripts/s163_run_ssm_ops.py.
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
TARGETS = {
    "output_vat_2102205": {"account_number": "2102205", "label": "OUTPUT VAT PAYABLE"},
    "wholesale_b2b_4000100": {"account_number": "4000100", "label": "WHOLESALE / B2B SALES"},
    "sales_bki_to_stores_4000101": {"account_number": "4000101", "label": "SALES - BKI TO STORES"},
    "legacy_vat_2103100": {"account_number": "2103100", "label": "VAT - OUTPUT (legacy)"},
    "royalty_4000003": {"account_number": "4000003", "label": "ROYALTY INCOME (collision check)"},
}

result = {"company": COMPANY, "targets": {}, "sales_group_children": [], "vat_accounts": []}

for key, t in TARGETS.items():
    rows = frappe.db.sql(
        """SELECT name, account_name, account_number, parent_account, is_group, root_type, account_type
           FROM `tabAccount`
           WHERE company=%s AND account_number=%s""",
        (COMPANY, t["account_number"]),
        as_dict=True,
    )
    result["targets"][key] = {
        "account_number": t["account_number"],
        "expected_label": t["label"],
        "exists": bool(rows),
        "matches": rows,
    }

# List children under 4000000 SALES group (if it exists)
sales_group = frappe.db.sql(
    """SELECT name FROM `tabAccount`
       WHERE company=%s AND account_number=%s AND is_group=1""",
    (COMPANY, "4000000"),
    as_dict=True,
)
if sales_group:
    result["sales_group_root"] = sales_group[0]["name"]
    result["sales_group_children"] = frappe.db.sql(
        """SELECT name, account_number, account_name, is_group
           FROM `tabAccount`
           WHERE company=%s AND parent_account=%s
           ORDER BY account_number""",
        (COMPANY, sales_group[0]["name"]),
        as_dict=True,
    )

# All VAT accounts for visibility
result["vat_accounts"] = frappe.db.sql(
    """SELECT name, account_number, account_name, parent_account
       FROM `tabAccount`
       WHERE company=%s AND (account_name LIKE '%%VAT%%' OR account_number LIKE '21022%%' OR account_number LIKE '21031%%')
       ORDER BY account_number""",
    (COMPANY,),
    as_dict=True,
)

# Phase 1 gate
result["phase1_blocked"] = not result["targets"]["output_vat_2102205"]["exists"]
result["ok"] = not result["phase1_blocked"]

print("S168_COA_AUDIT_BEGIN")
print(json.dumps(result, default=str))
print("S168_COA_AUDIT_END")
'''


def main() -> int:
	encoded = base64.b64encode(INNER_SCRIPT.encode()).decode()
	commands = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		"if [ -z \"$BACKEND\" ]; then echo 'ERROR: no frappe_backend container'; exit 2; fi",
		f"echo '{encoded}' | base64 -d > /tmp/s168_coa_audit.py",
		"docker cp /tmp/s168_coa_audit.py $BACKEND:/tmp/s168_coa_audit.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s168_coa_audit.py",
	]
	ssm = boto3.client("ssm", region_name=REGION)
	print("Sending SSM command (s168_audit_bki_coa)...", flush=True)
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
			if "S168_COA_AUDIT_BEGIN" not in stdout or "S168_COA_AUDIT_END" not in stdout:
				print("STDOUT:\n" + stdout[-4000:])
				print("STDERR:\n" + stderr[-2000:])
				print("FATAL: report markers not found")
				return 2
			begin = stdout.index("S168_COA_AUDIT_BEGIN") + len("S168_COA_AUDIT_BEGIN")
			end = stdout.index("S168_COA_AUDIT_END")
			report = json.loads(stdout[begin:end].strip())
			out = os.path.join(OUTPUT_DIR, "bki_coa_audit.json")
			with open(out, "w", encoding="utf-8") as f:
				json.dump(report, f, indent=2, default=str)
			print(f"  wrote {out}")
			return 0 if report.get("ok") else 1
	print("Timed out waiting for command")
	return 3


if __name__ == "__main__":
	sys.exit(main())
