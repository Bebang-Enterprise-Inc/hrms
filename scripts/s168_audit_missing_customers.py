"""S168 Phase 0.2 — Audit missing BKI Customer records.

For every active row in the S037 store_buyer_entity_register, verify that a
matching ERPNext Customer exists (cross-company name match per Amendment 14 —
no company filter). Writes output/s168/missing_customers_audit.json.
"""

from __future__ import annotations

import base64
import csv
import json
import os
import sys
import time

import boto3

INSTANCE_ID = "i-026b7477d27bd46d6"
REGION = "ap-southeast-1"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTER_CSV = os.path.join(
	REPO_ROOT,
	"data",
	"_CLEANROOM",
	"2026-03-12-s037-store-buyer-entity-register",
	"store_buyer_entity_register_2026-03-12.csv",
)
OUTPUT_DIR = os.path.join(REPO_ROOT, "output", "s168")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ACTIVE_BILLING_STATUSES = {
	"confirmed_legal_entity",
	"entity_confirmed_store_type_pending",
}


def load_register() -> list[dict]:
	if not os.path.exists(REGISTER_CSV):
		raise SystemExit(f"S037 register not found at {REGISTER_CSV}")
	with open(REGISTER_CSV, encoding="utf-8") as f:
		return list(csv.DictReader(f))


def build_inner_script(buyer_names: list[str]) -> str:
	return f'''
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

names = {json.dumps(buyer_names)}
result = {{"checked": len(names), "existing": [], "missing": []}}
for n in names:
    row = frappe.db.get_value("Customer", {{"customer_name": n}}, ["name", "customer_name"], as_dict=True)
    if row:
        result["existing"].append(row)
    else:
        result["missing"].append(n)
result["existing_count"] = len(result["existing"])
result["missing_count"] = len(result["missing"])
print("S168_MISSING_CUSTOMERS_BEGIN")
print(json.dumps(result, default=str))
print("S168_MISSING_CUSTOMERS_END")
'''


def main() -> int:
	rows = load_register()
	active_rows = [r for r in rows if (r.get("buyer_entity_status") or "").strip() in ACTIVE_BILLING_STATUSES]
	unique_buyers = sorted({r["buyer_entity_name"].strip() for r in active_rows if r.get("buyer_entity_name")})
	print(f"Register rows total: {len(rows)}")
	print(f"Active rows (billing-eligible status): {len(active_rows)}")
	print(f"Unique buyer entities: {len(unique_buyers)}")

	inner = build_inner_script(unique_buyers)
	encoded = base64.b64encode(inner.encode()).decode()
	commands = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		"if [ -z \"$BACKEND\" ]; then echo 'ERROR: no frappe_backend container'; exit 2; fi",
		f"echo '{encoded}' | base64 -d > /tmp/s168_missing_customers.py",
		"docker cp /tmp/s168_missing_customers.py $BACKEND:/tmp/s168_missing_customers.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s168_missing_customers.py",
	]
	ssm = boto3.client("ssm", region_name=REGION)
	print("Sending SSM command (s168_audit_missing_customers)...", flush=True)
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
			if "S168_MISSING_CUSTOMERS_BEGIN" not in stdout:
				print("STDOUT:\n" + stdout[-4000:])
				print("STDERR:\n" + stderr[-2000:])
				return 2
			begin = stdout.index("S168_MISSING_CUSTOMERS_BEGIN") + len("S168_MISSING_CUSTOMERS_BEGIN")
			end = stdout.index("S168_MISSING_CUSTOMERS_END")
			ssm_report = json.loads(stdout[begin:end].strip())
			full = {
				"register_csv": REGISTER_CSV,
				"register_total_rows": len(rows),
				"register_active_rows": len(active_rows),
				"unique_buyer_entities": len(unique_buyers),
				"buyer_entities": unique_buyers,
				"frappe_lookup": ssm_report,
			}
			out = os.path.join(OUTPUT_DIR, "missing_customers_audit.json")
			with open(out, "w", encoding="utf-8") as f:
				json.dump(full, f, indent=2, default=str)
			print(f"  wrote {out}")
			return 0
	print("Timed out waiting for command")
	return 3


if __name__ == "__main__":
	sys.exit(main())
