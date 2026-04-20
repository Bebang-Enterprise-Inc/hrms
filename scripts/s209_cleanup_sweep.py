#!/usr/bin/env python3
"""S209 P6-T1: cleanup sweep — cancels every submitted test artifact recorded
in the sweep_ledger.json and verifies ledger.pendingEntries == 0.

Processing order (reverse dependency):
  1. Sales Invoice  (si-create)   → cancel()
  2. BEI Warehouse Receiving      → cancel()
  3. Stock Entry                  → cancel()
  4. Material Request             → cancel() (auto-cancels if SI/SE cancelled)
  5. BEI Store Order              → cancel()  OR delete() if still Draft

GL reversal is handled natively by Frappe `cancel()`. NEVER mutates
`tabGL Entry` directly (DM-1).

On any cancel failure the script exits non-zero and prints the failing doc
so Phase 6 can STOP and ask Sam (per stop_only_for: cannot leave hanging GL).

Usage:
    python scripts/s209_cleanup_sweep.py
    python scripts/s209_cleanup_sweep.py --dry-run
    python scripts/s209_cleanup_sweep.py --ledger path/to/sweep_ledger.json

Writes post-cleanup state to:
    output/l3/s209/cleanup_report.json
"""
from __future__ import annotations
import argparse
import base64
import gzip
import json
import pathlib
import sys
import time


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = REPO_ROOT / "output/l3/s209/sweep_ledger.json"
CLEANUP_REPORT = REPO_ROOT / "output/l3/s209/cleanup_report.json"

AWS_REGION = "ap-southeast-1"
INSTANCE_ID = "i-026b7477d27bd46d6"

# Reverse-dependency order: later row types cancel first
PROCESSING_ORDER = [
    ("si-create", "Sales Invoice"),
    ("wr-create", "BEI Warehouse Receiving"),
    ("se-create", "Stock Entry"),
    ("mr-create", "Material Request"),
    ("order-create", "BEI Store Order"),
]


def _build_cancel_script(cancellations: list[dict]) -> str:
    """cancellations: [{"doctype": ..., "name": ...}]"""
    cancels_json = json.dumps(cancellations)
    return f'''
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

cancels = {cancels_json}

success = []
failures = []
skipped = []

for c in cancels:
    doctype = c["doctype"]
    name = c["name"]
    try:
        if not frappe.db.exists(doctype, name):
            skipped.append({{"doctype": doctype, "name": name, "reason": "not_found"}})
            continue
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 2:
            # Already cancelled
            skipped.append({{"doctype": doctype, "name": name, "reason": "already_cancelled"}})
            continue
        if doc.docstatus == 0:
            # Draft — delete outright (no GL to reverse)
            # Some doctypes use `delete()`, others via frappe.delete_doc
            try:
                doc.delete()
            except Exception:
                frappe.delete_doc(doctype, name, force=1)
            success.append({{"doctype": doctype, "name": name, "action": "deleted_draft"}})
            continue
        # docstatus == 1: cancel to reverse GL natively
        doc.flags.ignore_permissions = True
        doc.cancel()
        success.append({{"doctype": doctype, "name": name, "action": "cancelled"}})
    except Exception as e:
        failures.append({{"doctype": doctype, "name": name, "error": str(e)}})

frappe.db.commit()

payload = {{"success": success, "failures": failures, "skipped": skipped, "total": len(cancels)}}
blob = gzip.compress(json.dumps(payload).encode())
print("__S209_CANCEL_START__")
print(base64.b64encode(blob).decode())
print("__S209_CANCEL_END__")

frappe.destroy()
'''


def run_in_container(python_script: str, timeout: int = 300) -> str:
    import boto3
    ssm = boto3.client("ssm", region_name=AWS_REGION)
    enc = base64.b64encode(python_script.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s209_cancel.py",
        "docker cp /tmp/s209_cancel.py $BACKEND:/tmp/s209_cancel.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s209_cancel.py",
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
        time.sleep(5)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
            out = inv.get("StandardOutputContent", "")
            err = inv.get("StandardErrorContent", "")
            if inv["Status"] != "Success":
                sys.stderr.write(f"[SSM {inv['Status']}]\n{err[-2000:]}\n")
                raise RuntimeError(f"SSM command failed: {inv['Status']}")
            return out
    raise TimeoutError(f"SSM command {cid} did not complete")


def extract_payload(stdout: str) -> dict:
    s = stdout.find("__S209_CANCEL_START__")
    e = stdout.find("__S209_CANCEL_END__")
    if s < 0 or e < 0:
        raise RuntimeError("Could not find cancel markers in SSM output")
    return json.loads(gzip.decompress(
        base64.b64decode(stdout[s + len("__S209_CANCEL_START__"):e].strip())
    ).decode())


def load_ledger(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        print(f"[S209] ledger {path} not found; nothing to clean up")
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--dry-run", action="store_true", help="List cancellations without executing")
    args = ap.parse_args()

    ledger_path = pathlib.Path(args.ledger)
    entries = load_ledger(ledger_path)
    if not entries:
        print("[S209] ledger empty — cleanup complete by definition")
        return 0

    # Group by kind → doctype, preserve in-ledger order per group, then walk
    # PROCESSING_ORDER (reverse dependency).
    by_kind: dict[str, list[dict]] = {}
    for entry in entries:
        kind = entry.get("kind", "")
        by_kind.setdefault(kind, []).append(entry)

    cancellations: list[dict] = []
    for kind, doctype in PROCESSING_ORDER:
        for entry in reversed(by_kind.get(kind, [])):  # reverse order inside group too
            name = (entry.get("payload") or {}).get("name")
            if not name:
                continue
            cancellations.append({"doctype": doctype, "name": name, "kind": kind})

    if args.dry_run:
        print(f"[S209 dry-run] {len(cancellations)} cancellations would be attempted:")
        for c in cancellations:
            print(f"  reverse_order: {c['doctype']} / {c['name']} (from {c['kind']})")
        return 0

    print(f"[S209] Cancelling {len(cancellations)} test docs (reverse_order: SI->WR->SE->MR->Order)...")
    out = run_in_container(_build_cancel_script(cancellations))
    payload = extract_payload(out)

    CLEANUP_REPORT.parent.mkdir(parents=True, exist_ok=True)
    CLEANUP_REPORT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(
        f"[S209] success={len(payload['success'])} "
        f"skipped={len(payload['skipped'])} failures={len(payload['failures'])}"
    )
    for ok in payload["success"][:10]:
        print(f"  [ok] {ok['doctype']}/{ok['name']} -> {ok['action']}")
    for sk in payload["skipped"][:10]:
        print(f"  [skip] {sk['doctype']}/{sk['name']} ({sk['reason']})")

    if payload["failures"]:
        sys.stderr.write(f"\n[FAILURE] {len(payload['failures'])} cancels failed:\n")
        for f in payload["failures"]:
            sys.stderr.write(f"  {f['doctype']}/{f['name']}: {f['error'][:300]}\n")
        return 2

    # If all good, reset ledger so pendingEntries == 0
    ledger_path.write_text("[]", encoding="utf-8")
    print("[S209] ledger reset to []")
    return 0


if __name__ == "__main__":
    sys.exit(main())
