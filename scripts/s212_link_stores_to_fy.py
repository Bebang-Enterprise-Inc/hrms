#!/usr/bin/env python3
"""S212 Phase 3 — link all 49 per-store Companies to Fiscal Year 2026.

Reads every active per-store Company (entity_category='Store', not
Permanently Closed / Dormant) and appends it to `tabFiscal Year`
name='2026' `companies` child table if missing. Idempotent — re-running
adds nothing if all 49 are already linked.

Saves fy with ignore_permissions=True and an explicit commit so the
write is visible to subsequent SSM probes.

Emits:
  - output/l3/s212/fy_2026_after.json  { total_stores, added, already_linked, fy_2026_companies }

Why: S209 variance discovered that Stock Entries / Sales Invoices /
Journal Entries posted against per-store Companies silently fail when
the Company isn't in that year's Fiscal Year `companies` child table.
S209 only linked BKI + BEBANG ENTERPRISE (pre-sprint) + SM TANZA +
AYALA VERMOSA (manually during V1 seeding); the remaining 45 needed a
one-off linker before S212's full sweep.

Follows the S209 SSM + gzip+base64 pattern.
"""
from __future__ import annotations
import base64
import gzip
import json
import pathlib
import subprocess
import sys
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "output" / "l3" / "s212"
OUT_DIR.mkdir(parents=True, exist_ok=True)

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"


SCRIPT = '''
import os
for d in ["/home/frappe/logs", "/home/frappe/frappe-bench/logs",
          "/home/frappe/frappe-bench/hq.bebang.ph/logs",
          "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs"]:
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass

import json, base64, gzip
import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

# Active per-store Companies
stores = frappe.db.sql(
    """SELECT name FROM `tabCompany`
       WHERE entity_category = 'Store'
         AND (operational_status IS NULL OR operational_status NOT IN ('Permanently Closed','Dormant'))
       ORDER BY name""",
    as_dict=True,
)

# Load Fiscal Year 2026 doc (append operates on the parent doc, which saves both parent + child in one transaction)
fy = frappe.get_doc("Fiscal Year", "2026")
existing = {c.company for c in (fy.companies or [])}

added: list[str] = []
for s in stores:
    cname = s["name"]
    if cname and cname not in existing:
        fy.append("companies", {"company": cname})
        added.append(cname)
        existing.add(cname)  # keep local set in sync for edge case dupes in query

if added:
    fy.save(ignore_permissions=True)
    frappe.db.commit()

# Re-read after save so the emitted list reflects on-disk truth
fy_final = frappe.db.sql(
    "SELECT company FROM `tabFiscal Year Company` WHERE parent = '2026' ORDER BY company",
    as_dict=True,
)

payload = {
    "total_stores": len(stores),
    "added": len(added),
    "added_names": added,
    "already_linked": len(stores) - len(added),
    "fy_2026_companies_after": [r["company"] for r in fy_final],
}
compressed = gzip.compress(json.dumps(payload).encode())
print("__FY_B64_START__")
print(base64.b64encode(compressed).decode())
print("__FY_B64_END__")

frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 180) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s212_fy_link.py",
        "docker cp /tmp/s212_fy_link.py $BACKEND:/tmp/s212_fy_link.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s212_fy_link.py",
    ]
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": [str(timeout)]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}")
    deadline = time.time() + timeout + 30
    while time.time() < deadline:
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            err = inv.get("StandardErrorContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(f"[SSM {inv['Status']}]\n{err}\n")
                raise RuntimeError(f"SSM command failed: {inv['Status']}")
            return out
    raise TimeoutError(f"SSM command {cid} did not complete")


def extract_between(haystack: str, start: str, end: str) -> str:
    s = haystack.find(start)
    e = haystack.find(end)
    if s < 0 or e < 0:
        raise RuntimeError(f"Could not find markers {start}/{end}")
    return haystack[s + len(start):e].strip()


def main() -> int:
    out = run_in_container(SCRIPT)
    b64 = extract_between(out, "__FY_B64_START__", "__FY_B64_END__")
    payload = json.loads(gzip.decompress(base64.b64decode(b64)).decode())
    dest = OUT_DIR / "fy_2026_after.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[S212] Wrote {dest}")
    print(f"[S212] Store Companies: {payload['total_stores']}")
    print(f"[S212] Added to FY 2026: {payload['added']}")
    print(f"[S212] Already linked: {payload['already_linked']}")
    print(f"[S212] FY 2026 total after: {len(payload['fy_2026_companies_after'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
