#!/usr/bin/env python3
"""
S192 SSM-driven preflight setup and cleanup operations.

Provides a command-line interface invoked by tests/e2e/support/ssmSetup.ts.
Each command executes against the production Frappe container via AWS SSM
send-command, returning a JSON result on stdout.

Commands:
    seed-inventory --warehouse <name> --items '[{"item_code":"...","qty":N}]'
    revert-bin-seed --warehouse <name> --items '[{"item_code":"...","before_qty":N}]'
    ensure-delivery-schedule --store <name> --cargo <DRY|FC|FM>
    ensure-route --store <name> --cargo <DRY|FC|FM>
    ensure-user --email <addr> --roles '["Role1","Role2"]'
    remove-user-roles --email <addr> --roles '["Role1"]'
    cancel-doc --doctype <DocType> --name <name>
    rename-doc --doctype <DocType> --old <oldname> --new <newname>
    create-warehouse --name <name> --company <name|NULL>
    delete-warehouse --name <name>
    delete-doc --doctype <DocType> --name <name>
    verify-billing-baseline

All commands emit JSON to stdout on success; human-readable errors to stderr
with non-zero exit on failure.

Environment:
    AWS_PROFILE, AWS_REGION (for boto3)
    BEI_INSTANCE_ID (default: i-026b7477d27bd46d6)
    FRAPPE_CONTAINER (default: frappe_backend)
    FRAPPE_SITE (default: hq.bebang.ph)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
import time
from typing import Any

INSTANCE_ID = os.environ.get("BEI_INSTANCE_ID", "i-026b7477d27bd46d6")
CONTAINER = os.environ.get("FRAPPE_CONTAINER", "frappe_backend")
SITE = os.environ.get("FRAPPE_SITE", "hq.bebang.ph")
AWS_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")


def run_bench(python_code: str, timeout: int = 120) -> dict[str, Any]:
    """Execute Python inside the Frappe container via SSM send-command.

    Returns a dict with {'ok': bool, 'stdout': str, 'stderr': str}.
    """
    bench_cmd = (
        f"docker exec -i {CONTAINER} bench --site {SITE} execute "
        f"--kwargs '{{\"_script\":{json.dumps(python_code)}}}' "
        "hrms.api.testing_helpers.exec_inline"
    )
    # Fallback: write script to tmpfile and execute via bench console.
    # Preferred pattern: frappe.bench.execute with a helper API that
    # accepts inline Python. If the helper doesn't exist, use `bench execute`
    # against a known whitelisted function (requires module).

    ssm_payload = {
        "commands": [bench_cmd],
        "executionTimeout": [str(timeout)],
    }
    cmd = [
        "aws",
        "ssm",
        "send-command",
        "--instance-ids",
        INSTANCE_ID,
        "--document-name",
        "AWS-RunShellScript",
        "--parameters",
        json.dumps(ssm_payload),
        "--region",
        AWS_REGION,
        "--output",
        "json",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}

    if proc.returncode != 0:
        return {"ok": False, "stdout": proc.stdout, "stderr": proc.stderr}

    try:
        meta = json.loads(proc.stdout)
        cmd_id = meta["Command"]["CommandId"]
    except Exception as e:
        return {"ok": False, "stdout": proc.stdout, "stderr": f"parse error: {e}"}

    # Poll get-command-invocation
    for _ in range(60):
        time.sleep(2)
        inv = subprocess.run(
            [
                "aws",
                "ssm",
                "get-command-invocation",
                "--command-id",
                cmd_id,
                "--instance-id",
                INSTANCE_ID,
                "--region",
                AWS_REGION,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        if inv.returncode != 0:
            continue
        try:
            data = json.loads(inv.stdout)
        except Exception:
            continue
        status = data.get("Status", "")
        if status in ("Success", "Failed", "TimedOut", "Cancelled"):
            return {
                "ok": status == "Success",
                "stdout": data.get("StandardOutputContent", ""),
                "stderr": data.get("StandardErrorContent", ""),
                "status": status,
            }
    return {"ok": False, "stdout": "", "stderr": "SSM poll timeout"}


def cmd_seed_inventory(args) -> dict[str, Any]:
    items = json.loads(args.items)
    script = textwrap.dedent(
        f"""
        import frappe
        warehouse = {args.warehouse!r}
        items = {items!r}
        out = []
        for it in items:
            bin_ = frappe.db.get_value(
                'Bin', {{'item_code': it['item_code'], 'warehouse': warehouse}},
                ['name', 'actual_qty'], as_dict=True
            )
            before = bin_.actual_qty if bin_ else 0.0
            # Use Stock Reconciliation to seed precise qty
            sr = frappe.new_doc('Stock Reconciliation')
            sr.purpose = 'Stock Reconciliation'
            sr.company = frappe.db.get_value('Warehouse', warehouse, 'company')
            sr.append('items', {{
                'item_code': it['item_code'],
                'warehouse': warehouse,
                'qty': it['qty'],
                'valuation_rate': 1.0,
            }})
            sr.insert(ignore_permissions=True)
            sr.submit()
            out.append({{'item_code': it['item_code'], 'qty': it['qty'], 'before_qty': before}})
        print('RESULT:' + frappe.as_json({{'warehouse': warehouse, 'seeded': out}}))
        """
    )
    res = run_bench(script)
    if not res["ok"]:
        raise RuntimeError(f"seed-inventory failed: {res['stderr']}")
    marker = "RESULT:"
    idx = res["stdout"].find(marker)
    if idx == -1:
        raise RuntimeError(f"seed-inventory no result marker: {res['stdout']}")
    return json.loads(res["stdout"][idx + len(marker):])


def cmd_verify_billing_baseline(_args) -> dict[str, Any]:
    """Query all 53 store warehouses and verify Company → Customer → TIN chain."""
    script = textwrap.dedent(
        """
        import frappe
        warehouses = frappe.get_all(
            'Warehouse',
            filters={'disabled': 0, 'warehouse_type': ['like', '%Store%']},
            fields=['name', 'company']
        )
        billable = 0
        gaps = []
        for w in warehouses:
            if not w.company:
                gaps.append({'warehouse': w.name, 'reason': 'no Company'})
                continue
            customer = frappe.db.exists('Customer', w.company)
            if not customer:
                gaps.append({'warehouse': w.name, 'company': w.company, 'reason': 'no Customer'})
                continue
            tin = frappe.db.get_value('Customer', w.company, 'tax_id')
            if not tin:
                gaps.append({'warehouse': w.name, 'company': w.company, 'reason': 'no TIN'})
                continue
            billable += 1
        print('RESULT:' + frappe.as_json({
            'total_warehouses': len(warehouses),
            'billable': billable,
            'gaps': gaps
        }))
        """
    )
    res = run_bench(script)
    if not res["ok"]:
        raise RuntimeError(res["stderr"])
    idx = res["stdout"].find("RESULT:")
    return json.loads(res["stdout"][idx + 7:])


def cmd_cancel_doc(args) -> dict[str, Any]:
    script = textwrap.dedent(
        f"""
        import frappe
        try:
            doc = frappe.get_doc({args.doctype!r}, {args.name!r})
            if doc.docstatus == 1:
                doc.cancel()
            elif doc.docstatus == 0:
                frappe.delete_doc({args.doctype!r}, {args.name!r}, force=1, ignore_permissions=True)
            frappe.db.commit()
            print('RESULT:' + frappe.as_json({{'ok': True}}))
        except frappe.DoesNotExistError:
            print('RESULT:' + frappe.as_json({{'ok': True, 'missing': True}}))
        """
    )
    res = run_bench(script)
    if not res["ok"]:
        raise RuntimeError(res["stderr"])
    idx = res["stdout"].find("RESULT:")
    return json.loads(res["stdout"][idx + 7:])


def cmd_delete_doc(args) -> dict[str, Any]:
    return cmd_cancel_doc(args)  # Same path


def cmd_rename_doc(args) -> dict[str, Any]:
    script = textwrap.dedent(
        f"""
        import frappe
        frappe.rename_doc({args.doctype!r}, {args.old!r}, {args.new!r}, force=True)
        frappe.db.commit()
        print('RESULT:' + frappe.as_json({{'ok': True}}))
        """
    )
    res = run_bench(script)
    if not res["ok"]:
        raise RuntimeError(res["stderr"])
    idx = res["stdout"].find("RESULT:")
    return json.loads(res["stdout"][idx + 7:])


# Simple stubs for remaining commands — full implementation deferred until
# Phase 1 execution surfaces concrete needs.

def cmd_stub(name: str):
    def _impl(_args):
        raise NotImplementedError(
            f"{name}: implement when first scenario needs it. "
            f"Pattern: build Python script, run via run_bench()."
        )
    return _impl


DISPATCHERS: dict[str, Any] = {
    "seed-inventory": cmd_seed_inventory,
    "revert-bin-seed": cmd_stub("revert-bin-seed"),
    "ensure-delivery-schedule": cmd_stub("ensure-delivery-schedule"),
    "ensure-route": cmd_stub("ensure-route"),
    "ensure-user": cmd_stub("ensure-user"),
    "remove-user-roles": cmd_stub("remove-user-roles"),
    "cancel-doc": cmd_cancel_doc,
    "delete-doc": cmd_delete_doc,
    "rename-doc": cmd_rename_doc,
    "create-warehouse": cmd_stub("create-warehouse"),
    "delete-warehouse": cmd_stub("delete-warehouse"),
    "verify-billing-baseline": cmd_verify_billing_baseline,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=list(DISPATCHERS.keys()))
    parser.add_argument("--warehouse")
    parser.add_argument("--items")
    parser.add_argument("--store")
    parser.add_argument("--cargo")
    parser.add_argument("--email")
    parser.add_argument("--roles")
    parser.add_argument("--doctype")
    parser.add_argument("--name")
    parser.add_argument("--old")
    parser.add_argument("--new")
    parser.add_argument("--company")
    args = parser.parse_args()

    try:
        result = DISPATCHERS[args.command](args)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
