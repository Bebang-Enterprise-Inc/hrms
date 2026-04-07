#!/usr/bin/env python3
"""S169 Phase 4 finisher — rewrite the remaining 7 objects.

Pre-conditions verified:
- v_pos_orders_live wrapper exists
- 5 objects already rewritten (v_all_channel_daily, v_orders, v_monthly_store_summary,
  v_discount_identity_order_usage, daily_revenue MV)
- 7 remaining: 5 MVs + 2 views

Reads tmp/s169_view_definitions_before.sql for original definitions, applies single-token
substitution `pos_orders` -> `v_pos_orders_live` with word boundaries (won't match
pos_orders_items or pos_orders_payments), and applies via Supabase Management API.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CREATIONFLAGS = 0x08000000 if sys.platform == "win32" else 0
PROJECT_REF = "csnniykjrychgajfrgua"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

# Rewrite order: dependents AFTER their dependencies. v_ops_weekly depends on v_all_channel_daily
# (already done), v_system_daily_totals depends on store_daily_closing MV (in this batch).
# So MVs first, then dependent views.
REMAINING = [
    # 5 MVs were dropped by killed Phase 4 subagent without being recreated.
    # CASCADE also took v_system_daily_totals (depends on store_daily_closing).
    # Recovery: recreate all 6 with rewritten body, then refresh.
    # Order: store_daily_closing BEFORE v_system_daily_totals (dependency).
    ("MV",   "discount_summary"),
    ("MV",   "payment_reconciliation"),
    ("MV",   "store_daily_baselines"),
    ("MV",   "store_daily_closing"),
    ("MV",   "sales_dashboard_daily_store_metrics"),
    ("VIEW", "v_system_daily_totals"),  # CASCADE collateral — recreate from before (FALSE POSITIVE rewrite, use original body)
]


def get_token() -> str:
    r = subprocess.run(
        ["doppler", "secrets", "get", "SUPABASE_MGMT_TOKEN", "--plain",
         "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15, creationflags=CREATIONFLAGS,
    )
    if r.returncode != 0:
        raise RuntimeError(f"doppler failed: {r.stderr}")
    return r.stdout.strip()


def mgmt_query(token: str, sql: str) -> list:
    import requests
    r = requests.post(
        MGMT_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def parse_before_sql(path: Path) -> dict:
    """Parse the before sql file into {name: (kind, body)}."""
    out = {}
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^-- === (MV|VIEW): public\.([\w_]+) ===\s*$", text, flags=re.MULTILINE)
    # blocks = ['preamble', 'MV', 'name', 'body', 'MV', 'name', 'body', ...]
    i = 1
    while i < len(blocks):
        kind = blocks[i]
        name = blocks[i + 1]
        body = blocks[i + 2].strip()
        # strip trailing semicolon if present
        if body.endswith(";"):
            body = body[:-1].rstrip()
        out[name] = (kind, body)
        i += 3
    return out


def rewrite_body(body: str) -> tuple[str, int]:
    """Apply substitutions for the 3 ways pos_orders is referenced. Returns (new_body, n_substitutions)."""
    new = body
    n1 = len(re.findall(r"\bFROM\s+pos_orders\b", new, flags=re.IGNORECASE))
    new = re.sub(r"\bFROM\s+pos_orders\b", "FROM v_pos_orders_live", new, flags=re.IGNORECASE)
    n2 = len(re.findall(r"\bJOIN\s+pos_orders\b", new, flags=re.IGNORECASE))
    new = re.sub(r"\bJOIN\s+pos_orders\b", "JOIN v_pos_orders_live", new, flags=re.IGNORECASE)
    # Qualified column references: pos_orders.col → v_pos_orders_live.col
    # The trailing dot prevents matching column aliases like "sum(pos_orders) AS pos_orders".
    n3 = len(re.findall(r"\bpos_orders\.", new))
    new = re.sub(r"\bpos_orders\.", "v_pos_orders_live.", new)
    return new, n1 + n2 + n3


def main():
    repo = Path(__file__).resolve().parents[1]
    before_sql = repo / "tmp" / "s169_view_definitions_before.sql"
    deltas_path = repo / "output" / "l3" / "s169" / "view_rewrite_deltas.json"
    after_sql_path = repo / "tmp" / "s169_view_definitions_after.sql"

    defs = parse_before_sql(before_sql)
    print(f"Parsed {len(defs)} definitions from before sql")

    token = get_token()

    # Load existing deltas if any (Phase 4 partial run wrote some)
    deltas = []
    if deltas_path.exists():
        deltas = json.loads(deltas_path.read_text())
        print(f"Loaded {len(deltas)} existing delta entries")

    after_sql_chunks = []

    for kind, name in REMAINING:
        print(f"\n=== {kind}: public.{name} ===")
        if name not in defs:
            print(f"  ERROR: not in before sql")
            continue
        d_kind, body = defs[name]
        new_body, nsub = rewrite_body(body)
        if nsub == 0:
            # FALSE POSITIVE — use original body verbatim (e.g., v_system_daily_totals
            # has a column named pos_orders, not a table reference)
            print(f"  0 substitutions — using ORIGINAL body verbatim (false positive)")
            new_body = body
        else:
            print(f"  substitutions: {nsub}")

        after_sql_chunks.append(f"-- === {kind}: public.{name} ===\n{new_body};\n")

        # Pre-count — may fail if object was already dropped by killed Phase 4 subagent
        try:
            pre = mgmt_query(token, f"SELECT COUNT(*) AS c FROM public.{name}")
            pre_count = pre[0]["c"]
        except Exception:
            pre_count = "DROPPED (recovery from killed Phase 4 subagent)"
        print(f"  pre_count: {pre_count}")

        # The body in the before sql ALREADY includes the full CREATE statement
        # (e.g. "CREATE MATERIALIZED VIEW public.discount_summary AS SELECT ...").
        # Don't double-prefix. Just substitute pos_orders -> v_pos_orders_live and run.
        # For VIEWS, swap CREATE VIEW -> CREATE OR REPLACE VIEW so we don't have to drop.
        # For MVs, DROP IF EXISTS first.
        try:
            if kind == "VIEW":
                # Make idempotent
                view_sql = re.sub(r"^CREATE\s+VIEW\b", "CREATE OR REPLACE VIEW",
                                  new_body, count=1, flags=re.IGNORECASE)
                mgmt_query(token, view_sql)
            else:  # MV
                mgmt_query(token, f"DROP MATERIALIZED VIEW IF EXISTS public.{name} CASCADE")
                mgmt_query(token, new_body)  # body already starts with CREATE MATERIALIZED VIEW
        except Exception as e:
            print(f"  APPLY FAILED: {e}")
            deltas.append({
                "name": name, "kind": kind, "pre_count": pre_count,
                "post_count": None, "delta": None, "error": str(e),
            })
            continue

        # Refresh MV
        if kind == "MV":
            print(f"  refreshing...")
            try:
                mgmt_query(token, f"REFRESH MATERIALIZED VIEW public.{name}")
            except Exception as e:
                print(f"  REFRESH FAILED: {e}")

        # Post-count
        time.sleep(0.5)
        post = mgmt_query(token, f"SELECT COUNT(*) AS c FROM public.{name}")
        post_count = post[0]["c"]
        delta = post_count - pre_count if isinstance(pre_count, int) else f"recovered (was: {pre_count})"
        print(f"  post_count: {post_count}  delta: {delta}")

        deltas.append({
            "name": name, "kind": kind,
            "pre_count": pre_count, "post_count": post_count, "delta": delta,
        })

    # Write deltas
    deltas_path.write_text(json.dumps(deltas, indent=2))
    print(f"\nWrote {deltas_path}")

    # Append to after sql
    if after_sql_path.exists():
        existing = after_sql_path.read_text(encoding="utf-8")
    else:
        existing = ""
    after_sql_path.write_text(existing + "\n" + "\n".join(after_sql_chunks), encoding="utf-8")
    print(f"Wrote {after_sql_path}")

    print(f"\nFinished. Processed {len(REMAINING)} objects.")


if __name__ == "__main__":
    main()
