"""S214 Phase 4 — Create 3 new ads from viral organic posts via object_story_id.

Pattern per .claude/skills/meta-ads/references/api-reference.md Pattern 2:
  1. POST /act_*/adcreatives with object_story_id + call_to_action -> creative_id
  2. POST /act_*/ads with creative={creative_id: X} + adset_id + status=PAUSED

All 3 ads start PAUSED so Sam reviews + unpauses + narrows targeting manually
(esp. Post 2 Montalban which ideally wants a new geo-targeted adset).

HARD BLOCKER RRC-2: use object_story_id only, NEVER object_story_spec + link_data.
HARD BLOCKER RRC-1: no promo/discount copy in creative name or CTA link.
HARD BLOCKER RRC-8: use creationflags=CREATE_NO_WINDOW for subprocess (inherited from s214_meta_lib).

Run: python scripts/s214_boost_viral_posts.py [--dry-run]
"""
import argparse
import json
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

# Verified clean against 3,904 historical ads (see fact_check.md CLAIM-7).
BOOSTS = [
    {
        "post_id": "102628625216977_1266416878948597",
        "label": "Apr16-TagAFriend-SikatArtista",
        "creative_name": "S214 Boost - Sikat na Artista (Tag-a-Friend)",
        "ad_name": "S214 - [Post] - Tag-a-Friend - Sikat na Artista (Apr 16)",
        "campaign_id": "120243460275370030",   # Peak Season Community
        "target_adset_criterion": "metro_manila",  # find existing adset
        "cta_type": "LEARN_MORE",
        "cta_link": "https://www.facebook.com/bebanghalohalo",
        "url_tags": "utm_source=meta&utm_medium=paid&utm_campaign=s214_community_engagement",
        "expected_roas_driver": "community/comments (974 comments organic)",
    },
    {
        "post_id": "102628625216977_1260249656231986",
        "label": "Apr08-Montalban-StoreOpening",
        "creative_name": "S214 Boost - Nasa Montalban na si Bebang (Store Opening)",
        "ad_name": "S214 - [Post] - Nasa Montalban na si Bebang (Apr 8)",
        "campaign_id": "120242888352350030",   # Summer Buzz Awareness
        "target_adset_criterion": "metro",  # broadest existing adset; user can narrow geo after
        "cta_type": "ORDER_NOW",
        "cta_link": "https://www.foodpanda.ph/chain/cw3mi/bebang-halo-halo",
        "url_tags": "utm_source=meta&utm_medium=paid&utm_campaign=s214_montalban_awareness",
        "expected_roas_driver": "store opening shares (395 organic shares)",
    },
    {
        "post_id": "102628625216977_1267949595461992",
        "label": "Apr18-GrabengPressure-MoodMeme",
        "creative_name": "S214 Boost - Grabeng Pressure (Mood Meme)",
        "ad_name": "S214 - [Post] - Grabeng pressure naman to beb (Apr 18)",
        "campaign_id": "120243460275370030",   # Peak Season Community
        "target_adset_criterion": "metro_manila",
        "cta_type": "ORDER_NOW",
        "cta_link": "https://www.foodpanda.ph/chain/cw3mi/bebang-halo-halo",
        "url_tags": "utm_source=meta&utm_medium=paid&utm_campaign=s214_mood_meme_conversion",
        "expected_roas_driver": "viral mood meme shares (412 organic shares)",
    },
]

# Brand forbidden words (RRC-1)
FORBIDDEN_COPY_PATTERNS = ["discount", "promo", "sale", "bogo", "free", "% off", "50%", "50 %"]


def brand_rule_check(boost: dict) -> list[str]:
    violations = []
    check_fields = [boost["creative_name"], boost["ad_name"], boost["url_tags"]]
    for text in check_fields:
        low = text.lower()
        for word in FORBIDDEN_COPY_PATTERNS:
            if word in low:
                violations.append(f"'{word}' found in '{text[:40]}'")
    return violations


def find_existing_adset(campaign_id: str, criterion: str, token: str) -> dict | None:
    """Find an ACTIVE adset in the campaign matching criterion (substring match)."""
    data = meta_get(
        f"/{campaign_id}/adsets",
        token,
        {"fields": "id,name,status,effective_status,targeting,daily_budget", "limit": "100"},
    )
    for a in data.get("data", []):
        if a.get("status") != "ACTIVE":
            continue
        name_l = a.get("name", "").lower()
        if criterion.replace("_", " ") in name_l or criterion in name_l:
            return a
    # fallback: any ACTIVE adset in the campaign
    for a in data.get("data", []):
        if a.get("status") == "ACTIVE":
            return a
    return None


def create_creative(boost: dict, token: str) -> dict:
    cta = {
        "type": boost["cta_type"],
        "value": {"link": boost["cta_link"]},
    }
    return meta_post(
        f"/{AD_ACCOUNT}/adcreatives",
        token,
        {
            "name": boost["creative_name"],
            "object_story_id": boost["post_id"],
            "call_to_action": json.dumps(cta),
            "url_tags": boost["url_tags"],
        },
    )


def create_ad(boost: dict, creative_id: str, adset_id: str, token: str) -> dict:
    return meta_post(
        f"/{AD_ACCOUNT}/ads",
        token,
        {
            "name": boost["ad_name"],
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "PAUSED",
        },
    )


def verify_ad(ad_id: str, token: str) -> dict:
    return meta_get(
        f"/{ad_id}",
        token,
        {"fields": "id,name,status,effective_status,creative{id,object_story_id},adset_id,campaign_id"},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = get_token()

    print("=" * 70)
    print(f"S214 Phase 4 — Boost Viral Posts (mode: {'DRY RUN' if args.dry_run else 'LIVE'})")
    print("=" * 70)

    # ===== Brand-rule guard (RRC-1) =====
    print("\n[RRC-1] Brand rule check (no discount/promo words)...")
    total_violations = []
    for b in BOOSTS:
        v = brand_rule_check(b)
        if v:
            total_violations.extend([(b["label"], x) for x in v])
    if total_violations:
        print("[STOP] Brand rule violations:")
        for lbl, v in total_violations:
            print(f"  {lbl}: {v}")
        return 2
    print("  OK — no forbidden words.")

    # ===== Resolve adsets per boost =====
    print("\nResolving target adsets...")
    pre_state = []
    for b in BOOSTS:
        adset = find_existing_adset(b["campaign_id"], b["target_adset_criterion"], token)
        if not adset:
            print(f"  ✗ {b['label']}: no active adset in campaign {b['campaign_id']}")
            return 2
        b["resolved_adset_id"] = adset["id"]
        b["resolved_adset_name"] = adset.get("name", "")
        print(f"  ✓ {b['label']} -> adset {adset['id']} '{adset.get('name','')[:50]}'")
        pre_state.append({
            "label": b["label"],
            "post_id": b["post_id"],
            "campaign_id": b["campaign_id"],
            "resolved_adset_id": adset["id"],
            "resolved_adset_name": adset.get("name"),
            "cta_type": b["cta_type"],
            "cta_link": b["cta_link"],
        })

    save_pre_state("04_boost_viral_before", {"boosts": pre_state})

    if args.dry_run:
        print("\n[DRY RUN] No creatives or ads created.")
        return 0

    # ===== Create creative + ad for each post =====
    print("\n[LIVE] Creating 3 creatives + 3 ads (all PAUSED)...")
    results = []
    for b in BOOSTS:
        print(f"\n[{b['label']}]")
        # Creative
        print(f"  Creating creative (object_story_id={b['post_id']})...")
        creative_resp = create_creative(b, token)
        creative_id = creative_resp.get("id")
        if not creative_id:
            print(f"    ✗ Creative FAILED: {creative_resp}")
            results.append({"label": b["label"], "stage": "creative", "success": False, "response": creative_resp})
            log_form_submission({
                "phase": "P4",
                "action": "create_creative_failed",
                "target_post": b["post_id"],
                "response": creative_resp,
            })
            continue
        print(f"    ✓ creative_id={creative_id}")

        # Ad
        print(f"  Creating ad in adset {b['resolved_adset_id']}...")
        ad_resp = create_ad(b, creative_id, b["resolved_adset_id"], token)
        ad_id = ad_resp.get("id")
        if not ad_id:
            print(f"    ✗ Ad FAILED: {ad_resp}")
            results.append({"label": b["label"], "stage": "ad", "success": False, "response": ad_resp,
                            "creative_id": creative_id})
            log_form_submission({
                "phase": "P4",
                "action": "create_ad_failed",
                "target_post": b["post_id"],
                "creative_id": creative_id,
                "response": ad_resp,
            })
            continue
        print(f"    ✓ ad_id={ad_id}")

        # Verify
        verify = verify_ad(ad_id, token)
        status_ok = verify.get("status") == "PAUSED"
        osi_ok = verify.get("creative", {}).get("object_story_id") is not None
        print(f"    ✓ verify: status={verify.get('status')} object_story_id={verify.get('creative',{}).get('object_story_id')}")

        results.append({
            "label": b["label"],
            "post_id": b["post_id"],
            "creative_id": creative_id,
            "ad_id": ad_id,
            "adset_id": b["resolved_adset_id"],
            "verify_status": verify.get("status"),
            "verify_effective": verify.get("effective_status"),
            "stage": "complete",
            "success": status_ok and osi_ok,
        })
        log_form_submission({
            "phase": "P4-T3-T7",
            "action": "create_boost_ad",
            "target_post": b["post_id"],
            "creative_id": creative_id,
            "ad_id": ad_id,
            "adset_id": b["resolved_adset_id"],
            "cta_type": b["cta_type"],
            "cta_link": b["cta_link"],
            "starts_paused": status_ok,
            "success": status_ok and osi_ok,
        })

    save_post_state("04_boost_viral_after", {"results": results})

    passed = sum(1 for r in results if r["success"])
    print(f"\nPhase 4 summary: {passed}/{len(BOOSTS)} new boost ads created (all PAUSED)")
    print("\n>>> User action: review each ad in Ads Manager, narrow targeting if desired, UNPAUSE.")
    return 0 if passed == len(BOOSTS) else 1


if __name__ == "__main__":
    sys.exit(main())
