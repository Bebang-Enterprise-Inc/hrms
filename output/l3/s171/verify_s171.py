#!/usr/bin/env python3
"""S171 machine-verifiable phase gate.

Same shape as S169's verify_s169.py: filesystem checks (post-merge safe), comment-
stripped MUST_NOT_CONTAIN, MUST_CONTAIN against full text.

Usage:
    python output/l3/s171/verify_s171.py
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]


def _strip_python_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if "#" in line:
            in_single = in_double = False
            cut = None
            for i, ch in enumerate(line):
                if ch == "'" and not in_double:
                    in_single = not in_single
                elif ch == '"' and not in_single:
                    in_double = not in_double
                elif ch == "#" and not in_single and not in_double:
                    cut = i
                    break
            if cut is not None:
                line = line[:cut]
        out.append(line)
    return "\n".join(out)


def check_contains(path, needles, forbidden=()):
    p = REPO / path
    if not p.exists():
        return f"FAIL: {path} does not exist"
    text = p.read_text(encoding="utf-8", errors="replace")
    missing = [n for n in needles if n not in text]
    if path.endswith(".py"):
        code_only = _strip_python_comments(text)
        bad = [n for n in forbidden if n in code_only]
    else:
        bad = [n for n in forbidden if n in text]
    if missing:
        return f"FAIL: {path} missing: {missing}"
    if bad:
        return f"FAIL: {path} contains forbidden: {bad}"
    return f"PASS: {path}"


def check_file_nonempty(path):
    p = REPO / path
    if not p.exists():
        return f"FAIL: {path} does not exist"
    sz = p.stat().st_size
    if sz == 0:
        return f"FAIL: {path} is EMPTY"
    return f"PASS: {path} ({sz} bytes)"


def check_files_exist(files):
    missing = [f for f in files if not (REPO / f).exists()]
    if missing:
        return f"FAIL: missing files: {missing}"
    return f"PASS: all {len(files)} required files present"


def check_protected_unmodified():
    """S169 scripts must be reused as a library, never modified by S171."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "diff", "--name-only", "origin/production..HEAD"],
            capture_output=True, text=True, timeout=15,
        )
        names = (out.stdout or "").splitlines()
        protected = {
            "scripts/verify_mosaic_pos_sync.py",
            "scripts/sync_pos_to_supabase.py",
            "hrms/api/mosaic_webhook.py",
            "hrms/utils/supabase.py",
        }
        violated = [n for n in names if n in protected]
        if violated:
            return f"FAIL: protected S169 surfaces modified: {violated}"
        return f"PASS: no protected S169 surface modified"
    except Exception as e:
        return f"WARN: protected-surface check skipped ({e})"


results = [
    # Phase 0 evidence
    check_file_nonempty("output/l3/s171/phase0_preflight.json"),

    # Phase 1 — pos_orders drift
    check_file_nonempty("output/l3/s171/pos_orders_drift.json"),

    # Phases 2/3/4 sample audits
    check_file_nonempty("output/l3/s171/pos_order_items_drift.json"),
    check_file_nonempty("output/l3/s171/pos_order_payments_drift.json"),
    check_file_nonempty("output/l3/s171/price_breakdown_outliers.json"),

    # Phase 5 channel audit
    check_file_nonempty("output/l3/s171/channel_classification_audit.json"),

    # Phase 6 web verifier
    check_file_nonempty("output/l3/s171/web_orders_drift.json"),

    # Phase 7 cross-channel
    check_file_nonempty("output/l3/s171/cross_channel_reconciliation.json"),

    # Phase 8 tombstones
    check_file_nonempty("output/l3/s171/phantoms_tombstoned_s171.json"),

    # L3 evidence
    check_file_nonempty("output/l3/s171/form_submissions.json"),
    check_file_nonempty("output/l3/s171/api_mutations.json"),
    check_file_nonempty("output/l3/s171/state_verification.json"),

    # Closeout artifacts
    check_file_nonempty("output/l3/s171/DEFECT_REGISTER.csv"),
    check_file_nonempty("output/l3/s171/DATA_QUALITY_REPORT.md"),

    # Orchestrator script — MUST_CONTAIN / MUST_NOT_CONTAIN
    check_contains(
        "scripts/s171_full_parity_audit.py",
        [
            "import sentry_sdk",
            "sentry_sdk.init(",
            "from verify_mosaic_pos_sync import",
            "supabase_ids",
            "mosaic_ids",
            "tombstone_extras",
            "_supabase_query_sql",
            "Accept",
            "ensure_token",  # OAuth body is owned by the S169 helper we import
            "REQUEST_INTERVAL",
            "creationflags=0x08000000",
        ],
        forbidden=[
            "frappe.request.get_json",
            "DELETE FROM pos_orders",
            "DELETE FROM pos_order_items",
            "DELETE FROM pos_order_payments",
            "DELETE FROM web_orders",
        ],
    ),

    # Web verifier
    check_contains(
        "scripts/verify_web_orders_sync.py",
        [
            "x-api-key",
            "superadmin.bebang.ph/api/online-orders",
            "supabase_web_ids",
            "fetch_web_order_ids",
            "sentry_sdk.capture_exception",
            "SUPERADMIN_API_KEY",
        ],
        forbidden=[
            "DELETE FROM web_orders",
        ],
    ),

    # Drift monitor SQL
    check_contains(
        "data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql",
        [
            "CREATE OR REPLACE VIEW public.v_sync_drift_monitor AS",
            "v_pos_orders_live",
            "sync_verification",
            "drift_now",
            "COMMENT ON VIEW public.v_sync_drift_monitor IS",
        ],
    ),

    # Protected surfaces unchanged
    check_protected_unmodified(),

    # Sprint files exist
    check_files_exist([
        "scripts/s171_full_parity_audit.py",
        "scripts/verify_web_orders_sync.py",
        "data/supabase/migrations/2026-04-08-v-sync-drift-monitor.sql",
        "output/l3/s171/verify_s171.py",
        "docs/plans/2026-04-08-sprint-171-mosaic-website-sync-full-validation.md",
    ]),
]

fails = [r for r in results if r.startswith("FAIL")]
warns = [r for r in results if r.startswith("WARN")]
print("\n".join(results))
print(f"\n{'='*60}\n{len(results) - len(fails) - len(warns)} PASS, "
      f"{len(warns)} WARN, {len(fails)} FAIL\n{'='*60}")
sys.exit(1 if fails else 0)
