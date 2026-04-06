#!/usr/bin/env python3
"""S165 machine-verifiable phase gate. Runs from filesystem, not self-report."""
import subprocess, sys, pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]


def check_contains(path, needles):
    p = REPO / path
    if not p.exists():
        return f"FAIL: {path} does not exist"
    text = p.read_text(encoding='utf-8')
    missing = [n for n in needles if n not in text]
    return f"FAIL: {path} missing: {missing}" if missing else f"PASS: {path}"


def check_diff_includes(branch, files):
    out = subprocess.run(["git", "diff", "--name-only", f"origin/production..{branch}"],
                         capture_output=True, text=True, cwd=REPO)
    diff = out.stdout.split()
    missing = [f for f in files if f not in diff]
    return f"FAIL: branch diff missing: {missing}" if missing else f"PASS: branch diff includes all required files"


results = [
    check_contains("scripts/verify_mosaic_pos_sync.py", [
        # Core function
        "def fetch_mosaic_count(",
        '.get("meta", {}).get("total"',
        "sync_verification",
        "spaces/AAQA3NVVR6c",
        # CB3: module-alias import + global propagation
        "import sync_pos_to_supabase as sps",
        "sps.SUPABASE_KEY =",
        "sps.SUPABASE_MGMT_TOKEN =",
        # CB5: Sentry fail-fast
        "sentry_sdk.init",
        "sys.exit(2)",
        # MW1: reinstall SIGINT
        "signal.signal(signal.SIGINT",
        # HW4: window ends at yesterday
        "datetime.now(PHT).date() - timedelta(days=1)",
        # HW1: PostgREST count=exact pattern
        "content-range",
        # CLI flags
        "--days",
        "--no-heal",
        "--dry-run",
        # MW2: retry pattern for count-only fetch
        "MAX_RETRIES",
        "RATE_LIMIT_WAIT",
    ]),
    check_contains("data/supabase/migrations/2026-04-06-create-sync-verification.sql", [
        "CREATE TABLE IF NOT EXISTS sync_verification",
        "healed", "unresolved", "api_error",
    ]),
    check_contains(".github/workflows/daily-pos-sync.yml", [
        "0 2-16 * * *",
        "30 16 * * *",
        "verify-sync:",
        "verify_mosaic_pos_sync.py",
        "github.event.schedule == '30 16 * * *'",
        # CB1: boolean fix
        "inputs.skip_verify != 'true'",
        "inputs.skip_anomaly != 'true'",
        "type: boolean",
        # CB2: concurrency + timeout
        "concurrency:",
        "group: daily-pos-sync",
        "timeout-minutes: 50",
    ]),
    check_diff_includes("s165-mosaic-sync-verification", [
        "scripts/verify_mosaic_pos_sync.py",
        "data/supabase/migrations/2026-04-06-create-sync-verification.sql",
        ".github/workflows/daily-pos-sync.yml",
        # MW8: L3 evidence files must be committed
        "output/l3/s165/form_submissions.json",
        "output/l3/s165/api_mutations.json",
        "output/l3/s165/state_verification.json",
        "output/l3/s165/verification_run.log",
        "output/l3/s165/verify_s165.py",
    ]),
]

for r in results:
    print(r)

if any(r.startswith("FAIL") for r in results):
    sys.exit(1)
print("\nAll S165 verification checks passed.")
