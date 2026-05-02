"""S232 migration applier — runs SQL files in scripts/s232_supabase_migrations/ in order.

Idempotent: every migration uses IF NOT EXISTS / IF NOT EXISTS patterns.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
MIG_DIR = REPO_ROOT / "scripts" / "s232_supabase_migrations"

PROJECT_REF = "csnniykjrychgajfrgua"
SQL_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def _doppler(name: str) -> str:
    val = os.environ.get(name, "")
    if val:
        return val
    r = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", name,
         "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True, timeout=15,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def main():
    token = _doppler("SUPABASE_MGMT_TOKEN")
    if not token:
        print("ERROR: SUPABASE_MGMT_TOKEN missing")
        sys.exit(1)

    only = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(MIG_DIR.glob("*.sql"))
    if only:
        files = [f for f in files if only in f.name]

    print(f"Applying {len(files)} migration(s) from {MIG_DIR}")
    for f in files:
        print(f"\n--- {f.name} ---")
        sql = f.read_text(encoding="utf-8")
        # Run in a single query — Supabase Management API SQL endpoint accepts multi-statement
        r = httpx.post(
            SQL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"query": sql},
            timeout=300,
        )
        if r.status_code >= 400:
            print(f"  FAIL: HTTP {r.status_code}: {r.text[:500]}")
            sys.exit(2)
        try:
            data = r.json()
            if isinstance(data, list) and data:
                print(f"  Result: {data[:5]}")
            else:
                print(f"  OK")
        except Exception:
            print(f"  OK (non-JSON response)")
    print("\nAll migrations applied.")


if __name__ == "__main__":
    main()
