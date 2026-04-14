"""Supabase migration runner — idempotent, checksum-verified, tracked.

Applies SQL migrations from supabase/migrations/ in filename order. Tracks
applied migrations in public.schema_migrations with SHA256 checksum, so:

  - Re-running is safe (skips already-applied)
  - Tampering is detected (checksum mismatch errors out)
  - New migrations apply automatically
  - Per-migration timing is logged

Usage:
    python scripts/apply_migration.py                    # apply pending
    python scripts/apply_migration.py --dry-run          # show pending only
    python scripts/apply_migration.py --file <path>      # apply a specific file
    python scripts/apply_migration.py --status           # show migration history

Env:
    SUPABASE_MGMT_TOKEN        required for DDL via Management API
    SUPABASE_PROJECT_REF       default csnniykjrychgajfrgua
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "csnniykjrychgajfrgua")


def doppler_get(key: str) -> str | None:
    r = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", key,
         "--project", "bei-erp", "--config", "dev", "--plain"],
        capture_output=True, text=True, timeout=15,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def get_mgmt_token() -> str:
    token = (os.environ.get("SUPABASE_MGMT_TOKEN") or "").strip()
    if token:
        return token
    token = doppler_get("SUPABASE_MGMT_TOKEN")
    if token:
        return token
    raise SystemExit("SUPABASE_MGMT_TOKEN not available (env or Doppler)")


def sql(query: str, token: str) -> list:
    """Execute SQL via Supabase Management API."""
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query},
        timeout=120,
    )
    if not r.ok:
        raise RuntimeError(f"SQL failed ({r.status_code}): {r.text[:500]}")
    try:
        return r.json() if r.text else []
    except Exception:
        return []


def ensure_tracking_table(token: str) -> None:
    """Create schema_migrations table if missing. Idempotent."""
    sql("""
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            version         TEXT PRIMARY KEY,
            checksum        TEXT NOT NULL,
            script_path     TEXT NOT NULL,
            applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            applied_by      TEXT DEFAULT current_user,
            duration_ms     INTEGER,
            content_length  INTEGER
        );
        COMMENT ON TABLE public.schema_migrations IS
            'Applied Supabase migrations. Managed by scripts/apply_migration.py. Do NOT edit manually.';
    """, token)


def load_applied(token: str) -> dict[str, dict]:
    rows = sql(
        "SELECT version, checksum, script_path, applied_at FROM public.schema_migrations ORDER BY version",
        token,
    )
    return {r["version"]: r for r in rows}


def list_migrations() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(p for p in MIGRATIONS_DIR.iterdir() if p.suffix == ".sql")


def compute_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def version_from_name(path: Path) -> str:
    """Extract version from filename (stem up to first underscore or full stem)."""
    return path.stem


def apply_migration(path: Path, token: str) -> None:
    version = version_from_name(path)
    checksum = compute_checksum(path)
    content = path.read_text(encoding="utf-8")

    print(f"  Applying {version}...")
    t0 = time.time()
    sql(content, token)
    duration_ms = int((time.time() - t0) * 1000)

    # Record in schema_migrations (safe escape via Management API parameterization via replace)
    escaped_version = version.replace("'", "''")
    escaped_checksum = checksum.replace("'", "''")
    escaped_path = str(path.relative_to(MIGRATIONS_DIR.parent.parent)).replace("\\", "/").replace("'", "''")
    sql(
        f"""
        INSERT INTO public.schema_migrations
            (version, checksum, script_path, applied_at, duration_ms, content_length)
        VALUES
            ('{escaped_version}', '{escaped_checksum}', '{escaped_path}',
             NOW(), {duration_ms}, {len(content)})
        ON CONFLICT (version) DO UPDATE SET
            checksum = EXCLUDED.checksum,
            applied_at = EXCLUDED.applied_at,
            duration_ms = EXCLUDED.duration_ms,
            content_length = EXCLUDED.content_length
        """,
        token,
    )
    print(f"    OK ({duration_ms} ms, {len(content)} chars)")


def cmd_status(token: str) -> int:
    ensure_tracking_table(token)
    applied = load_applied(token)
    pending = list_migrations()

    print("="*70)
    print("MIGRATION STATUS")
    print("="*70)
    print(f"Applied: {len(applied)}")
    for v, row in applied.items():
        print(f"  [x] {v}  applied_at={row['applied_at']}")

    pending_files = [p for p in pending if version_from_name(p) not in applied]
    print(f"\nPending: {len(pending_files)}")
    for p in pending_files:
        print(f"  [ ] {version_from_name(p)}  checksum={compute_checksum(p)[:16]}...")

    drift = []
    for p in pending:
        v = version_from_name(p)
        if v in applied and applied[v]["checksum"] != compute_checksum(p):
            drift.append((v, applied[v]["checksum"], compute_checksum(p)))
    if drift:
        print(f"\nCHECKSUM DRIFT ({len(drift)}):")
        for v, old, new in drift:
            print(f"  [!] {v}  applied={old[:16]} current={new[:16]}")
        return 1
    return 0


def cmd_apply(token: str, dry_run: bool = False, single_file: str | None = None) -> int:
    ensure_tracking_table(token)
    applied = load_applied(token)

    if single_file:
        paths = [Path(single_file)]
    else:
        paths = list_migrations()

    to_apply = []
    for p in paths:
        v = version_from_name(p)
        current_checksum = compute_checksum(p)
        if v in applied:
            if applied[v]["checksum"] != current_checksum:
                print(f"[!] CHECKSUM DRIFT for {v}: applied={applied[v]['checksum'][:16]}... vs current={current_checksum[:16]}...")
                print(f"    Migration file modified after apply. Investigate — aborting.")
                return 2
            continue
        to_apply.append(p)

    if not to_apply:
        print("[OK] No pending migrations.")
        return 0

    print(f"{'[DRY RUN] ' if dry_run else ''}Pending migrations: {len(to_apply)}")
    for p in to_apply:
        print(f"  - {version_from_name(p)} ({p.stat().st_size} bytes)")

    if dry_run:
        return 0

    for p in to_apply:
        apply_migration(p, token)

    print(f"\n[OK] Applied {len(to_apply)} migration(s).")
    return 0


def cmd_backfill(token: str, through_version: str | None = None) -> int:
    """Record historical migrations as applied without re-running them.

    Use when bootstrapping tracking on a DB where migrations have been applied
    manually. With --through, marks all migrations up to and including that
    version as applied. Without --through, marks ALL currently-pending as applied.
    """
    ensure_tracking_table(token)
    applied = load_applied(token)
    all_paths = list_migrations()

    if through_version:
        # Backfill only up to the specified version (exclusive of newer ones)
        target = []
        for p in all_paths:
            v = version_from_name(p)
            if v in applied:
                continue
            target.append(p)
            if v == through_version:
                break
    else:
        target = [p for p in all_paths if version_from_name(p) not in applied]

    if not target:
        print("[OK] Nothing to backfill.")
        return 0

    print(f"Backfilling {len(target)} migration(s) as already-applied (no SQL run):")
    for p in target:
        v = version_from_name(p)
        checksum = compute_checksum(p)
        content_len = p.stat().st_size
        escaped_version = v.replace("'", "''")
        escaped_checksum = checksum.replace("'", "''")
        escaped_path = str(p.relative_to(MIGRATIONS_DIR.parent.parent)).replace("\\", "/").replace("'", "''")
        sql(
            f"""
            INSERT INTO public.schema_migrations
                (version, checksum, script_path, applied_at, applied_by, duration_ms, content_length)
            VALUES
                ('{escaped_version}', '{escaped_checksum}', '{escaped_path}',
                 NOW(), 'backfill', 0, {content_len})
            ON CONFLICT (version) DO NOTHING
            """,
            token,
        )
        print(f"  [backfilled] {v}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Supabase migration runner")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--file", type=str, help="Apply a single migration file")
    parser.add_argument("--backfill", action="store_true",
                        help="Mark pending migrations as already-applied without running")
    parser.add_argument("--through", type=str, default=None,
                        help="With --backfill: mark as applied up to and including this version")
    args = parser.parse_args()

    token = get_mgmt_token()

    if args.status:
        return cmd_status(token)
    if args.backfill:
        return cmd_backfill(token, through_version=args.through)
    return cmd_apply(token, dry_run=args.dry_run, single_file=args.file)


if __name__ == "__main__":
    sys.exit(main())
