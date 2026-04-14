#!/usr/bin/env python3
"""S194 Procurement-chain SSM preflight helper.

Runs locally; called by `tests/e2e/support/ssmSetup.ts` (the
`createBEISupplier` / `createBEIItem` / `createMatchException` helpers).
Each subcommand emits a JSON object on stdout and exits 0 on success.

Subcommands implemented in this stub:
  create-bei-supplier   --code <c> --name <n> --status <s> [--is-new 0|1] [--tin <t|NULL>]
  set-supplier-status   --code <c> --status <s>
  set-supplier-field    --code <c> --field <f> --value <v|NULL>
  delete-bei-supplier   --code <c>
  create-bei-item       --code <c> --name <n> [--group <g>]
  delete-bei-item       --code <c>
  create-match-exception --invoice <name> [--reason <r>]
  delete-match-exception --name <n>

This stub uses AWS SSM `send-command` against the production
Frappe container (instance ID + container name from env). Exact SSM
plumbing matches `scripts/s192_preflight_setup.py` — duplicated here so
S192 helpers stay untouched.

Currently this file is a STUB. The Phase S agent (or whoever runs the
S194 spec for the first time) MUST flesh out the SSM call bodies before
the spec can execute. Each subcommand below currently exits 1 with a
clear error so partial wiring does not silently pass.
"""
from __future__ import annotations

import argparse
import json
import sys


def _err(msg: str, code: int = 1) -> None:
    sys.stderr.write(msg + "\n")
    sys.exit(code)


def _stub(name: str) -> None:
    _err(
        f"[s194_preflight_setup] subcommand `{name}` is a stub. "
        "Wire it to AWS SSM (see scripts/s192_preflight_setup.py for the pattern) "
        "before running Phase S of S194.",
        2,
    )


def cmd_create_supplier(args: argparse.Namespace) -> None:
    _stub("create-bei-supplier")


def cmd_set_supplier_status(args: argparse.Namespace) -> None:
    _stub("set-supplier-status")


def cmd_set_supplier_field(args: argparse.Namespace) -> None:
    _stub("set-supplier-field")


def cmd_delete_supplier(args: argparse.Namespace) -> None:
    _stub("delete-bei-supplier")


def cmd_create_item(args: argparse.Namespace) -> None:
    _stub("create-bei-item")


def cmd_delete_item(args: argparse.Namespace) -> None:
    _stub("delete-bei-item")


def cmd_create_match_exception(args: argparse.Namespace) -> None:
    _stub("create-match-exception")


def cmd_delete_match_exception(args: argparse.Namespace) -> None:
    _stub("delete-match-exception")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="s194_preflight_setup.py",
        description="S194 procurement-chain SSM helpers (stub)",
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
    s.add_argument("--group", default="Test")
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
