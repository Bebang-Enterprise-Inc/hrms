"""S225 Phase 3 — retire one warehouse duplicate via Material Transfer Stock Entry.

Audit B-2 + B-3 + W-3 fix: use Material Transfer (Stock Entry), NOT Stock Reconciliation.
The original v1 plan used Stock Reconciliation, but:
  (a) `SR.add_batch()` doesn't exist in ERPNext v15 — that API was hallucinated.
  (b) SR posts the delta through P&L 'Stock Adjustment Expense' leaving no linking
      transfer doc for BIR audit.
  (c) BEI's existing inter-warehouse movement uses Stock Entry with stock_entry_type
      = "Material Transfer" (see hrms/api/warehouse.py:1537).

Material Transfer is the correct doctype:
  - Single document, asset-to-asset GL movement (no P&L).
  - Generates a matched SLE pair (s-out at duplicate, s-in at canonical).
  - Preserves batch tracking via the existing v15 Serial and Batch Bundle flow.
  - Full BIR audit trail via the linked Stock Entry doc.

Default: dry-run. Pass --commit to mutate.

Run from worktree:
    python scripts/canonical/retire_warehouse_duplicate.py \
      --duplicate "3MD LOGISTICS – CAMANGYANAN - BKI" \
      --canonical "3MD LOGISTICS - CAMANGYANAN - BKI" \
      --cluster-id "cluster-3md-logistics-camangyanan-bki" \
      --sam-token "S225 Phase 3 APPROVED ALL"
      [--commit]

Per cluster:
  1. Validate winner exists, not disabled, not is_group, same company.
  2. Snapshot before (warehouse doc + Bin rows + open transactions).
  3. Build single Material Transfer SE with all items (qty > 0).
  4. Submit SE.
  5. Set Warehouse.disabled = 1 on duplicate.
  6. Snapshot after; verify two-sided per-item conservation (audit B-9).
  7. Write per-cluster ledger to output/s225/verification/dup_<slug>_consolidation.json.
"""
from __future__ import annotations
import argparse
import base64
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "output" / "s225" / "verification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

INSTANCE_ID = "i-026b7477d27bd46d6"


def _slug_from_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s


def _build_inner(duplicate: str, canonical: str, sam_token: str, commit: bool) -> str:
    return f'''
import os, json, traceback, sys
for d in [
    "/home/frappe/logs",
    "/home/frappe/frappe-bench/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/logs",
    "/home/frappe/frappe-bench/sites/hq.bebang.ph/private/files",
]:
    os.makedirs(d, exist_ok=True)

import frappe
frappe.init(site="hq.bebang.ph", sites_path="/home/frappe/frappe-bench/sites")
frappe.connect()
frappe.set_user("Administrator")

DUPLICATE = {duplicate!r}
CANONICAL = {canonical!r}
SAM_TOKEN = {sam_token!r}
COMMIT = {commit}

result = {{
    "duplicate": DUPLICATE,
    "canonical": CANONICAL,
    "sam_token": SAM_TOKEN,
    "committed": COMMIT,
    "step": "init",
}}

try:
    # === 1. Validate ===
    dup_doc = frappe.db.get_value("Warehouse", DUPLICATE,
        ["name", "warehouse_name", "company", "disabled", "is_group", "parent_warehouse"], as_dict=True)
    can_doc = frappe.db.get_value("Warehouse", CANONICAL,
        ["name", "warehouse_name", "company", "disabled", "is_group", "parent_warehouse"], as_dict=True)
    if not dup_doc:
        result["status"] = "FAIL_DUPLICATE_NOT_FOUND"
        print(json.dumps(result))
        sys.exit(1)
    if not can_doc:
        result["status"] = "FAIL_CANONICAL_NOT_FOUND"
        print(json.dumps(result))
        sys.exit(1)
    if can_doc["disabled"]:
        result["status"] = "FAIL_CANONICAL_IS_DISABLED"
        print(json.dumps(result))
        sys.exit(1)
    if can_doc["is_group"]:
        result["status"] = "FAIL_CANONICAL_IS_GROUP"
        print(json.dumps(result))
        sys.exit(1)
    if can_doc["company"] != dup_doc["company"]:
        result["status"] = "FAIL_INTERCOMPANY_NOT_AUTHORIZED"
        result["winner_company"] = can_doc["company"]
        result["loser_company"] = dup_doc["company"]
        result["hint"] = "Use Sam token APPROVED INTERCOMPANY for explicit authorization"
        print(json.dumps(result))
        sys.exit(1)
    result["step"] = "validated"

    # === 2. Snapshot before ===
    dup_bins_before = frappe.db.sql(
        "SELECT item_code, actual_qty, stock_uom FROM `tabBin` WHERE warehouse=%s ORDER BY item_code",
        (DUPLICATE,), as_dict=True,
    )
    can_bins_before = frappe.db.sql(
        "SELECT item_code, actual_qty, stock_uom FROM `tabBin` WHERE warehouse=%s ORDER BY item_code",
        (CANONICAL,), as_dict=True,
    )
    open_mrs = frappe.db.sql(
        "SELECT mri.parent AS mr_name, mri.item_code, mri.qty, mr.status "
        "FROM `tabMaterial Request Item` mri "
        "JOIN `tabMaterial Request` mr ON mr.name = mri.parent "
        "WHERE mri.warehouse=%s AND mr.docstatus=1 AND mr.status NOT IN ('Issued','Cancelled') "
        "LIMIT 50",
        (DUPLICATE,), as_dict=True,
    )
    draft_ses = frappe.db.sql(
        "SELECT sed.parent AS se_name, sed.item_code, sed.qty, sed.s_warehouse, sed.t_warehouse "
        "FROM `tabStock Entry Detail` sed "
        "JOIN `tabStock Entry` se ON se.name = sed.parent "
        "WHERE (sed.s_warehouse=%s OR sed.t_warehouse=%s) AND se.docstatus=0 LIMIT 50",
        (DUPLICATE, DUPLICATE), as_dict=True,
    )
    result["before"] = {{
        "duplicate_doc": dup_doc,
        "canonical_doc": can_doc,
        "duplicate_bins": dup_bins_before,
        "canonical_bins": can_bins_before,
        "open_mrs_on_duplicate": open_mrs,
        "draft_ses_on_duplicate": draft_ses,
    }}
    result["step"] = "snapshot_before"

    # Items to migrate (only those with non-zero stock)
    items_to_migrate = [b for b in dup_bins_before if b["actual_qty"] > 0]
    if not items_to_migrate:
        result["status"] = "NO_STOCK_TO_MIGRATE"
        result["note"] = "Duplicate has no positive stock — disable directly without SE"
        if COMMIT:
            frappe.db.set_value("Warehouse", DUPLICATE, "disabled", 1)
            frappe.db.commit()
            result["disabled_at"] = frappe.utils.now()
            result["status"] = "DISABLED_NO_SE_NEEDED"
        else:
            result["status"] = "DRY_RUN_NO_SE_NEEDED"
        print(json.dumps(result, default=str))
        sys.exit(0)

    # === 3. Build Material Transfer SE ===
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.purpose = "Material Transfer"
    se.company = dup_doc["company"]
    se.posting_date = frappe.utils.today()
    se.posting_time = frappe.utils.nowtime()
    se.from_warehouse = DUPLICATE
    se.to_warehouse = CANONICAL
    se.remarks = (
        f"S225 canonical cleanup: consolidate {{DUPLICATE}} -> {{CANONICAL}}. "
        f"Sam authorization: {{SAM_TOKEN}}. Per docs/STORE_COMPANY_CANONICAL.md rules 1+2."
    )
    items_planned = []
    for b in items_to_migrate:
        item_code = b["item_code"]
        qty = float(b["actual_qty"])
        item_doc = frappe.db.get_value("Item", item_code,
            ["name", "stock_uom", "has_batch_no"], as_dict=True)
        uom = b["stock_uom"] or (item_doc["stock_uom"] if item_doc else "Nos")
        row = {{
            "item_code": item_code,
            "qty": qty,
            "uom": uom,
            "stock_uom": uom,
            "conversion_factor": 1,
            "s_warehouse": DUPLICATE,
            "t_warehouse": CANONICAL,
        }}
        se.append("items", row)
        items_planned.append({{
            "item_code": item_code,
            "qty": qty,
            "uom": uom,
            "has_batch_no": int(item_doc.get("has_batch_no", 0)) if item_doc else 0,
        }})
    result["items_planned"] = items_planned
    result["step"] = "se_built"

    if not COMMIT:
        result["status"] = "DRY_RUN"
        result["dry_run_se_summary"] = {{
            "stock_entry_type": "Material Transfer",
            "company": se.company,
            "from_warehouse": DUPLICATE,
            "to_warehouse": CANONICAL,
            "item_count": len(items_planned),
            "total_qty": sum(i["qty"] for i in items_planned),
        }}
        print(json.dumps(result, default=str))
        sys.exit(0)

    # === 4. Submit SE ===
    se.insert(ignore_permissions=True)
    se.submit()
    result["se_name"] = se.name
    result["step"] = "se_submitted"

    # === 5. Disable duplicate warehouse ===
    frappe.db.set_value("Warehouse", DUPLICATE, "disabled", 1)
    result["step"] = "warehouse_disabled"

    # === 6. Snapshot after ===
    dup_bins_after = frappe.db.sql(
        "SELECT item_code, actual_qty, stock_uom FROM `tabBin` WHERE warehouse=%s ORDER BY item_code",
        (DUPLICATE,), as_dict=True,
    )
    can_bins_after = frappe.db.sql(
        "SELECT item_code, actual_qty, stock_uom FROM `tabBin` WHERE warehouse=%s ORDER BY item_code",
        (CANONICAL,), as_dict=True,
    )
    result["after"] = {{
        "duplicate_bins": dup_bins_after,
        "canonical_bins": can_bins_after,
    }}

    # === 7. Two-sided per-item conservation (audit B-9) ===
    TOL = 0.001
    dup_after_map = {{b["item_code"]: float(b["actual_qty"]) for b in dup_bins_after}}
    can_before_map = {{b["item_code"]: float(b["actual_qty"]) for b in can_bins_before}}
    can_after_map = {{b["item_code"]: float(b["actual_qty"]) for b in can_bins_after}}

    per_item_results = []
    issues = []
    for b in items_to_migrate:
        ic = b["item_code"]
        dup_before_qty = float(b["actual_qty"])
        dup_after_qty = dup_after_map.get(ic, 0.0)
        can_before_qty = can_before_map.get(ic, 0.0)
        can_after_qty = can_after_map.get(ic, 0.0)
        gain = can_after_qty - can_before_qty
        per_item_results.append({{
            "item_code": ic,
            "duplicate_before_qty": dup_before_qty,
            "duplicate_after_qty": dup_after_qty,
            "canonical_before_qty": can_before_qty,
            "canonical_after_qty": can_after_qty,
            "canonical_gain": gain,
            "conservation_error": gain - dup_before_qty,
        }})
        if abs(dup_after_qty) > TOL:
            issues.append(f"item {{ic}}: duplicate Bin still has {{dup_after_qty}} units (STRANDED)")
        if abs(gain - dup_before_qty) > TOL:
            issues.append(f"item {{ic}}: canonical gain={{gain}} expected={{dup_before_qty}} (MIGRATION INCOMPLETE)")
    result["per_item_results"] = per_item_results
    result["conservation_issues"] = issues

    if issues:
        # Roll back the SE submit + warehouse disable
        result["status"] = "FAIL_CONSERVATION_VIOLATED"
        try:
            se.cancel()
        except Exception:
            pass
        try:
            frappe.db.set_value("Warehouse", DUPLICATE, "disabled", 0)
        except Exception:
            pass
        frappe.db.rollback()
    else:
        result["status"] = "PASS"
        frappe.db.commit()

    print(json.dumps(result, default=str))

except Exception as e:
    result["fatal_error"] = str(e)[:600]
    result["traceback"] = traceback.format_exc()[:1500]
    result["status"] = "FATAL"
    try:
        frappe.db.rollback()
    except Exception:
        pass
    print(json.dumps(result, default=str))
    sys.exit(1)
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duplicate", required=True, help="Loser warehouse name (full docname)")
    ap.add_argument("--canonical", required=True, help="Winner warehouse name (full docname)")
    ap.add_argument("--cluster-id", required=True, help="Cluster ID slug from audit")
    ap.add_argument("--sam-token", required=True, help="Sam approval token text for the SE remarks")
    ap.add_argument("--commit", action="store_true", help="Apply mutations (default: dry-run)")
    args = ap.parse_args()

    inner = _build_inner(args.duplicate, args.canonical, args.sam_token, args.commit)
    enc = base64.b64encode(inner.encode()).decode()
    cmds = [
        "BACKEND=$(docker ps --filter name=frappe_backend --format '{{.ID}}' | head -1)",
        f"echo '{enc}' | base64 -d > /tmp/s225_retire_dup.py",
        "docker cp /tmp/s225_retire_dup.py $BACKEND:/tmp/s225_retire_dup.py",
        "docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/s225_retire_dup.py",
    ]
    import boto3
    ssm = boto3.client("ssm", region_name="ap-southeast-1")
    r = ssm.send_command(
        InstanceIds=[INSTANCE_ID],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": cmds, "executionTimeout": ["240"]},
    )
    cid = r["Command"]["CommandId"]
    print(f"CommandId: {cid}", flush=True)

    inv = None
    for _ in range(80):
        time.sleep(3)
        inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE_ID)
        if inv["Status"] in ("Success", "Failed", "TimedOut"):
            break
    if inv is None:
        print("SSM did not complete", flush=True)
        return 2

    stdout = inv.get("StandardOutputContent", "")
    stderr = inv.get("StandardErrorContent", "")
    print("--- STDOUT ---")
    print(stdout)
    if stderr.strip():
        print("--- STDERR ---")
        print(stderr)

    inner_result = None
    for line in stdout.splitlines()[::-1]:
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                inner_result = json.loads(s)
                break
            except json.JSONDecodeError:
                continue

    slug = _slug_from_name(args.duplicate)
    suffix = "applied" if args.commit else "dry_run"
    out_path = OUT_DIR / f"dup_{args.cluster_id.replace('cluster-', '')}_{suffix}.json"
    out_path.write_text(json.dumps({
        "ssm_command_id": cid,
        "ssm_status": inv["Status"],
        "args": vars(args),
        "result": inner_result,
        "raw_stdout": stdout[-4000:],
        "raw_stderr": stderr[-2000:],
    }, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_path}", flush=True)

    status = (inner_result or {}).get("status", "UNKNOWN")
    if args.commit:
        return 0 if status == "PASS" or status == "DISABLED_NO_SE_NEEDED" else 1
    else:
        return 0 if status in ("DRY_RUN", "DRY_RUN_NO_SE_NEEDED") else 1


if __name__ == "__main__":
    sys.exit(main())
