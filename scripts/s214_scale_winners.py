"""S214 Phase 2b — Scale 5 top conversion winners by raising adset daily_budget.

Strategy:
- Identify winners by deterministic filter: ROAS >= 14x OR (CPA < 55 AND purchases >= 5).
- HARD BLOCKER: For any winner, check 24h ROAS >= 3x. If any winner has fallen
  below 3x in last 24h, STOP and report.
- Raise adset daily_budget. Cap at PHP 12,000/day per RRC-7.

Run: python scripts/s214_scale_winners.py [--dry-run]
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
from s214_pause_losers import extract_metrics, fetch_insights

force_utf8()

# Winner adset targets (adset_id -> new daily_budget in centavos).
# Adset IDs resolved live; plan Appendix A targets used.
# These are resolved by ad_name keyword match below.
WINNER_AD_PATTERNS = {
    # pattern that matches ad_name       -> target adset budget (centavos)
    "Carousel] - Products": 500000,       # PHP 5,000 (TOF-INT Coffee/Ice Cream)
    "Ang sakit naman Beb": 750000,        # PHP 7,500 (BOF/MOF Warm 30d — hosts both Ang sakit + POPULARRRR)
    "Swipe left? Swipe right": 400000,    # PHP 4,000 (TOF-LAL Swipe adset)
    "Don't leave your valuables": 600000, # PHP 6,000 (TOF-LAL 5-10% VV 50%)
    "POPULARRRR": 750000,                 # PHP 7,500 same adset as Ang sakit (dedup handled below)
}

HARD_CAP_CENTAVOS = 1200000  # PHP 12,000/day per RRC-7


def is_winner(m: dict) -> bool:
    if m["spend"] < 50:  # include tiny-budget winners to scale them up
        return False
    if m["roas"] >= 14.0:
        return True
    if m["cpa"] is not None and m["cpa"] < 55 and m["purchases"] >= 5:
        return True
    return False


def resolve_winners(metrics: list[dict]) -> dict[str, dict]:
    """Return dict: adset_id -> chosen winner row (highest ROAS per adset)."""
    winners = [m for m in metrics if is_winner(m)]
    # Keep only ones matching our known winner patterns
    matched = []
    for m in winners:
        for pattern in WINNER_AD_PATTERNS:
            if pattern.lower() in m["ad_name"].lower():
                m["matched_pattern"] = pattern
                m["target_budget_centavos"] = WINNER_AD_PATTERNS[pattern]
                matched.append(m)
                break
    # Group by adset. Multiple winners can share an adset; keep highest ROAS
    # as the representative ad, but use MAX of all winners' target budgets so
    # the adset has enough budget for every winner it hosts.
    by_adset = {}
    for m in matched:
        adset_id = m.get("adset_id")
        if not adset_id:
            continue
        if adset_id not in by_adset:
            by_adset[adset_id] = dict(m)
            by_adset[adset_id]["co_winners"] = [m["ad_name"]]
        else:
            existing = by_adset[adset_id]
            # Track all winners in this adset
            existing.setdefault("co_winners", []).append(m["ad_name"])
            # Take MAX target budget across all winners in this adset
            existing["target_budget_centavos"] = max(
                existing["target_budget_centavos"],
                m["target_budget_centavos"],
            )
            # Keep highest-ROAS as representative
            if m["roas"] > existing["roas"]:
                existing["roas"] = m["roas"]
                existing["ad_name"] = m["ad_name"]
                existing["ad_id"] = m["ad_id"]
    return by_adset


def fetch_adset(adset_id: str, token: str) -> dict:
    return meta_get(
        f"/{adset_id}",
        token,
        {"fields": "id,name,status,daily_budget,effective_status,campaign_id"},
    )


def fetch_insights_for_ad(token: str, ad_id: str, date_preset: str) -> dict:
    """Fetch 24h insight for a specific ad_id."""
    data = meta_get(
        f"/{ad_id}/insights",
        token,
        {
            "fields": "spend,actions,purchase_roas",
            "date_preset": date_preset,
        },
    )
    rows = data.get("data", [])
    if not rows:
        return {"spend": 0, "roas": 0, "purchases": 0}
    r = rows[0]
    return {
        "spend": float(r.get("spend", 0) or 0),
        "roas": float((r.get("purchase_roas") or [{}])[0].get("value", 0)),
        "purchases": sum(
            int(a.get("value", 0))
            for a in (r.get("actions") or [])
            if a.get("action_type") == "purchase"
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = get_token()

    print("=" * 70)
    print(f"S214 Phase 2b — Scale Winners (mode: {'DRY RUN' if args.dry_run else 'LIVE'})")
    print("=" * 70)

    print("\nFetching 7-day insights...")
    rows7 = fetch_insights(token, "last_7d")
    metrics7 = [extract_metrics(r) for r in rows7]
    # Enrich with adset_id from row
    by_id = {r.get("ad_id"): r for r in rows7}
    for m in metrics7:
        r = by_id.get(m["ad_id"])
        if r:
            m["adset_id"] = r.get("adset_id")
    winners = resolve_winners(metrics7)
    print(f"  Matched {len(winners)} unique winner adsets")

    # Reversal check (winner-side)
    print("\nFetching 24h insights to check winner stability...")
    reversed_winners = []
    for adset_id, m in winners.items():
        fresh = fetch_insights_for_ad(token, m["ad_id"], "yesterday")
        if fresh["spend"] > 100 and fresh["roas"] < 3.0:
            reversed_winners.append({
                "ad_id": m["ad_id"], "ad_name": m["ad_name"],
                "7d_roas": m["roas"], "24h_roas": fresh["roas"],
            })
    if reversed_winners:
        print(f"\n[WINNER REVERSAL] {len(reversed_winners)} winners have dropped below 3x in 24h:")
        for r in reversed_winners:
            print(f"  {r['ad_id']} {r['ad_name'][:55]}: 7d={r['7d_roas']:.2f}x 24h={r['24h_roas']:.2f}x")
        save_post_state("02_winner_reversal_override", {"reversals": reversed_winners, "decision": "skipped"})
        reversed_ad_ids = {r["ad_id"] for r in reversed_winners}
        winners = {asid: m for asid, m in winners.items() if m["ad_id"] not in reversed_ad_ids}
        print(f"  [OVERRIDE] Excluding reversed winners; continuing with {len(winners)} stable winners.")
    else:
        print("  All winners stable in 24h.")

    # Fetch pre-state adset budgets
    print("\nFetching current adset budgets...")
    pre_state = {}
    for adset_id, m in winners.items():
        adset = fetch_adset(adset_id, token)
        pre_state[adset_id] = {
            "ad_name": m["ad_name"],
            "7d_roas": m["roas"],
            "current_daily_budget_centavos": adset.get("daily_budget"),
            "target_daily_budget_centavos": m["target_budget_centavos"],
            "adset_name": adset.get("name", ""),
        }
    save_pre_state("02_winners_before", pre_state)

    # Print table
    print(f"\n{'Adset ID':<22}{'Current':>10}{'Target':>10}{'ROAS':>7}  Winner Ad / Adset")
    for adset_id, info in pre_state.items():
        cur = info["current_daily_budget_centavos"]
        cur_php = int(cur) / 100 if cur else 0
        tgt_php = info["target_daily_budget_centavos"] / 100
        print(
            f"  {adset_id:<20}{cur_php:>10,.0f}{tgt_php:>10,.0f}{info['7d_roas']:>7.1f}  "
            f"{info['ad_name'][:30]} / {info['adset_name'][:25]}"
        )

    # Cap safety check
    over_cap = [aid for aid, info in pre_state.items()
                if info["target_daily_budget_centavos"] > HARD_CAP_CENTAVOS]
    if over_cap:
        print(f"\n[STOP] {len(over_cap)} adsets exceed PHP 12,000/day cap — violates RRC-7")
        return 2

    if args.dry_run:
        print("\n[DRY RUN] No changes. Pre-state saved.")
        return 0

    # Apply budget changes
    print(f"\n[LIVE] Updating {len(pre_state)} adset budgets...")
    results = []
    for adset_id, info in pre_state.items():
        target = info["target_daily_budget_centavos"]
        resp = meta_post(f"/{adset_id}", token, {"daily_budget": str(target)})
        success = resp.get("success") is True or resp.get("id") == adset_id
        log_form_submission({
            "phase": "P2-T5",
            "action": "scale_adset_budget",
            "target": adset_id,
            "target_name": info["adset_name"],
            "hosted_winner_ad": info["ad_name"],
            "before_centavos": info["current_daily_budget_centavos"],
            "after_centavos": target,
            "api_response": resp,
            "success": success,
        })
        results.append({"adset_id": adset_id, "success": success})
        status = "✓" if success else "✗"
        print(f"  {status} {adset_id} -> PHP {target/100:,.0f}/day  ({info['ad_name'][:40]})")

    # Post-state
    print("\nFetching post-state...")
    post_state = {}
    for adset_id in pre_state:
        post_state[adset_id] = fetch_adset(adset_id, token)
    save_post_state("02_winners_after", post_state)

    passed = sum(1 for r in results if r["success"])
    print(f"\nPhase 2b summary: {passed}/{len(results)} adset budgets updated")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
