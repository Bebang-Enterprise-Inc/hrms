# Code Verification — S214 Meta Ads Plan

**Audited:** 2026-04-21  
**Plan file:** `docs/plans/2026-04-21-sprint-214-meta-ads-rules-fix-refresh-archive.md`

---

## CV-1: Existing script `manage_meta_ad_rules.py` exists and has rule-CRUD patterns

- **Status:** CONFIRMED (partial)
- **Evidence:** `F:\Dropbox\Projects\BEI-ERP\Marketing\digital-marketing\scripts\manage_meta_ad_rules.py` exists (445 lines). Has `delete_old_rules()` (DELETE method), `create_new_rules()` (POST to `adrules_library`), `verify_rules()` (GET), `--dry-run` flag, and `meta_api_post()` helper. Ad account `act_843498792928069` and `API_VERSION = "v25.0"` match plan.
- **Issue:** The script does NOT have a `disable_rule()` or `update_rule_status()` helper. It can create and delete rules, but has no pattern for setting `status=DISABLED` on an existing rule. The plan correctly identifies this as something to ADD (Duplication Audit says [EXTEND]). This is expected, not a gap.

---

## CV-2: Existing script `boost_replacements.py` uses `object_story_id` pattern

- **Status:** STALE
- **Evidence:** `F:\Dropbox\Projects\BEI-ERP\Marketing\digital-marketing\scripts\boost_replacements.py` exists (101 lines). It stores post IDs in a `REPLACEMENTS` list with plain `'id'` keys (e.g., `'102628625216977_1207511461505783'`), but the actual ad creation code is a stub: it prints `"[ACTION REQUIRED] Launch these 3 posts in Ads Manager manually or via script."` — **no API call to create ad creatives is implemented**. No `object_story_id` field is used anywhere in the script.
- **Issue:** The plan claims this script "demonstrates the `object_story_id` boost pattern." It does not. The script identifies posts to boost but does not implement the boost API call. The actual `object_story_id` pattern is in `references/api-reference.md`, not in this script. The plan's Duplication Audit says [EXTEND] — the agent should know it is building the boost implementation essentially from scratch, using the skill reference, not the existing script as a template.

---

## CV-3: Existing script `meta_ads_audit.py` can be used for pre/post comparison

- **Status:** CONFIRMED (with caveat)
- **Evidence:** `F:\Dropbox\Projects\BEI-ERP\Marketing\digital-marketing\scripts\meta_ads_audit.py` exists (287 lines). Fetches active campaigns + ad-level 7-day insights, flags underperformers, saves to `Marketing/digital-marketing/data/weekly_audit.json`. Usable for pre/post spend comparison.
- **Issue:** Script uses `API_VERSION = 'v23.0'` while the plan uses v25.0 throughout. Meta maintains backward compatibility so this works, but there is a version divergence. Minor — not a blocker.

---

## CV-4: SKILL's `references/api-reference.md` documents Pattern 2 (boost via object_story_id)

- **Status:** CONFIRMED
- **Evidence:** `F:\Dropbox\Projects\BEI-ERP\.claude\skills\meta-ads\references\api-reference.md` lines 79–89. Section titled "Pattern: Boost Existing Organic Post with CTA Override" shows exact curl using `object_story_id=102628625216977_POST_ID` + `call_to_action`. Uses `act_843498792928069/adcreatives` endpoint. CTA types listed include `ORDER_NOW` and `LEARN_MORE` as used in the plan.

---

## CV-5: Meta API version v25.0 is current per skill

- **Status:** CONFIRMED
- **Evidence:** `F:\Dropbox\Projects\BEI-ERP\.claude\skills\meta-ads\SKILL.md` line 33: `API Version | **v25.0** (migrated Q1 2026 from v23.0)`. Plan uses v25.0 throughout. Consistent.

---

## CV-6: Meta app ID 9832393326853416 "BigQuery - Looker Studio" is documented as in dev mode

- **Status:** CONFIRMED
- **Evidence:** `SKILL.md` line 37: `Token App | "BigQuery - Looker Studio" (ID: 9832393326853416) — **dev mode**`. Also confirmed in `api-reference.md` lines 52–53 which explains why `object_story_spec + link_data` fails with error 1885183.

---

## CV-7: Schedule time format for Meta rules

- **Status:** STALE
- **Evidence:** The plan's Phase 1 implementation note states: `schedule = [{"start_minute": 840, "end_minute": 899}]` as the format for a Meta rule `schedule_spec`. However, the existing `manage_meta_ad_rules.py` `daily_schedule()` function (lines 103–106) produces a DIFFERENT format: `{"schedule_type": "CUSTOM", "schedule": [{"start_minute": N, "end_minute": N, "days": [d]} for d in range(7)]}` — a wrapper object with `schedule_type` key and a `days` array per entry. The plan's bare array `[{"start_minute": 840, "end_minute": 899}]` omits both the outer `schedule_type` wrapper and the per-day `days` field required by the actual API. The api-reference.md does not document the rule schedule format. This is a concrete implementation error in the plan's example code.

---

## CV-8: Rule update via POST `{rule-id}?status=DISABLED` is correct syntax

- **Status:** UNVERIFIABLE
- **Evidence:** The existing `manage_meta_ad_rules.py` has no rule-status-update call to examine. The Meta Graph API allows `POST /{rule-id}` with `status=DISABLED` as a standard pattern for ad objects — this is consistent with how the script pauses ads (`POST /{ad_id}` with `status=PAUSED` as seen in api-reference.md lines 39). Pattern is plausible but not confirmed against a live call in existing code.

---

## CV-9: Doppler key `META_ACCESS_TOKEN` is the right key for ad mutations

- **Status:** CONFIRMED
- **Evidence:** `SKILL.md` Doppler Secrets section: `doppler secrets get META_ACCESS_TOKEN --project bei-erp --config dev --plain`. Also confirmed in `manage_meta_ad_rules.py` line 57 (`get_secret("META_ACCESS_TOKEN")`) and `boost_replacements.py` line 41 (`get_doppler_secret('META_ACCESS_TOKEN')`). All scripts use this key for ad API mutations.

---

## CV-10: Sprint registry has S214 row and next reservation shows S215

- **Status:** CONFIRMED
- **Evidence:** `docs/plans/SPRINT_REGISTRY.md` line 313 contains S214 row with `s214-meta-ads-rules-fix-refresh-archive` branch and status `PLANNED 2026-04-21`. Line 316: "Next canonical sprint ID to assign: `S215`". Both claims confirmed.

---

## CV-11: Scripts listed in Duplication Audit actually exist

- **Status:** CONFIRMED (all 5 exist)
- **Evidence:** All confirmed present in `F:\Dropbox\Projects\BEI-ERP\Marketing\digital-marketing\scripts\`:
  - `meta_ads_audit.py` — EXISTS
  - `meta_ads_fetch_organic.py` — EXISTS
  - `meta_ads_session_log.py` — EXISTS
  - `manage_meta_ad_rules.py` — EXISTS
  - `boost_replacements.py` — EXISTS

---

## CV-12: Plan file paths are valid (evidence files exist)

- **Status:** CONFIRMED (6 of 7)
- **Evidence:**
  - `Marketing/digital-marketing/reports/WEEKLY_REPORT_2026-04-21.md` — EXISTS
  - `Marketing/digital-marketing/data/_tmp/adrules.json` — EXISTS (8 rules confirmed)
  - `Marketing/digital-marketing/data/_tmp/activity_30d.json` — EXISTS (113 events confirmed)
  - `Marketing/digital-marketing/data/insights_7d.json` — EXISTS (36 rows; 35 with spend > 0)
  - `Marketing/digital-marketing/data/posts_30days.json` — EXISTS (52 posts confirmed)
  - `Marketing/digital-marketing/data/_tmp/all_ads_with_story.json` — EXISTS (3,904 total_ads, 1,230 unique story_ids confirmed)
  - `Marketing/digital-marketing/data/_tmp/sandbox_ads_all.json` — EXISTS (194 total, 193 HARD_ERROR confirmed)
- **Issue:** `insights_7d.json` has 36 rows (plan says 35 spending ads — correct when filtered to spend > 0).

---

## CV-13: The 3 campaign IDs exist in prior audit data

- **Status:** PARTIAL / NEW GAP
- **Evidence:**
  - `120243460275370030` (BEB - Peak Season Community [Apr 2026]) — CONFIRMED in `SESSION_2026-04-04.md` line 96-97. Created Apr 4.
  - `120242888352350030` (BEB - Summer Buzz Awareness [Mar 2026]) — NOT FOUND in any local data file. Campaign name "Summer Buzz" appears in session but no ID is recorded for it.
  - `120242888355100030` (BEB - Iskrambol Foodpanda Traffic [Mar 2026]) — NOT FOUND in any local data file. Name appears in session budget tables but no ID recorded.
- **Issue:** 2 of 3 campaign IDs have no local data backing. They are absent from insights_7d (paused campaigns not in active insight results), not in _tmp files, not in any JSON. The plan claims "every object ID in this plan is verified concrete as of 2026-04-21 09:45 AM PHT" (Ground-Truth Lock) but 2 campaign IDs appear to have been retrieved from a live API query that was not persisted to any local file. An executing agent should re-query Meta API to confirm these IDs before proceeding with P3-T3 — they cannot be verified from local evidence alone.

---

## CV-14: Sessions dir exists where plan says to write SESSION_2026-04-21.md

- **Status:** CONFIRMED
- **Evidence:** `F:\Dropbox\Projects\BEI-ERP\Marketing\digital-marketing\sessions\` exists (contains `SESSION_2026-04-04.md`). The directory is valid; the new session file does not yet exist (expected — it is a deliverable of the sprint).

---

## CV-15: Cold-start test — unresolved references

- **Status:** NEW GAP
- **Evidence:** Several values in the plan are marked as "(to be looked up in P2-T1)" or "(to resolve)":
  - 9 of 16 loser ad IDs (rows 9–16 in Phase 2 table) have no IDs in the plan
  - 4 of 5 winner ad IDs marked "(to resolve)"
  - 2 of 4 winner adset IDs marked "(resolve)"
  - The plan explains the resolution mechanism (query `insights_7d.json` via ad_name + campaign_name match and hardcode into script at P2-T1). This is clear procedurally.
  - **However:** `insights_7d.json` has 36 rows, not 35 as stated (minor). More critically, the named ads "Ad #1 Carousel Products duplicate in TOF-LAL", "Ad #14 Friday na", "Ad #121 Not your ordinary", etc. require name matching against the JSON — an agent must read the actual data file and confirm the IDs at execution time. This is architecturally sound but means an agent cannot fully pre-populate the Python constants from the plan alone.
  - **Separate issue:** RRC-8 (Windows headless / `CREATE_NO_WINDOW`) is listed as a requirement for every subprocess call. `boost_replacements.py` does NOT use `creationflags=0x08000000`, only `manage_meta_ad_rules.py` does. New scripts must add this flag.

---

## CV-16: Ground-Truth Lock evidence files exist

- **Status:** CONFIRMED (all 7)
- **Evidence:** All 7 files verified in CV-12. Counts cross-checked:
  - adrules.json: 8 rules ✓
  - activity_30d.json: 113 events ✓
  - insights_7d.json: 35 spending ads ✓ (36 total, 35 with spend)
  - posts_30days.json: 52 posts total ✓; 31 in last 14d ✓; 3 viral unboosted ✓
  - all_ads_with_story.json: 3,904 total_ads, 1,230 unique story_ids ✓
  - sandbox_ads_all.json: 194 fetched, 193 HARD_ERROR ✓
  - WEEKLY_REPORT_2026-04-21.md: exists ✓
  - 3 boost post IDs verified present with correct scores (3,513 / 3,071 / 2,655) and `already_boosted: False` ✓

---

## Summary

```
CONFIRMED: 11 / 16
STALE (false positives): 2
NEW GAPS (plan problems discovered): 3
UNVERIFIABLE: 1
```

### Stale Claims (plan overstates what exists)
1. **CV-2:** `boost_replacements.py` does NOT demonstrate `object_story_id` boost API pattern — the boost creation code is a stub with `[ACTION REQUIRED]`. The agent must build the boost implementation from `api-reference.md`, not from this script.
2. **CV-7:** Schedule format example in Phase 1 (`[{"start_minute": 840, "end_minute": 899}]`) is incomplete — actual API format wraps it in `{"schedule_type": "CUSTOM", "schedule": [...]}` with per-day `days` arrays, per the existing script.

### New Gaps (plan problems that could cause execution failure)
1. **CV-7 / P1-T5:** The schedule_spec format example in the plan is wrong. The executing agent must use the format from `manage_meta_ad_rules.py`'s `daily_schedule()` helper, not the bare array shown in the plan.
2. **CV-13 / CV-15:** Two of three campaign IDs for reactivation (Summer Buzz `120242888352350030`, Iskrambol Foodpanda `120242888355100030`) have no backing in any local data file. The plan asserts they are "verified concrete" but they cannot be independently confirmed from local evidence. The agent must re-query Meta API at P3-T1 to verify these IDs before executing status changes.
3. **CV-15 / RRC-8:** `boost_replacements.py` (the template for Phase 4) does NOT use `CREATE_NO_WINDOW` subprocess flag. New `s214_boost_viral_posts.py` must add it explicitly or RRC-8 will be silently violated.
