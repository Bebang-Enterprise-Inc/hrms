"""S214 Phase 5 — Archive (NOT delete) ~193 ads in hard-error delivery state.

Error categories: custom audience unavailable (~73), generic rollup (~48),
dev-mode app creative (~33), auth expired (~12), deprecated crop (~10),
app deleted/sandbox (~6), others (~11). All have status=PAUSED and have
never delivered. Archiving removes them from default Ads Manager views
without losing history. Reversible (status=PAUSED) if needed.

HARD BLOCKER: archive = status=ARCHIVED, never DELETE request.
Rate pacing: sleep(0.5) between calls to stay under Meta ~200/hr limit.

Run: python scripts/s214_archive_error_ads.py [--dry-run] [--batch-size N]
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from s214_meta_lib import (
    AD_ACCOUNT,
    BASE,
    OUTPUT_DIR,
    force_utf8,
    get_token,
    log_form_submission,
    meta_post,
    save_post_state,
    save_pre_state,
)

force_utf8()

HARD_ERROR_STATUSES = ["WITH_ISSUES", "DISAPPROVED", "PENDING_REVIEW"]
RATE_SLEEP_SECONDS = 1.0  # conservative to avoid account-level rate limit (error code 17)
FAILURE_TOLERANCE = 0.05  # allow 5% failures


def fetch_all_error_ads(token: str) -> list[dict]:
    """Paginate all ads in error statuses."""
    ads = []
    params = {
        "fields": "id,name,status,effective_status,created_time,issues_info,campaign{name},adset{name}",
        "filtering": json.dumps([
            {"field": "effective_status", "operator": "IN", "value": HARD_ERROR_STATUSES}
        ]),
        "limit": "200",
        "access_token": token,
    }
    url = f"{BASE}/{AD_ACCOUNT}/ads?" + urllib.parse.urlencode(params)
    page = 1
    while url:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        if "error" in data:
            print(f"  API ERROR: {data['error']}")
            break
        batch = data.get("data", [])
        ads.extend(batch)
        print(f"  Page {page}: {len(batch)} ads (total {len(ads)})")
        url = data.get("paging", {}).get("next")
        page += 1
        if page > 30:
            break
        time.sleep(RATE_SLEEP_SECONDS)
    return ads


def has_hard_error(ad: dict) -> bool:
    issues = ad.get("issues_info") or []
    return any(i.get("error_type") == "HARD_ERROR" for i in issues)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-size", type=int, default=250, help="max ads to archive this run")
    args = ap.parse_args()

    token = get_token()

    print("=" * 70)
    print(f"S214 Phase 5 — Archive Error Ads (mode: {'DRY RUN' if args.dry_run else 'LIVE'})")
    print("=" * 70)

    print("\nFetching ALL ads in hard-error delivery state...")
    all_error_ads = fetch_all_error_ads(token)
    print(f"  Fetched {len(all_error_ads)} ads in WITH_ISSUES/DISAPPROVED/PENDING_REVIEW")

    hard_error = [a for a in all_error_ads if has_hard_error(a)]
    print(f"  {len(hard_error)} have HARD_ERROR")

    # Error category summary
    from collections import Counter
    cat_counts = Counter()
    for a in hard_error:
        for iss in (a.get("issues_info") or []):
            if iss.get("error_type") == "HARD_ERROR":
                cat_counts[iss.get("error_summary", "unknown")[:60]] += 1
    print("\n  Top error categories:")
    for cat, n in cat_counts.most_common(10):
        print(f"    {n:>4}  {cat}")

    to_archive = hard_error[: args.batch_size]
    save_pre_state("05_error_ads_before", {
        "total_fetched": len(all_error_ads),
        "hard_error_count": len(hard_error),
        "to_archive_count": len(to_archive),
        "error_categories": dict(cat_counts),
        "ad_ids": [a["id"] for a in to_archive],
    })

    if args.dry_run:
        print(f"\n[DRY RUN] Would archive {len(to_archive)} ads.")
        return 0

    # ===== Archive loop with rate pacing =====
    print(f"\n[LIVE] Archiving {len(to_archive)} ads (sleep {RATE_SLEEP_SECONDS}s between)...")
    started = time.time()
    archived = 0
    failures = []
    for i, ad in enumerate(to_archive, 1):
        # Retry with exponential backoff on transient errors
        resp = None
        last_err = None
        for attempt in range(3):
            try:
                resp = meta_post(f"/{ad['id']}", token, {"status": "ARCHIVED"}, log_as_mutation=False)
                break
            except Exception as e:
                last_err = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"  [{i}] transient error: {type(e).__name__}; retry in {wait}s")
                time.sleep(wait)
        if resp is None:
            failures.append({"ad_id": ad["id"], "name": ad.get("name", "")[:50],
                             "error": f"{type(last_err).__name__}: {last_err}"})
        else:
            success = resp.get("success") is True or resp.get("id") == ad["id"]
            if success:
                archived += 1
            else:
                failures.append({"ad_id": ad["id"], "name": ad.get("name", "")[:50], "response": resp})
        if i % 25 == 0 or i == len(to_archive):
            elapsed = time.time() - started
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i}/{len(to_archive)}] archived={archived} failures={len(failures)} "
                  f"elapsed={elapsed:.0f}s rate={rate:.1f}/s")
        time.sleep(RATE_SLEEP_SECONDS)

    elapsed_total = time.time() - started
    success_rate = archived / len(to_archive) if to_archive else 1.0

    log_form_submission({
        "phase": "P5-T3",
        "action": "bulk_archive_error_ads",
        "total_attempted": len(to_archive),
        "archived_count": archived,
        "failure_count": len(failures),
        "success_rate": success_rate,
        "elapsed_seconds": round(elapsed_total, 1),
        "within_tolerance": success_rate >= (1 - FAILURE_TOLERANCE),
    })

    save_post_state("05_error_ads_after", {
        "attempted": len(to_archive),
        "archived": archived,
        "failures": failures,
        "success_rate": success_rate,
        "elapsed_seconds": round(elapsed_total, 1),
    })

    # Also write succinct archive summary
    summary_path = OUTPUT_DIR / "archive_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_fetched": len(all_error_ads),
            "hard_error_count": len(hard_error),
            "archived_count": archived,
            "failure_count": len(failures),
            "success_rate": success_rate,
            "elapsed_seconds": round(elapsed_total, 1),
            "error_categories": dict(cat_counts),
        }, f, indent=2)

    print(f"\nPhase 5 summary: {archived}/{len(to_archive)} archived "
          f"({success_rate*100:.1f}% success, {elapsed_total:.0f}s elapsed)")
    if failures:
        print(f"  Failures: {len(failures)} — see post_state/05_error_ads_after.json")
    # Pass criterion: success_rate >= (1 - FAILURE_TOLERANCE) = 95%
    return 0 if success_rate >= (1 - FAILURE_TOLERANCE) else 1


if __name__ == "__main__":
    sys.exit(main())
