"""S214 Phase 1 — Disable broken EMERGENCY rule + extend Sales OFF to 10 PM PHT.

Rules mutated:
  1. 888035557619357  BEB: EMERGENCY - Pause ALL if spend > 100K  →  status=DISABLED
  2. 1539999288125943 BEB: Sales OFF at 6PM                        →  schedule added: fire 22:00-22:59 PHT

Schedule format per manage_meta_ad_rules.py daily_schedule() helper:
  {"schedule_type": "CUSTOM",
   "schedule": [{"start_minute": N, "end_minute": N, "days": [d]} for d in range(7)]}

Run: python scripts/s214_rule_fix.py [--dry-run]
"""
import argparse
import json
import sys

sys.path.insert(0, str((__import__("pathlib").Path(__file__).parent).resolve()))
from s214_meta_lib import (
    TMP_DIR,
    force_utf8,
    get_token,
    log_form_submission,
    meta_get,
    meta_post,
    save_post_state,
    save_pre_state,
)

force_utf8()

EMERGENCY_RULE_ID = "888035557619357"
SALES_OFF_RULE_ID = "1539999288125943"

# Sales OFF rule — Meta schedule_spec uses ACCOUNT-TIMEZONE minutes (not UTC).
# BEI account timezone is Asia/Manila. Current "6 PM" rule has start_minute=1080
# (18 * 60). To fire at 10 PM PHT: 22 * 60 = 1320.
# Keep the same "point-in-time" pattern (start == end) as the current rule.
SALES_OFF_NEW_SCHEDULE = {
    "schedule_type": "CUSTOM",
    "schedule": [
        {"start_minute": 1320, "end_minute": 1320, "days": [d]}
        for d in range(7)  # 0=Monday ... 6=Sunday per Meta convention
    ],
}


def fetch_rule(rule_id: str, token: str) -> dict:
    # Meta single-rule GET uses `schedule_spec` (adrules_library LIST returned `schedule`
    # — different field name in different endpoints).
    return meta_get(
        f"/{rule_id}",
        token,
        {"fields": "id,name,status,schedule_spec,evaluation_spec,execution_spec,updated_time"},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print the 2 changes but do nothing")
    args = ap.parse_args()

    token = get_token()

    print("=" * 70)
    print("S214 Phase 1 — Rule Fix")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 70)

    # ===== Fetch pre-state =====
    print("\nFetching pre-state of both rules...")
    rule_emergency = fetch_rule(EMERGENCY_RULE_ID, token)
    rule_salesoff = fetch_rule(SALES_OFF_RULE_ID, token)

    pre_state = {
        "emergency": rule_emergency,
        "sales_off": rule_salesoff,
    }
    save_pre_state("01_rules_before", pre_state)
    print(f"  Emergency rule status: {rule_emergency.get('status')}")
    print(f"  Sales OFF rule status: {rule_salesoff.get('status')}")
    print(f"  Sales OFF current schedule_spec: {rule_salesoff.get('schedule_spec', '(empty)')}")

    # ===== Report planned changes =====
    print("\nPlanned changes:")
    print(f"  [1] Rule {EMERGENCY_RULE_ID} 'BEB: EMERGENCY' -> status=DISABLED")
    print(f"  [2] Rule {SALES_OFF_RULE_ID} 'BEB: Sales OFF at 6PM' -> fire at 22:00 PHT daily (minute 1320)")
    print(f"      new schedule_spec: {json.dumps(SALES_OFF_NEW_SCHEDULE)[:120]}...")

    if args.dry_run:
        print("\n[DRY RUN] No changes made. Pre-state saved.")
        return 0

    # ===== Mutation 1: disable EMERGENCY rule =====
    print("\n[LIVE] Disabling EMERGENCY rule...")
    resp1 = meta_post(f"/{EMERGENCY_RULE_ID}", token, {"status": "DISABLED"})
    print(f"  Response: {resp1}")
    success1 = resp1.get("success") is True or resp1.get("id") == EMERGENCY_RULE_ID
    log_form_submission({
        "phase": "P1-T5",
        "action": "disable_rule",
        "target": EMERGENCY_RULE_ID,
        "target_name": "BEB: EMERGENCY - Pause ALL if spend > 100K",
        "before_status": rule_emergency.get("status"),
        "after_status": "DISABLED",
        "api_response": resp1,
        "success": success1,
    })

    # ===== Mutation 2: update Sales OFF schedule =====
    print("\n[LIVE] Updating Sales OFF rule schedule...")
    resp2 = meta_post(
        f"/{SALES_OFF_RULE_ID}",
        token,
        {"schedule_spec": json.dumps(SALES_OFF_NEW_SCHEDULE)},
    )
    print(f"  Response: {resp2}")
    success2 = resp2.get("success") is True or resp2.get("id") == SALES_OFF_RULE_ID

    fallback_applied = False
    if not success2:
        print("\n[LIVE] Schedule update failed — falling back to DISABLING Sales OFF rule entirely.")
        print("  (Per plan fallback: disable Sales OFF, rely on Sales ON 9AM + human attention.)")
        resp2b = meta_post(f"/{SALES_OFF_RULE_ID}", token, {"status": "DISABLED"})
        print(f"  Fallback response: {resp2b}")
        fallback_applied = resp2b.get("success") is True or resp2b.get("id") == SALES_OFF_RULE_ID
        resp2 = {"primary": resp2, "fallback": resp2b}

    log_form_submission({
        "phase": "P1-T5",
        "action": "update_rule_schedule" if not fallback_applied else "disable_rule_as_fallback",
        "target": SALES_OFF_RULE_ID,
        "target_name": "BEB: Sales OFF at 6PM",
        "before_schedule": rule_salesoff.get("schedule_spec"),
        "attempted_new_schedule": SALES_OFF_NEW_SCHEDULE,
        "fallback_applied": fallback_applied,
        "api_response": resp2,
        "success": success2 or fallback_applied,
    })

    # ===== Fetch post-state =====
    print("\nFetching post-state...")
    post_emergency = fetch_rule(EMERGENCY_RULE_ID, token)
    post_salesoff = fetch_rule(SALES_OFF_RULE_ID, token)
    post_state = {
        "emergency": post_emergency,
        "sales_off": post_salesoff,
        "fallback_applied": fallback_applied,
    }
    save_post_state("01_rules_after", post_state)
    print(f"  Emergency rule now: {post_emergency.get('status')}")
    print(f"  Sales OFF rule now: status={post_salesoff.get('status')} schedule_spec={post_salesoff.get('schedule_spec')}")

    # ===== Summary =====
    overall_success = success1 and (success2 or fallback_applied)
    print("\n" + "=" * 70)
    print(f"Phase 1 status: {'PASS' if overall_success else 'FAIL'}")
    print(f"  Emergency rule: {rule_emergency.get('status')} -> {post_emergency.get('status')} (expected DISABLED)")
    if fallback_applied:
        print(f"  Sales OFF: disabled (FALLBACK — schedule update rejected)")
    else:
        print(f"  Sales OFF: schedule updated to 22:00 PHT (minute 1320)")
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
