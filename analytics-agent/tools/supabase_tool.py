"""Supabase Meta Ads analytics view query tool for the BEI Analytics Agent.

Queries Supabase views via REST API using the service role key fetched from
Doppler.  A strict view allowlist prevents accidental access to tables outside
the Meta Ads analytics scope — the service role key bypasses RLS, so this
gate is the only line of defence.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from claude_agent_sdk import tool

# ---------------------------------------------------------------------------
# View allowlist — ONLY these views may be queried
# ---------------------------------------------------------------------------
ALLOWED_VIEWS: set[str] = {
    "v_meta_campaign_summary",
    "v_meta_flagged_ads",
    "v_meta_boost_candidates",
    "v_meta_weekly_trend",
    "v_meta_ad_inventory",
    "meta_organic_posts",
}

# ---------------------------------------------------------------------------
# Doppler secret cache (populated on first call, stable for process lifetime)
# ---------------------------------------------------------------------------
_supabase_url: str | None = None
_service_role_key: str | None = None


def _get_secret(name: str) -> str:
    """Get a secret from env var (Docker .env) or Doppler CLI fallback (local dev)."""
    val = os.environ.get(name)
    if val:
        return val
    # Fallback: Doppler CLI (local Windows dev)
    subprocess_kwargs: dict = {}
    if platform.system() == "Windows":
        subprocess_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    result = subprocess.run(
        [
            "doppler",
            "secrets",
            "get",
            name,
            "--project",
            "bei-erp",
            "--config",
            "dev",
            "--plain",
        ],
        capture_output=True,
        text=True,
        check=True,
        **subprocess_kwargs,
    )
    return result.stdout.strip()


def _ensure_secrets() -> tuple[str, str]:
    """Return (supabase_url, service_role_key), fetching from Doppler once."""
    global _supabase_url, _service_role_key  # noqa: PLW0603

    if _supabase_url is None:
        _supabase_url = _get_secret("SUPABASE_URL")
    if _service_role_key is None:
        _service_role_key = _get_secret("SUPABASE_SERVICE_ROLE_KEY")

    return _supabase_url, _service_role_key


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------
@tool(
    "query_supabase",
    "Query a Supabase Meta Ads analytics view",
    {
        "view": str,    # view name — MUST be in ALLOWED_VIEWS
        "filters": str,  # optional: Supabase REST filters like "status=eq.ACTIVE"
        "select": str,   # optional: column selection like "campaign_name,spend,cpa"
        "limit": int,    # optional: row limit, default 100
    },
)
def query_supabase(
    view: str,
    filters: str = "",
    select: str = "*",
    limit: int = 100,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Query an allowed Supabase analytics view and return its rows."""

    # ---- Allowlist gate ----
    if view not in ALLOWED_VIEWS:
        return {
            "error": (
                f"View '{view}' is not in the allowlist. "
                f"Allowed views: {', '.join(sorted(ALLOWED_VIEWS))}"
            ),
            "rows": [],
        }

    try:
        base_url, key = _ensure_secrets()
    except subprocess.CalledProcessError as exc:
        return {
            "error": f"Failed to fetch Doppler secrets: {exc.stderr or str(exc)}",
            "rows": [],
        }

    # ---- Build URL ----
    params: dict[str, str] = {"select": select, "limit": str(limit)}
    query_string = urllib.parse.urlencode(params)

    # Append raw REST filters (already in PostgREST syntax, e.g. "status=eq.ACTIVE")
    if filters:
        query_string = f"{query_string}&{filters}"

    url = f"{base_url.rstrip('/')}/rest/v1/{view}?{query_string}"

    # ---- Make request ----
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8")
        except Exception:
            pass
        return {
            "error": f"HTTP {exc.code}: {exc.reason} — {error_body}",
            "rows": [],
        }
    except urllib.error.URLError as exc:
        return {"error": f"URL error: {exc.reason}", "rows": []}
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON response: {exc}", "rows": []}
    except Exception as exc:
        return {"error": str(exc), "rows": []}
