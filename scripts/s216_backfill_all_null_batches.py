#!/usr/bin/env python3
"""S216 Phase 1b — broader backfill: assign BACKFILL-* batches to ALL NULL-batch
stock across every warehouse (not just BKI). Reuses S213's SLE-UPDATE pattern.

Emits output/l3/s216/backfill_all_run.json
"""
from __future__ import annotations
import base64, gzip, json, pathlib, sys, time
from datetime import datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "output" / "l3" / "s216"
AUDIT = OUT_DIR / "batch_audit_all.json"
OUT = OUT_DIR / "backfill_all_run.json"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


def _warehouse_short(wh_name: str) -> str:
	import re
	s = wh_name.replace(" - BKI", "").strip()
	s = re.sub(r"[\u2013\u2014]", "-", s)
	s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
	return s.upper()[:40]


def _build_script(tuples, today):
	return f'''
import json, traceback, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

TUPLES = {json.dumps(tuples)}
TODAY = {json.dumps(today)}

ok, err = 0, 0
errors = []
for t in TUPLES:
    item = t["item_code"]; wh = t["warehouse"]; batch_id = t["batch_id"]
    try:
        frappe.db.savepoint("s216_bf")
        if not frappe.db.exists("Batch", batch_id):
            b = frappe.new_doc("Batch")
            b.batch_id = batch_id
            b.item = item
            b.description = f"S216 backfill — NULL-batch cleanup at {{wh}} on {{TODAY}}"
            b.insert(ignore_permissions=True)
        frappe.db.sql(
            """UPDATE `tabStock Ledger Entry`
               SET batch_no=%s, modified=NOW()
               WHERE item_code=%s AND warehouse=%s AND batch_no IS NULL AND docstatus=1""",
            (batch_id, item, wh),
        )
        new_qty = frappe.db.sql(
            """SELECT COALESCE(SUM(actual_qty),0) FROM `tabStock Ledger Entry`
               WHERE batch_no=%s AND docstatus=1""",
            (batch_id,),
        )[0][0]
        frappe.db.set_value("Batch", batch_id, "batch_qty", float(new_qty))
        frappe.db.release_savepoint("s216_bf")
        frappe.db.commit()
        ok += 1
    except Exception as e:
        try: frappe.db.rollback(save_point="s216_bf")
        except Exception: pass
        err += 1
        errors.append({{"item": item, "wh": wh, "err": repr(e)[:200]}})

payload = {{"ok": ok, "err": err, "errors": errors[:20], "total": len(TUPLES)}}
compressed = gzip.compress(json.dumps(payload, default=str).encode())
print("__B64_START__")
print(base64.b64encode(compressed).decode())
print("__B64_END__")
frappe.destroy()
'''


def run(script, timeout=600):
	import boto3
	ssm = boto3.client("ssm", region_name=AWS_REGION)
	enc = base64.b64encode(script.encode()).decode()
	cmds = [
		"BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
		f"echo '{enc}' | base64 -d > /tmp/s216_bf.py",
		"docker cp /tmp/s216_bf.py $BACKEND:/tmp/s216_bf.py",
		"docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s216_bf.py",
	]
	r = ssm.send_command(InstanceIds=[INSTANCE_ID], DocumentName="AWS-RunShellScript",
		Parameters={"commands": cmds, "executionTimeout": [str(timeout)]})
	cid = r["Command"]["CommandId"]
	print(f"CommandId: {cid}")
	deadline = time.time() + timeout + 30
	while time.time() < deadline:
		time.sleep(5)
		inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
		if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
			out = inv.get("StandardOutputContent", "")
			if inv["Status"] != "Success":
				sys.stderr.write(inv.get("StandardErrorContent", ""))
				raise RuntimeError(inv["Status"])
			return out
	raise TimeoutError()


def main() -> int:
	if not AUDIT.exists():
		sys.stderr.write(f"{AUDIT} missing — run s216_audit_all_warehouses.py first\n")
		return 1
	data = json.loads(AUDIT.read_text(encoding="utf-8"))
	tuples = data.get("tuples") or []
	if not tuples:
		print("No tuples — nothing to do.")
		return 0

	today = datetime.utcnow().strftime("%Y%m%d")
	enriched = []
	for t in tuples:
		short = _warehouse_short(t["warehouse"])
		batch_id = f"BACKFILL-{today}-{t['item_code']}-{short}"[:140]  # Frappe name limit ~140
		enriched.append({
			"item_code": t["item_code"],
			"warehouse": t["warehouse"],
			"batch_id": batch_id,
		})
	print(f"About to backfill {len(enriched)} tuples")

	# Chunk to avoid any single SSM script being too large
	CHUNK = 150
	total_ok = 0; total_err = 0; all_errs = []
	for i in range(0, len(enriched), CHUNK):
		chunk = enriched[i:i+CHUNK]
		print(f"  Chunk {i//CHUNK + 1} — {len(chunk)} tuples")
		out = run(_build_script(chunk, today))
		s = out.find("__B64_START__"); e = out.find("__B64_END__")
		b64 = out[s+len("__B64_START__"):e].strip()
		p = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
		total_ok += p["ok"]; total_err += p["err"]
		all_errs.extend(p.get("errors") or [])

	report = {"total": len(enriched), "ok": total_ok, "err": total_err, "errors": all_errs[:30]}
	OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
	print(f"Wrote {OUT}")
	print(f"Total: ok={total_ok} err={total_err}")
	return 0 if total_err == 0 else 1


if __name__ == "__main__":
	sys.exit(main())
