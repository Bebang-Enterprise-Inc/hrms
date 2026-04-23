#!/usr/bin/env python3
"""S194 Procurement-chain SSM preflight helper.

Called by `tests/e2e/support/ssmSetup.ts` (the `createBEISupplier` /
`createBEIItem` / `createMatchException` helpers). Each subcommand emits
a JSON object on stdout and exits 0 on success.

Implementation uses the Frappe REST API (authenticated via
FRAPPE_API_KEY + FRAPPE_API_SECRET from Doppler) rather than SSM
send-command, so it can be invoked from Windows dev machines without
boto3 / AWS creds. For environments where REST is unavailable, pass
`--via=ssm` and the helper will fall back to SSM (not yet wired).

Environment (from Doppler `doppler run -- python s194_preflight_setup.py ...`):
  FRAPPE_URL, FRAPPE_API_KEY, FRAPPE_API_SECRET

Subcommands:
  create-bei-supplier   --code <c> --name <n> --status <s> [--is-new 0|1] [--tin <t|NULL>]
  set-supplier-status   --code <c> --status <s>
  set-supplier-field    --code <c> --field <f> --value <v|NULL>
  delete-bei-supplier   --code <c>
  create-bei-item       --code <c> --name <n> [--group <g>]
  delete-bei-item       --code <c>
  create-match-exception --invoice <name> [--reason <r>]
  delete-match-exception --name <n>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

try:
    import urllib.request as urlreq
    import urllib.error as urlerr
    import urllib.parse as urlparse
except Exception:  # pragma: no cover
    _err("urllib not available", 3)


SUPPLIER_DOCTYPE = "BEI Supplier"
ITEM_DOCTYPE = "Item"  # procurement.py references frappe.db.exists("Item", ...) — stock Frappe doctype, not BEI Item
MATCH_EXC_DOCTYPE = "BEI Match Exception"


def _err(msg: str, code: int = 1) -> None:
    sys.stderr.write(msg + "\n")
    sys.exit(code)


def _frappe_env() -> Dict[str, str]:
    url = os.environ.get("FRAPPE_URL", "").rstrip("/")
    key = os.environ.get("FRAPPE_API_KEY", "")
    secret = os.environ.get("FRAPPE_API_SECRET", "")
    if not url or not key or not secret:
        _err(
            "FRAPPE_URL / FRAPPE_API_KEY / FRAPPE_API_SECRET missing. "
            "Invoke via: doppler run -p bei-erp -c dev -- python "
            "scripts/s194_preflight_setup.py <subcommand> ...",
            4,
        )
    return {"url": url, "key": key, "secret": secret}


def _auth_header(env: Dict[str, str]) -> Dict[str, str]:
    return {"Authorization": f"token {env['key']}:{env['secret']}"}


def _request(method: str, path: str, body: Any = None) -> Dict[str, Any]:
    env = _frappe_env()
    data = None
    # Cloudflare in front of *.bebang.ph blocks the default Python-urllib UA
    # (Error 1010). Spoof a real browser. Curl + node use their own UAs which
    # also work — but Python's default does not.
    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/132.0.0.0 Safari/537.36"
        ),
        **_auth_header(env),
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlreq.Request(
        f"{env['url']}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urlreq.urlopen(req, timeout=60) as resp:
            payload = resp.read().decode("utf-8")
            if resp.status >= 400:
                _err(f"HTTP {resp.status}: {payload}", 5)
            return json.loads(payload) if payload else {}
    except urlerr.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        _err(f"HTTP {e.code} on {method} {path}: {body_txt}", 5)
    except urlerr.URLError as e:
        _err(f"URLError {e.reason} on {method} {path}", 6)
    return {}


def _enc(s: str) -> str:
    """URL-encode a path segment (DocType names contain spaces)."""
    return urlparse.quote(s, safe="")


def _get_doc(doctype: str, name: str) -> Dict[str, Any]:
    return _request("GET", f"/api/resource/{_enc(doctype)}/{_enc(name)}").get("data", {})


def _create_doc(doctype: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    return _request("POST", f"/api/resource/{_enc(doctype)}", fields).get("data", {})


def _update_doc(doctype: str, name: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    return _request("PUT", f"/api/resource/{_enc(doctype)}/{_enc(name)}", fields).get("data", {})


def _delete_doc(doctype: str, name: str) -> None:
    _request("DELETE", f"/api/resource/{_enc(doctype)}/{_enc(name)}")


def cmd_create_supplier(args: argparse.Namespace) -> None:
    fields = {
        "supplier_code": args.code,
        "supplier_name": args.name,
        "status": args.status,
    }
    if args.is_new == "1":
        # is_new_supplier is age-based (creation date < 30d) — the flag
        # may not exist as a settable field. We rely on creation time for
        # the freshness check. This flag is metadata only if present.
        fields["is_new_supplier"] = 1
    if args.tin is not None and args.tin != "NULL":
        fields["tin"] = args.tin
    try:
        result = _create_doc(SUPPLIER_DOCTYPE, fields)
        print(json.dumps({
            "code": result.get("name", args.code),
            "name": result.get("supplier_name", args.name),
            "created": True,
        }))
    except SystemExit:
        raise
    except Exception as e:
        _err(f"create-bei-supplier failed: {e}", 7)


def cmd_set_supplier_status(args: argparse.Namespace) -> None:
    _update_doc(SUPPLIER_DOCTYPE, args.code, {"status": args.status})
    print(json.dumps({"code": args.code, "status": args.status}))


def cmd_set_supplier_field(args: argparse.Namespace) -> None:
    # Frappe REST PUT ignores JSON null — use empty string to actually clear
    # a field. S194-15: setSupplierField(..., tin, NULL) needs to empty the
    # TIN so the gate fires. Sending {"tin": null} was a no-op.
    value = "" if args.value == "NULL" else args.value
    _update_doc(SUPPLIER_DOCTYPE, args.code, {args.field: value})
    print(json.dumps({"code": args.code, "field": args.field, "value": value}))


def cmd_delete_supplier(args: argparse.Namespace) -> None:
    try:
        _delete_doc(SUPPLIER_DOCTYPE, args.code)
    except SystemExit:
        # Re-raise real errors; already logged
        raise
    print(json.dumps({"code": args.code, "deleted": True}))


def cmd_create_item(args: argparse.Namespace) -> None:
    fields = {
        "item_code": args.code,
        "item_name": args.name,
        "stock_uom": "Nos",  # Frappe-default UoM; required field on Item
        "is_stock_item": 0,  # tests don't need stock-tracked items
        # Rate authorized by Sam (CEO) on 2026-04-22 to make S194-21
        # mathematically satisfiable (qty=1 invoice = 100K + 12% VAT = 112K
        # >= test's paymentAmount=100K). Other tests verified safe at 100K:
        # - Boundary tests (S194-13/14) still trigger their thresholds
        # - TIN gate (S194-15) still > 250K threshold at qty=6
        # - Match-passing tests still chain (po=gr=invoice)
        # - Variance tests already exceed thresholds; behaviour preserved
        "standard_rate": 100000,
    }
    if args.group:
        fields["item_group"] = args.group
    try:
        result = _create_doc(ITEM_DOCTYPE, fields)
        print(json.dumps({
            "code": result.get("name", args.code),
            "name": result.get("item_name", args.name),
            "created": True,
        }))
    except SystemExit:
        raise
    except Exception as e:
        _err(f"create-bei-item failed: {e}", 8)


def cmd_delete_item(args: argparse.Namespace) -> None:
    _delete_doc(ITEM_DOCTYPE, args.code)
    print(json.dumps({"code": args.code, "deleted": True}))


def cmd_create_match_exception(args: argparse.Namespace) -> None:
    fields = {
        "invoice": args.invoice,
        "purchase_order": args.invoice,  # MX needs both; callers pass PO name as invoice arg
        "reason": args.reason,
        "status": "Pending CPO",
    }
    try:
        result = _create_doc(MATCH_EXC_DOCTYPE, fields)
        print(json.dumps({
            "name": result.get("name", ""),
            "invoice": args.invoice,
            "status": result.get("status", "Pending CPO"),
        }))
    except SystemExit:
        raise
    except Exception as e:
        _err(f"create-match-exception failed: {e}", 9)


def cmd_delete_match_exception(args: argparse.Namespace) -> None:
    _delete_doc(MATCH_EXC_DOCTYPE, args.name)
    print(json.dumps({"name": args.name, "deleted": True}))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="s194_preflight_setup.py",
        description="S194 procurement-chain SSM helpers (REST impl)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("create-bei-supplier")
    s.add_argument("--code", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--status", required=True)
    s.add_argument("--is-new", default="0")
    s.add_argument("--tin", default=None)
    s.set_defaults(func=cmd_create_supplier)

    s = sub.add_parser("set-supplier-status")
    s.add_argument("--code", required=True)
    s.add_argument("--status", required=True)
    s.set_defaults(func=cmd_set_supplier_status)

    s = sub.add_parser("set-supplier-field")
    s.add_argument("--code", required=True)
    s.add_argument("--field", required=True)
    s.add_argument("--value", required=True)
    s.set_defaults(func=cmd_set_supplier_field)

    s = sub.add_parser("delete-bei-supplier")
    s.add_argument("--code", required=True)
    s.set_defaults(func=cmd_delete_supplier)

    s = sub.add_parser("create-bei-item")
    s.add_argument("--code", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--group", default="TEST-Raw Materials")
    s.set_defaults(func=cmd_create_item)

    s = sub.add_parser("delete-bei-item")
    s.add_argument("--code", required=True)
    s.set_defaults(func=cmd_delete_item)

    s = sub.add_parser("create-match-exception")
    s.add_argument("--invoice", required=True)
    s.add_argument("--reason", default="S194 spec auto-seed")
    s.set_defaults(func=cmd_create_match_exception)

    s = sub.add_parser("delete-match-exception")
    s.add_argument("--name", required=True)
    s.set_defaults(func=cmd_delete_match_exception)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
