# S214 Run Summary — Meta Ads Rules Fix + Refresh + Archive

**Date:** 2026-04-21
**Sprint:** S214
**Branch:** `s214-meta-ads-rules-fix-refresh-archive`
**Worktree:** `F:/Dropbox/Projects/BEI-ERP-s214-meta-ads-rules-fix-refresh-archive`
**Overall status:** **PASS** (7/7 phases green; combined archive coverage 99%)

## What changed on the Meta ad account

### 1. Rules (Phase 1)
- `888035557619357` **BEB: EMERGENCY - Pause ALL if spend > 100K**: `ENABLED → DISABLED`
  - Was misfiring daily ~11 AM PHT on PHP ~10K spend (100× below threshold)
  - Was cutting delivery to ~2 hours/day for 14+ days
- `1539999288125943` **BEB: Sales OFF at 6PM**: schedule `18:00 → 22:00` PHT (minute 1080 → 1320)
  - Keeps Sales ON 9AM rule; fires OFF 4 hours later to capture 6-10 PM peak sales

### 2. Conversion adset rebalancing (Phase 2)
- **Paused 11 losers** (CPA > PHP 400 AND ROAS < 2x on 7d): stopped ~PHP 56K/week waste
- **Excluded 2 reversals** (plan HARD BLOCKER): Matcha-fying Gravity + Basta happy both flipped to 24h ROAS > 4.5x; kept alive
- **Scaled 3 winner adsets** (+PHP 14,500/day on ROAS 24-80x ads):
  - `120228362624100030` BEH Engaged Shoppers (Don't leave valuables, 80x): PHP 1,500 → 7,500
  - `120226411235010030` INT Coffee/Ice Cream (Swipe + Carousel Products, 39x): PHP 2,500 → 5,000
  - `120227382261260030` INT Online food ordering (Ang sakit naman Beb!, 24x): PHP 1,500 → 7,500

### 3. Funnel restoration (Phase 3)
Reactivated 3 campaigns (PAUSED → ACTIVE), restoring all funnel stages:
- Summer Buzz Awareness (`120242888352350030`) — 3 active adsets
- Peak Season Community Engagement (`120243460275370030`) — 1 active adset (PHP 5,200/day)
- Iskrambol Foodpanda Traffic (`120242888355100030`) — 1 active adset

### 4. Viral organic boosts (Phase 4) — USER REVIEW NEEDED
3 new ads created via `object_story_id` pattern, **all starting PAUSED**:

| New ad | Post | Campaign | CTA |
|---|---|---|---|
| `120244564280350030` | Apr 16 Tag-a-Friend Sikat na Artista (974 comments) | Peak Season Community | LEARN_MORE → fb.com/bebanghalohalo |
| `120244564281190030` | Apr 8 Nasa Montalban store opening (395 shares) | Summer Buzz Awareness | ORDER_NOW → Foodpanda chain page |
| `120244564282510030` | Apr 18 Grabeng pressure mood meme (412 shares) | Peak Season Community | ORDER_NOW → Foodpanda chain page |

**→ Your next action:** review each in Ads Manager. For Post 2 (Montalban), optionally narrow adset targeting to Montalban geo-radius before unpausing.

### 5. Library cleanup (Phase 5)
- **~192 of 193 error-state ads archived** (99%+ coverage)
- Split across 2 API attempts (first hit rate limit at ~31 archived, retry completed 161 more)
- 1 residual failure within 5% plan tolerance
- Ads Manager now much cleaner — no more 193 red "Delivery error" banners

## Expected spend recovery

| Window | Expected daily | Notes |
|---|---:|---|
| Today (Apr 21) after fix | PHP 20-30K | EMERGENCY rule gone; 9 AM - 10 PM delivery window |
| Day +2 | PHP 30-38K | Awareness + engagement + traffic campaigns delivering |
| Day +5 | PHP 38-45K | If Sam unpauses 3 new viral boosts |
| Day +7+ | PHP 45-55K | Winners scaling into their new budgets |

Prior baseline: PHP 10K/day. Pre-bug baseline: PHP 50-62K/day.

## Evidence (all under `output/s214/`)

- `RUN_STATUS.json` — overall PASS with per-check reconciliation
- `pre_state/` — 8 files (rules, losers, winners, campaigns, boosts, archive pre-state)
- `post_state/` — 6 files (each phase's post-mutation state)
- `form_submissions.json` — every mutation logged with before/after
- `api_mutations.json` — raw Meta API call/response log
- `archive_summary.json` — Phase 5 archive stats

## Rollback instructions (if needed)

1. **Undo rule fix:** `POST /888035557619357 status=ENABLED` + `POST /1539999288125943 schedule_spec={<1080 version>}`
2. **Unpause losers:** `POST /{ad_id} status=ACTIVE` for each in `post_state/02_losers_after.json`
3. **Revert winner budgets:** `POST /{adset_id} daily_budget=<pre_state value>`
4. **Re-pause campaigns:** `POST /{campaign_id} status=PAUSED` for 3 in `post_state/03_campaigns_after.json`
5. **Delete new boost ads:** `DELETE /{ad_id}` for 3 in `post_state/04_boost_viral_after.json`
6. **Unarchive (edge case):** `POST /{ad_id} status=PAUSED` for each archived ad — but these are all broken anyway

## Next steps

1. **You (Sam):** review 3 new PAUSED boost ads, unpause when ready
2. **Monitor:** 48 hours — does spend trend toward PHP 30-40K/day?
3. **Follow-up:** if EMERGENCY rule should return, rebuild with correct logic — use `account_spent_today > 100000` (test with actual 100K spend to verify)
4. **Session log:** `Marketing/digital-marketing/sessions/SESSION_2026-04-21.md` (to be written by closeout + ingested to BEI Brain)
5. **PR:** closeout + merge
