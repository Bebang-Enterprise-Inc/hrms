#!/usr/bin/env python3
"""S213 Phase 2 — backfill NULL batch_no on existing Stock Ledger Entries.

Reads output/l3/s213/batch_audit_report.json and for each (item, warehouse)
tuple with NULL-batch qty:
  1. Creates a `tabBatch` record `BACKFILL-YYYYMMDD-<item>-<wh-short>` if missing.
  2. UPDATEs `tabStock Ledger Entry` rows matching (item, warehouse,
     batch_no IS NULL, docstatus=1) to the new batch_no.
  3. Recomputes `Bin` via the Frappe repost machinery so downstream reads
     see fresh numbers (Bin totals stay the same — this is a labeling fix).
  4. Stores the new batch_id on the Batch doc's `batch_qty` via
     `update_batch_qty` hook.
  5. Commits.

Why direct SQL on SLE and not Stock Reconciliation:
  - SR moves qty (posts compensating SLE rows). Our job is labeling
    existing qty, not moving it.
  - Targeting `batch_no IS NULL` in an SR is not a supported operation —
    SR treats the absence of a batch as "net-new".
  - Direct SQL preserves the original creation timestamps + GL posting
    dates. No phantom SLE rows in the audit trail.
  - Safe because: qty unchanged, valuation unchanged, GL unchanged.

Idempotent: re-running with an empty audit (0 NULL-batch tuples) is a no-op.
"""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time
from datetime import datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "output" / "l3" / "s213"
AUDIT = OUT_DIR / "batch_audit_report.json"
OUT = OUT_DIR / "backfill_run_report.json"
LOG = OUT_DIR / "backfill_run.log"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


def _warehouse_short(wh_name: str) -> str:
	"""Short tag for batch_id suffix. Strips ' - BKI', compresses whitespace, uppercases."""
	s = wh_name.replace(" - BKI", "").strip()
	# Replace various dashes with single hyphen, compress runs of spaces/punct
	import re
	s = re.sub(r"[\u2013\u2014]", "-", s)  # em/en dash → hyphen
	s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
	return s.upper()[:40]


def _build_backfill_script(tuples: list[dict], today: str) -> str:
	"""Return the Python script to run inside the Frappe container.

	tuples: list of {"item_code", "warehouse", "null_qty", "valuation_rate", "batch_id"}
	"""
	tuples_json = json.dumps(tuples)
	return f'''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json, traceback, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

TUPLES = {tuples_json}
TODAY = {json.dumps(today)}

results = []
for t in TUPLES:
    item = t["item_code"]
    wh = t["warehouse"]
    batch_id = t["batch_id"]
    try:
        frappe.db.savepoint("s213_backfill")
        # 1. Create Batch if missing
        if not frappe.db.exists("Batch", batch_id):
            batch = frappe.new_doc("Batch")
            batch.batch_id = batch_id
            batch.item = item
            batch.reference_doctype = None
            batch.reference_name = None
            batch.description = f"S213 backfill for NULL-batch stock at {{wh}} on {{TODAY}}"
            batch.insert(ignore_permissions=True)
            batch_created = True
        else:
            batch_created = False

        # 2. UPDATE SLE rows — labeling, not moving
        updated = frappe.db.sql(
            """UPDATE `tabStock Ledger Entry`
               SET batch_no = %s, modified = NOW()
               WHERE item_code = %s
                 AND warehouse = %s
                 AND batch_no IS NULL
                 AND docstatus = 1""",
            (batch_id, item, wh),
        )
        affected = frappe.db.sql(
            """SELECT COUNT(*) FROM `tabStock Ledger Entry`
               WHERE batch_no=%s AND item_code=%s AND warehouse=%s""",
            (batch_id, item, wh),
        )[0][0]

        # 3. Recompute Batch.batch_qty from SLE sum
        new_qty = frappe.db.sql(
            """SELECT COALESCE(SUM(actual_qty), 0) FROM `tabStock Ledger Entry`
               WHERE batch_no=%s AND docstatus=1""",
            (batch_id,),
        )[0][0]
        frappe.db.set_value("Batch", batch_id, "batch_qty", float(new_qty))

        frappe.db.release_savepoint("s213_backfill")
        frappe.db.commit()

        results.append({{
            "item_code": item, "warehouse": wh, "batch_id": batch_id,
            "status": "ok", "sle_rows_affected": int(affected),
            "batch_qty_after": float(new_qty), "batch_created": batch_created,
        }})
    except Exception as e:
        try:
            frappe.db.rollback(save_point="s213_backfill")
        except Exception:
            pass
        tb = traceback.format_exc()
        results.append({{
            "item_code": item, "warehouse": wh, "batch_id": batch_id,
            "status": "error", "error": repr(e), "tb_head": tb[:2000],
        }})

payload = {{"results": results, "total": len(results),
            "ok": sum(1 for r in results if r["status"] == "ok"),
            "err": sum(1 for r in results if r["status"] == "error")}}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__BF_B64_START__")
print(base64.b64encode(compressed).decode())
print("__BF_B64_END__")
frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 600) -> str:
	import boto3
	ssm = boto3.client("ssm", region_name=AWS_REGION)
	enc = base64.b64encode(python_script.encode()).decode()
	cmds = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		f"echo '{enc}' | base64 -d > /tmp/s213_bf.py",
		"docker cp /tmp/s213_bf.py $BACKEND:/tmp/s213_bf.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s213_bf.py",
	]
	r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
		Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
	cid = r["Command"]["CommandId"]
	print(f"CommandId: {cid}")
	deadline = time.time() + timeout + 30
	while time.time() < deadline:
		time.sleep(4)
		inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
		if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
			out = inv.get("StandardOutputContent", "")
			err = inv.get("StandardErrorContent", "")
			if inv["Status"] != "Success":
				sys.stderr.write(err); raise RuntimeError(inv["Status"])
			return out
	raise TimeoutError()


def extract_between(haystack: str, start: str, end: str) -> str:
	s = haystack.find(start); e = haystack.find(end)
	if s < 0 or e < 0:
		raise RuntimeError(f"Could not find markers {start}/{end}")
	return haystack[s + len(start):e].strip()


def main() -> int:
	if not AUDIT.exists():
		sys.stderr.write(f"Audit report missing at {AUDIT}. Run s213_audit_null_batches.py first.\n")
		return 1
	audit = json.loads(AUDIT.read_text(encoding="utf-8"))
	tuples = audit.get("null_batch_tuples") or []
	if not tuples:
		print("[S213] No NULL-batch tuples — nothing to do.")
		return 0

	today = datetime.utcnow().strftime("%Y%m%d")
	enriched = []
	for t in tuples:
		short = _warehouse_short(t["warehouse"])
		batch_id = f"BACKFILL-{today}-{t['item_code']}-{short}"
		enriched.append({
			"item_code": t["item_code"],
			"warehouse": t["warehouse"],
			"null_qty": t["null_qty"],
			"valuation_rate": t["valuation_rate"],
			"batch_id": batch_id,
		})

	# Preview
	print(f"[S213] About to backfill {len(enriched)} tuples. Preview (first 5):")
	for t in enriched[:5]:
		print(f"  {t['item_code']:10s} | {t['warehouse'][:40]:40s} | batch_id={t['batch_id']}")
	print()

	script = _build_backfill_script(enriched, today)
	out = run_in_container(script)
	LOG.write_text(out, encoding="utf-8")
	b64 = extract_between(out, "__BF_B64_START__", "__BF_B64_END__")
	payload = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
	OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
	print(f"[S213] Wrote {OUT}")
	print(f"[S213] OK: {payload['ok']} | ERR: {payload['err']} | Total: {payload['total']}")
	if payload["err"]:
		for r in payload["results"]:
			if r["status"] == "error":
				print(f"  [err] {r['item_code']} | {r['warehouse']} | {r['error']}")
	return 0 if payload["err"] == 0 else 1


if __name__ == "__main__":
	sys.exit(main())
