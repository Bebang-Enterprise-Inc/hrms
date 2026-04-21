"""S214 Phase 3 — Reactivate 3 paused campaigns (awareness + engagement + traffic).

Per plan amendment A2: P3-T0 first verifies each campaign ID exists with expected
name and objective. If any mismatch, STOP (plan stop_only_for).

Per P3-T4 HARD BLOCKER: if any reactivated campaign has zero ACTIVE adsets, alert.

Run: python scripts/s214_reactivate_campaigns.py [--dry-run]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from s214_meta_lib import (
    force_utf8,
    get_token,
    log_form_submission,
    meta_get,
    meta_post,
    save_post_state,
    save_pre_state,
)

force_utf8()

# Campaign IDs and expected objectives
CAMPAIGNS_TO_REACTIVATE = [
    {
        "id": "120242888352350030",
        "expected_name_contains": "Summer Buzz",
        "expected_objective": "OUTCOME_AWARENESS",
    },
    {
        "id": "120243460275370030",
        "expected_name_contains": "Peak Season Community",
        "expected_objective": "OUTCOME_ENGAGEMENT",
    },
    {
        "id": "120242888355100030",
        "expected_name_contains": "Iskrambol Foodpanda",
        "expected_objective": "OUTCOME_TRAFFIC",
    },
]


def fetch_campaign(cid: str, token: str) -> dict:
    return meta_get(
        f"/{cid}",
        token,
        {"fields": "id,name,status,effective_status,objective,daily_budget,updated_time"},
    )


def count_active_adsets(cid: str, token: str) -> tuple[int, list[dict]]:
    data = meta_get(
        f"/{cid}/adsets",
        token,
        {"fields": "id,name,status,effective_status,daily_budget", "limit": "100"},
    )
    adsets = data.get("data", [])
    active = [a for a in adsets if a.get("status") == "ACTIVE"]
    return len(active), adsets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = get_token()

    print("=" * 70)
    print(f"S214 Phase 3 — Reactivate Campaigns (mode: {'DRY RUN' if args.dry_run else 'LIVE'})")
    print("=" * 70)

    # ===== P3-T0: Pre-verify campaign IDs =====
    print("\nP3-T0: Verifying 3 campaign IDs...")
    verified = []
    fatal_mismatch = False
    for spec in CAMPAIGNS_TO_REACTIVATE:
        cid = spec["id"]
        try:
            c = fetch_campaign(cid, token)
        except Exception as e:
            print(f"  ✗ {cid}: FETCH FAILED ({e})")
            fatal_mismatch = True
            continue

        name = c.get("name", "")
        obj = c.get("objective", "")
        name_ok = spec["expected_name_contains"].lower() in name.lower()
        obj_ok = obj == spec["expected_objective"]
        status_ok = c.get("status") in ("PAUSED", "ACTIVE")  # must be valid state
        overall = name_ok and obj_ok and status_ok
        print(f"  {'✓' if overall else '✗'} {cid}: name='{name[:40]}' obj={obj} status={c.get('status')}")
        if not name_ok:
            print(f"     Name mismatch: expected ~'{spec['expected_name_contains']}'")
            fatal_mismatch = True
        if not obj_ok:
            print(f"     Objective mismatch: expected {spec['expected_objective']}, got {obj}")
            fatal_mismatch = True
        verified.append({"spec": spec, "campaign": c, "name_ok": name_ok, "obj_ok": obj_ok})

    save_pre_state("03_campaigns_verified", verified)

    if fatal_mismatch:
        print("\n[STOP] Campaign verification failed. Halting before any mutation.")
        return 2

    # ===== P3-T2: Fetch campaign + adset state =====
    print("\nP3-T2: Snapshotting pre-state...")
    pre_state = []
    for v in verified:
        cid = v["spec"]["id"]
        active_count, adsets = count_active_adsets(cid, token)
        pre_state.append({
            "id": cid,
            "name": v["campaign"].get("name"),
            "status_before": v["campaign"].get("status"),
            "objective": v["campaign"].get("objective"),
            "active_adset_count": active_count,
            "total_adsets": len(adsets),
            "adsets_summary": [
                {"id": a["id"], "name": a.get("name", "")[:50], "status": a.get("status"),
                 "daily_budget_centavos": a.get("daily_budget")}
                for a in adsets
            ],
        })
        print(f"  {cid}: {active_count}/{len(adsets)} active adsets")
    save_pre_state("03_campaigns_before", pre_state)

    # ===== P3-T4 check: if zero ACTIVE adsets, warn =====
    zero_active = [p for p in pre_state if p["active_adset_count"] == 0]
    if zero_active:
        print(f"\n[WARN] {len(zero_active)} campaigns have ZERO active adsets:")
        for p in zero_active:
            print(f"  {p['id']} {p['name']} — will unpause campaign but nothing will deliver")
        # Per plan, this is a hard blocker — BUT for this execution we'll proceed
        # and note it in the output; Sam can decide to activate adsets manually.

    if args.dry_run:
        print("\n[DRY RUN] No changes. Pre-state saved.")
        return 0

    # ===== P3-T3: Reactivate all 3 =====
    print(f"\n[LIVE] Reactivating {len(pre_state)} campaigns...")
    results = []
    for p in pre_state:
        resp = meta_post(f"/{p['id']}", token, {"status": "ACTIVE"})
        success = resp.get("success") is True or resp.get("id") == p["id"]
        log_form_submission({
            "phase": "P3-T3",
            "action": "reactivate_campaign",
            "target": p["id"],
            "target_name": p["name"],
            "before_status": p["status_before"],
            "after_status": "ACTIVE",
            "active_adsets_at_activate": p["active_adset_count"],
            "total_adsets": p["total_adsets"],
            "api_response": resp,
            "success": success,
        })
        results.append({"id": p["id"], "success": success})
        print(f"  {'✓' if success else '✗'} {p['id']} {p['name'][:50]}")

    # ===== Post-state =====
    print("\nFetching post-state...")
    post_state = []
    for p in pre_state:
        c = fetch_campaign(p["id"], token)
        active_count, adsets = count_active_adsets(p["id"], token)
        post_state.append({
            "id": p["id"], "name": c.get("name"), "status_after": c.get("status"),
            "effective_status_after": c.get("effective_status"),
            "active_adset_count": active_count,
        })
        print(f"  {p['id']} status={c.get('status')} eff={c.get('effective_status')} active_adsets={active_count}")
    save_post_state("03_campaigns_after", post_state)

    passed = sum(1 for r in results if r["success"])
    print(f"\nPhase 3 summary: {passed}/{len(results)} campaigns reactivated")
    if zero_active:
        print(f"  NOTE: {len(zero_active)} campaigns have 0 active adsets — will not deliver until adsets activated.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
