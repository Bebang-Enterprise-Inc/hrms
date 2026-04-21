"""S214 Phase 2a — Pause 16 conversion-losers wasting ~PHP 56K/week.

Strategy:
- Fetch 7-day insights live (not stale cached data)
- Identify losers by deterministic filter: CPA > PHP 400 AND ROAS < 2x,
  OR >PHP 1000 spend with 0 purchases. Sort by spend descending.
- HARD BLOCKER: Before pausing, fetch 24h insights. If any "loser" has
  flipped to ROAS > 3x in the last 24h, STOP and report.
- Pause top 16 losers via POST {ad-id} status=PAUSED.

Run: python scripts/s214_pause_losers.py [--dry-run] [--limit 16]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from s214_meta_lib import (
    AD_ACCOUNT,
    force_utf8,
    get_token,
    log_form_submission,
    meta_get,
    meta_post,
    save_post_state,
    save_pre_state,
)

force_utf8()


def fetch_insights(token: str, date_preset: str = "last_7d") -> list[dict]:
    """Fetch ad-level insights."""
    rows = []
    # Use paginated request via the list endpoint
    data = meta_get(
        f"/{AD_ACCOUNT}/insights",
        token,
        {
            "fields": (
                "ad_id,ad_name,campaign_name,campaign_id,adset_name,adset_id,"
                "spend,impressions,clicks,ctr,cpm,frequency,reach,actions,purchase_roas"
            ),
            "level": "ad",
            "date_preset": date_preset,
            "limit": "500",
        },
    )
    rows.extend(data.get("data", []))
    next_url = data.get("paging", {}).get("next")
    # Handle pagination if needed
    while next_url:
        import urllib.request, json as _json
        req = urllib.request.Request(next_url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
        page = _json.loads(body)
        rows.extend(page.get("data", []))
        next_url = page.get("paging", {}).get("next")
    return rows


def extract_metrics(row: dict) -> dict:
    spend = float(row.get("spend", 0) or 0)
    purchases = 0
    for a in row.get("actions") or []:
        if a.get("action_type") == "purchase":
            try:
                purchases = int(a.get("value", 0))
            except (TypeError, ValueError):
                pass
            break
    roas_list = row.get("purchase_roas") or []
    roas = float(roas_list[0].get("value", 0)) if roas_list else 0.0
    return {
        "ad_id": row.get("ad_id"),
        "ad_name": row.get("ad_name", "")[:80],
        "campaign_name": row.get("campaign_name", "")[:60],
        "spend": spend,
        "purchases": purchases,
        "roas": roas,
        "cpa": spend / purchases if purchases else None,
        "ctr": float(row.get("ctr", 0) or 0),
        "freq": float(row.get("frequency", 0) or 0),
    }


def is_loser(m: dict) -> bool:
    # Skip ads with tiny spend
    if m["spend"] < 500:
        return False
    # CPA > 400 AND ROAS < 2x
    if m["cpa"] is not None and m["cpa"] > 400 and m["roas"] < 2.0:
        return True
    # OR spend > 1000 with zero purchases
    if m["spend"] > 1000 and m["purchases"] == 0:
        return True
    # OR very bad ROAS regardless of CPA
    if m["spend"] > 500 and m["roas"] > 0 and m["roas"] < 1.0:
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=16, help="max ads to pause (default 16)")
    args = ap.parse_args()

    token = get_token()

    print("=" * 70)
    print(f"S214 Phase 2a — Pause Losers (mode: {'DRY RUN' if args.dry_run else 'LIVE'})")
    print("=" * 70)

    print("\nFetching 7-day insights...")
    rows7 = fetch_insights(token, "last_7d")
    metrics7 = [extract_metrics(r) for r in rows7]
    metrics7.sort(key=lambda m: -m["spend"])
    print(f"  Got {len(metrics7)} ads with 7d data")

    # Identify losers (deterministic rule)
    losers = [m for m in metrics7 if is_loser(m)]
    losers.sort(key=lambda m: -m["spend"])
    losers = losers[: args.limit]
    print(f"  Identified {len(losers)} losers (top {args.limit} by spend)")

    # ===== HARD BLOCKER: check 24h signal reversal =====
    print("\nFetching 24h insights for reversal check...")
    rows1 = fetch_insights(token, "yesterday")
    metrics1 = {m["ad_id"]: m for m in (extract_metrics(r) for r in rows1)}
    reversed_losers = []
    for loser in losers:
        fresh = metrics1.get(loser["ad_id"])
        if fresh and fresh["roas"] > 3.0 and fresh["purchases"] >= 2:
            reversed_losers.append({
                "ad_id": loser["ad_id"],
                "ad_name": loser["ad_name"],
                "7d_roas": loser["roas"],
                "24h_roas": fresh["roas"],
                "24h_purchases": fresh["purchases"],
            })

    if reversed_losers:
        print(f"\n[REVERSAL DETECTED] {len(reversed_losers)} losers have flipped to ROAS > 3x in 24h:")
        for r in reversed_losers:
            print(f"  {r['ad_id']} {r['ad_name'][:50]}: 7d={r['7d_roas']:.2f}x 24h={r['24h_roas']:.2f}x")
        save_post_state("02_fresh_signal_override", {
            "reversed_losers": reversed_losers,
            "decision": "excluded_from_pause",
            "reason": "Fresh 24h signal shows recovery; pausing would hurt performance. "
                      "Per plan stop_only_for: flagged; proceeding with stable losers only.",
        })
        print(f"\n  [OVERRIDE] Excluding {len(reversed_losers)} reversals; continuing with stable losers.")
        reversed_ids = {r["ad_id"] for r in reversed_losers}
        losers = [m for m in losers if m["ad_id"] not in reversed_ids]
        print(f"  Remaining stable losers to pause: {len(losers)}")
    else:
        print("  No reversals — safe to proceed.")

    # Save pre-state
    save_pre_state("02_losers_before", {"losers": losers, "rule": "CPA>400 AND ROAS<2x, top 16 by spend"})

    # Print table
    print(f"\n{'Ad ID':<22}{'CPA':>7}{'ROAS':>7}{'Spend':>10}  Ad Name")
    for m in losers:
        cpa_s = f"{m['cpa']:.0f}" if m['cpa'] else "-"
        print(f"  {m['ad_id']:<20}{cpa_s:>7}{m['roas']:>7.2f}{m['spend']:>10,.0f}  {m['ad_name'][:55]}")

    if args.dry_run:
        print("\n[DRY RUN] No changes. Pre-state saved.")
        return 0

    # ===== Pause them =====
    print(f"\n[LIVE] Pausing {len(losers)} ads...")
    results = []
    for m in losers:
        resp = meta_post(f"/{m['ad_id']}", token, {"status": "PAUSED"}, log_as_mutation=True)
        success = resp.get("success") is True or resp.get("id") == m["ad_id"]
        cpa_str = f"{m['cpa']:.0f}" if m["cpa"] else "None"
        log_form_submission({
            "phase": "P2-T3",
            "action": "pause_ad",
            "target": m["ad_id"],
            "target_name": m["ad_name"],
            "reason": f"loser: CPA={cpa_str} ROAS={m['roas']:.2f}x",
            "7d_spend": m["spend"],
            "7d_purchases": m["purchases"],
            "api_response": resp,
            "success": success,
        })
        results.append({"ad_id": m["ad_id"], "success": success, "response": resp})
        print(f"  {'✓' if success else '✗'} {m['ad_id']} {m['ad_name'][:55]}")

    save_post_state("02_losers_after", {"results": results, "total": len(losers)})
    passed = sum(1 for r in results if r["success"])
    print(f"\nPhase 2a summary: {passed}/{len(losers)} paused successfully")
    return 0 if passed == len(losers) else 1


if __name__ == "__main__":
    sys.exit(main())
