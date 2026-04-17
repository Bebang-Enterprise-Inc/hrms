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


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36"
)


def _frappe_rest_headers() -> dict:
    """Read FRAPPE_URL/KEY/SECRET from env (Doppler-injected)."""
    url = os.environ.get("FRAPPE_URL", "").rstrip("/")
    key = os.environ.get("FRAPPE_API_KEY", "")
    secret = os.environ.get("FRAPPE_API_SECRET", "")
    if not url or not key or not secret:
        raise RuntimeError(
            "FRAPPE_URL / FRAPPE_API_KEY / FRAPPE_API_SECRET missing. "
            "Invoke via: doppler run -p bei-erp -c dev -- python scripts/s192_preflight_setup.py ..."
        )
    return {"__base": url, "Authorization": f"token {key}:{secret}",
            "User-Agent": _UA, "Accept": "application/json"}


def _frappe_get(headers: dict, path: str):
    import urllib.request
    import urllib.error
    base = headers.pop("__base") if "__base" in headers else os.environ["FRAPPE_URL"].rstrip("/")
    h = {k: v for k, v in headers.items() if k != "__base"}
    req = urllib.request.Request(f"{base}{path}", method="GET", headers=h)
    headers["__base"] = base  # restore
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def _frappe_write(headers: dict, method: str, path: str, body: dict):
    import urllib.request
    import urllib.error
    base = headers.pop("__base") if "__base" in headers else os.environ["FRAPPE_URL"].rstrip("/")
    h = {k: v for k, v in headers.items() if k != "__base"}
    h["Content-Type"] = "application/json"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{base}{path}", method=method, headers=h, data=data)
    headers["__base"] = base
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def cmd_ensure_user(args) -> dict[str, Any]:
    """Idempotent Frappe User create + role-add via REST.

    - If User with `email` exists: add any missing roles, return rolesAdded.
    - If missing: create with all roles and default password BeiTest2026!.
    Emits JSON: {email, created: bool, rolesAdded: [...]}
    """
    if not args.email or not args.roles:
        raise ValueError("ensure-user requires --email and --roles")
    roles = json.loads(args.roles)
    if not isinstance(roles, list):
        raise ValueError("--roles must be JSON array of role names")

    import urllib.parse as _up
    headers = _frappe_rest_headers()
    email_enc = _up.quote(args.email, safe="")

    status, payload = _frappe_get(headers, f"/api/resource/User/{email_enc}")
    if status == 404:
        body = {
            "email": args.email,
            "first_name": args.email.split("@")[0],
            "send_welcome_email": 0,
            "new_password": "BeiTest2026!",
            "enabled": 1,
            "roles": [{"role": role} for role in roles],
        }
        st, resp = _frappe_write(headers, "POST", "/api/resource/User", body)
        if st >= 400:
            raise RuntimeError(f"ensure-user create failed: HTTP {st} {str(resp)[:400]}")
        return {"email": args.email, "created": True, "rolesAdded": roles}
    if status >= 400:
        raise RuntimeError(f"ensure-user lookup failed: HTTP {status} {str(payload)[:400]}")

    existing = {row.get("role") for row in (payload.get("data") or {}).get("roles", [])}
    missing = [r for r in roles if r not in existing]
    if missing:
        new_roles = [{"role": r} for r in sorted(existing | set(roles)) if r]
        st, resp = _frappe_write(
            headers, "PUT", f"/api/resource/User/{email_enc}", {"roles": new_roles}
        )
        if st >= 400:
            raise RuntimeError(f"ensure-user role-add failed: HTTP {st} {str(resp)[:400]}")
    return {"email": args.email, "created": False, "rolesAdded": missing}


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
    "ensure-user": cmd_ensure_user,
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
