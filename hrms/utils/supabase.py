"""Canonical Supabase access layer for Frappe-side Python code (S169).

Mirrors the shape used ad-hoc in hrms/api/sales_dashboard.py:168-199.
Future sprints migrate sales_dashboard.py, discount_abuse.py, marketing_giveaways.py,
and store_order_demand_snapshot.py to import from here.

Uses PostgREST for normal CRUD and the Supabase Management API for DDL / complex UPDATEs.
Pure HTTP via requests -- by design, mirrors existing BEI patterns.
"""
import os
from typing import Any, Optional

import requests

import frappe

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://csnniykjrychgajfrgua.supabase.co")
SUPABASE_MGMT_URL = "https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query"


def get_service_key() -> str:
    """Return the Supabase service role key.

    Source order:
      1. Environment variable SUPABASE_SERVICE_ROLE_KEY
      2. Frappe bench config `supabase_service_role_key`
      3. Doppler fallback (local dev only)
    """
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if key:
        return key
    key = (frappe.conf.get("supabase_service_role_key") or "").strip()
    if key:
        return key
    # Local dev fallback via Doppler -- safe because Doppler CLI requires auth.
    # Windows headless rule: CREATE_NO_WINDOW (0x08000000) to avoid visible terminals.
    try:
        import subprocess
        result = subprocess.run(
            ["doppler", "secrets", "get", "SUPABASE_SERVICE_ROLE_KEY",
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    frappe.throw("SUPABASE_SERVICE_ROLE_KEY not available")


def get_mgmt_token() -> str:
    """Return the Supabase Management API token (for DDL / complex SQL)."""
    token = (os.environ.get("SUPABASE_MGMT_TOKEN") or "").strip()
    if token:
        return token
    token = (frappe.conf.get("supabase_mgmt_token") or "").strip()
    if token:
        return token
    try:
        import subprocess
        result = subprocess.run(
            ["doppler", "secrets", "get", "SUPABASE_MGMT_TOKEN",
             "--plain", "--project", "bei-erp", "--config", "dev"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    frappe.throw("SUPABASE_MGMT_TOKEN not available")


def supabase_headers(prefer: Optional[str] = None) -> dict:
    """Return PostgREST headers with the service role key."""
    key = get_service_key()
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def supabase_get(path: str, params: Optional[dict] = None, timeout: int = 15) -> Any:
    """GET against PostgREST. Returns parsed JSON."""
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    r = requests.get(url, headers=supabase_headers(), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def supabase_patch(path: str, params: dict, body: dict, timeout: int = 15) -> Any:
    """PATCH against PostgREST (for column-scoped UPDATEs on a filtered set)."""
    url = f"{SUPABASE_URL}/rest/v1/{path.lstrip('/')}"
    r = requests.patch(
        url,
        headers=supabase_headers(prefer="return=representation"),
        params=params,
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def supabase_query_sql(sql: str, params: tuple = ()) -> list:
    """Execute arbitrary SQL via the Supabase Management API.

    Use this for DDL, RETURNING clauses, or transactional UPDATEs that PostgREST
    can't express cleanly. Returns a list of row dicts.

    LIMITATION: The Management API does NOT support true parameterized queries.
    This helper does naive ``%s`` substitution that ONLY supports a fixed-shape
    tuple of (str, str, int) -- the exact shape used by the S169 webhook caller.
    For broader use, callers MUST use ``supabase_patch()`` or ``supabase_get()``
    with PostgREST filter params instead. TODO: a follow-up sprint should switch
    to a properly parameterized Management API call if more consumers adopt this.
    """
    if params:
        safe_args = []
        for p in params:
            if p is None:
                safe_args.append("NULL")
            elif isinstance(p, str):
                safe_args.append("'" + p.replace("'", "''") + "'")
            elif isinstance(p, bool):
                safe_args.append("TRUE" if p else "FALSE")
            else:
                # Only int (or numeric coercible) is supported beyond str/None.
                safe_args.append(str(int(p)))
        sql_filled = sql
        for arg in safe_args:
            sql_filled = sql_filled.replace("%s", arg, 1)
    else:
        sql_filled = sql

    r = requests.post(
        SUPABASE_MGMT_URL,
        headers={
            "Authorization": f"Bearer {get_mgmt_token()}",
            "Content-Type": "application/json",
        },
        json={"query": sql_filled},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
