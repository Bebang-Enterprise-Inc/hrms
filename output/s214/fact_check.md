# S214 Fact-Check Report
**Plan:** `docs/plans/2026-04-21-sprint-214-meta-ads-rules-fix-refresh-archive.md`
**Audited:** 2026-04-21
**Auditor:** Clean-context adversarial fact-checker (zero prior context)

---

## CLAIM-1: Rule `888035557619357` is named "BEB: EMERGENCY - Pause ALL if spend > 100K" with filter `time_preset=TODAY, spent > 100000, entity=CAMPAIGN`
- **Verdict:** SUPPORTED
- **Evidence:** From `adrules.json`, id `888035557619357`:
  - name: `"BEB: EMERGENCY - Pause ALL if spend > 100K"` ✓
  - filters: `entity_type=CAMPAIGN` ✓, `time_preset=TODAY` ✓, `spent > 100000` ✓
  - execution: `PAUSE` ✓
- **Discrepancy:** None. All three filter fields and name match exactly.

---

## CLAIM-2: Rule `1539999288125943` is named "BEB: Sales OFF at 6PM" with `execution_type=PAUSE`
- **Verdict:** SUPPORTED
- **Evidence:** From `adrules.json`, id `1539999288125943`:
  - name: `"BEB: Sales OFF at 6PM"` ✓
  - execution_spec: `{"execution_type": "PAUSE"}` ✓
- **Discrepancy:** None.

---

## CLAIM-3: 8 rules were created on 2026-04-05 between 11:49:08 and 11:52:23 PHT (+0800)
- **Verdict:** SUPPORTED
- **Evidence:** All 8 rules in `adrules.json` have `created_time` on `2026-04-05` at `+0800`:
  - Earliest: `2026-04-05T11:49:08+0800` (Sales OFF at 6PM)
  - Latest: `2026-04-05T11:52:23+0800` (Frequency Cap)
  - All 8 timestamps fall within the 11:49:08–11:52:23 window ✓
- **Discrepancy:** None.

---

## CLAIM-4: 193 ads have HARD_ERROR delivery issues
- **Verdict:** SUPPORTED
- **Evidence:** `sandbox_ads_all.json` contains 194 total entries; 193 have at least one `issues_info` entry with `error_type == "HARD_ERROR"`. The plan says "194 returned, 193 HARD_ERROR" which matches exactly.
- **Discrepancy:** None.

---

## CLAIM-5: 33 ads have "Ads creative post was created by an app that is in development mode" error
- **Verdict:** SUPPORTED
- **Evidence:** Exact string match of error_summary `"Ads creative post was created by an app that is in development mode"` in `sandbox_ads_all.json` yields exactly 33 ads.
- **Discrepancy:** None.

---

## CLAIM-6: 3,904 total ads in account + 1,230 unique story_ids (used for historical dedup)
- **Verdict:** SUPPORTED
- **Evidence:** `all_ads_with_story.json`:
  - `total_ads` field: `3904` ✓
  - `story_ids` array length: `1230` ✓
- **Discrepancy:** None.

---

## CLAIM-7: Three specific viral post_ids are NOT in historical story_ids (safe to boost) AND appear in posts_30days.json with `already_boosted: false`
- **Verdict:** SUPPORTED
- **Evidence (dedup check):** None of the three post_ids appear in `all_ads_with_story.json` story_ids:
  - `102628625216977_1266416878948597`: NOT_FOUND ✓
  - `102628625216977_1260249656231986`: NOT_FOUND ✓
  - `102628625216977_1267949595461992`: NOT_FOUND ✓
- **Evidence (posts_30days.json):** All three posts found with `already_boosted: False`:
  - `_1266416878948597`: found, `already_boosted=False`, `score=3513`
  - `_1260249656231986`: found, `already_boosted=False`, `score=3071`
  - `_1267949595461992`: found, `already_boosted=False`, `score=2655`
- **Note:** The plan's score ordering (2,655 / 3,071 / 3,513 for Apr 16 / Apr 8 / Apr 18) maps to post IDs in reverse order from above. Scores are correct per-post but the listing order in the plan is Apr 16=2655, Apr 8=3071, Apr 18=3513 — confirmed correct by the data.
- **Discrepancy:** None.

---

## CLAIM-8: 7-day spend was PHP 74,863 with 334 purchases
- **Verdict:** PARTIAL
- **Evidence:** From `insights_7d.json`:
  - Total spend across 36 rows: **PHP 74,863** ✓ (exact match)
  - Total purchases (summing `actions[action_type==purchase].value`): **335** — plan claims 334
- **Discrepancy:** Purchase count is 335 in the data, not 334 as stated in the plan. Off by 1. Minor discrepancy but measurable.

---

## CLAIM-9: April 20 hourly spend pattern — 10AM hour PHP 9,106; 11AM hour PHP 865; 12PM onwards PHP 0
- **Verdict:** UNVERIFIABLE
- **Evidence:** No April 20 specific hourly data file exists on disk. The `hourly_breakdown.json` file covers a date range of `2026-01-09` to `2026-02-07` — entirely different period. No other file in `Marketing/digital-marketing/data/` or `_tmp/` contains April 20 hourly breakdown.
- **Discrepancy:** N/A — source was a live API query that was not persisted.

---

## CLAIM-10: PHP 27,800 sum of active adset daily budgets across 4 campaigns
- **Verdict:** SUPPORTED
- **Evidence:** Using the 4 campaign-specific adset files (`as_120225029875060030.json`, `as_120225480340900030.json`, `as_120225775497020030.json`, `as_120231023755930030.json`):
  - Campaign `120225029875060030`: 1 ACTIVE adset = PHP 5,000
  - Campaign `120225480340900030`: 4 ACTIVE adsets = PHP 15,500
  - Campaign `120225775497020030`: 3 ACTIVE adsets = PHP 5,500
  - Campaign `120231023755930030`: 2 ACTIVE adsets = PHP 1,800
  - **Total: PHP 27,800** ✓
- **Note:** The plan cites only `as_lal.json`, `as_bof.json`, `as_int.json` as the 3 evidence files, but these appear to be summary views that do NOT cover campaign `120231023755930030`. The correct evidence is the 4 campaign-named files which sum to PHP 27,800. The named-file trio (`as_lal` + `as_bof` + `as_int`) sums to PHP 26,000. The correct total is only reached via the 4 campaign files. The plan's cited evidence source is slightly inaccurate but the final number is correct.
- **Discrepancy:** Evidence file citation in plan says 3 files (`as_lal`, `as_bof`, `as_int`) but correct total requires 4 campaign-specific files. The PHP 27,800 figure itself is verified correct.

---

## CLAIM-11: Campaign IDs exist and have correct objectives
- **Verdict:** UNVERIFIABLE
- **Evidence:** No saved file on disk contains campaign-level details (name, objective) for these three campaign IDs (`120242888352350030`, `120243460275370030`, `120242888355100030`). The `_tmp/c_*.json` files cover only the 4 active conversion campaigns, not awareness/engagement/traffic campaigns. These paused campaigns were not captured in any data snapshot.
- **Discrepancy:** N/A — no on-disk evidence either way.

---

## CLAIM-12: Sprint registry says "next is S215" and S214 row with correct branch `s214-meta-ads-rules-fix-refresh-archive` exists
- **Verdict:** SUPPORTED
- **Evidence:** From `SPRINT_REGISTRY.md`:
  - Line 313: S214 row exists with branch `s214-meta-ads-rules-fix-refresh-archive` and status `PLANNED` ✓
  - Line 316: "Next canonical sprint ID to assign: `S215` (S212 COMPLETED-PARTIAL; S213 FG004 batch backfill PLANNED; S214 Meta Ads rules+refresh+archive PLANNED)" ✓
- **Discrepancy:** None.

---

## CLAIM-13: 16 specific loser ad IDs in the plan's Phase 2 table match ads in insights_7d.json
- **Verdict:** PARTIAL
- **Evidence:** Of the 8 explicitly listed loser ad IDs in the plan (rows 1–8), all 8 are present in `insights_7d.json`:
  - `120236490022230030` ✓ (spend=6,474)
  - `120236894994690030` ✓ (spend=5,858)
  - `120238080535160030` ✓ (spend=5,255)
  - `120236894995250030` ✓ (spend=5,048)
  - `120226689093050030` ✓ (spend=4,707)
  - `120229072327660030` ✓ (spend=4,070)
  - `120227612549140030` ✓ (spend=3,345)
  - `120226689305170030` ✓ (spend=3,240)
- The remaining 8 loser IDs (rows 9–16) are marked `*(to be looked up in P2-T1)*` in the plan — they have no hardcoded IDs in the plan, so cannot be verified against `insights_7d.json`. The plan acknowledges this explicitly.
- **Discrepancy:** None for the 8 hardcoded IDs. The other 8 are intentionally deferred to agent execution.

---

## CLAIM-14: Winner ad `120233175036340030` in adset `120226411235010030` (INT Coffee/Ice Cream) — ROAS 19.80x
- **Verdict:** SUPPORTED
- **Evidence:** From `insights_7d.json`:
  - `ad_id`: `120233175036340030` ✓
  - `adset_id`: `120226411235010030` ✓ (exact match)
  - `purchase_roas[action_type=omni_purchase].value`: `19.798348` → rounds to **19.80x** ✓
  - `spend`: PHP 4,885.80
- **Discrepancy:** None.

---

## CLAIM-15: Phase Budget: 4+5+6+5+8+4+5 = 37 units
- **Verdict:** SUPPORTED
- **Evidence:** Arithmetic: 4+5 = 9; 9+6 = 15; 15+5 = 20; 20+8 = 28; 28+4 = 32; 32+5 = **37** ✓
- **Discrepancy:** None. Math is correct.

---

## CLAIM-16: 652 employees in Employee Master (claim in CLAUDE.md)
- **Verdict:** CONTRADICTED
- **Evidence:** `data/_FINAL/EMPLOYEE_MASTER.csv` has **702 data rows** (excluding header). The plan itself does not make this claim — it is a CLAUDE.md/MEMORY.md claim.
  - CLAUDE.md says both "652 employees" and "696 employees" in different places — both are wrong.
  - MEMORY.md says "696 rows, max Bio ID 9001881" — also wrong (702 rows found).
- **Discrepancy:** CLAUDE.md is internally inconsistent (652 vs 696) and the actual file has 702 rows. This is a documentation drift issue in CLAUDE.md/MEMORY.md, not in the S214 plan itself.

---

## CLAIM-17: Today is 2026-04-21 (plan dated 2026-04-21)
- **Verdict:** SUPPORTED
- **Evidence:** `python -c "from datetime import date; print(date.today().isoformat())"` returns `2026-04-21` ✓
- **Discrepancy:** None.

---

## CLAIM-18: The organic-fetch dedup check in the SKILL only covered ACTIVE/PAUSED/CAMPAIGN_PAUSED statuses (NOT including ARCHIVED) — plan claims this was a gap
- **Verdict:** SUPPORTED
- **Evidence:** `Marketing/digital-marketing/scripts/meta_ads_fetch_organic.py`, line 61:
  ```python
  f'filtering=[{{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED","CAMPAIGN_PAUSED"]}}]&'
  ```
  The filter list is exactly `["ACTIVE", "PAUSED", "CAMPAIGN_PAUSED"]` — `"ARCHIVED"` is absent ✓
- **Discrepancy:** None. The gap is real and confirmed.

---

## Summary

```
Total claims: 18
SUPPORTED: 12
CONTRADICTED: 1
PARTIAL: 3
UNVERIFIABLE: 2
NOT_FOUND: 0
```

### CONTRADICTED Claims (critical issues)

**CLAIM-16 (CLAUDE.md employee count):** `data/_FINAL/EMPLOYEE_MASTER.csv` has **702 rows**, not 652 or 696 as stated in CLAUDE.md/MEMORY.md. This is documentation drift — the S214 plan itself does not reference this number and is unaffected. Action needed: update CLAUDE.md and MEMORY.md to reflect 702.

### PARTIAL Claims (minor discrepancies)

**CLAIM-8 (purchases count):** Data shows 335 purchases in insights_7d.json; plan claims 334. Off by 1 — negligible for execution purposes.

**CLAIM-10 (budget evidence files):** PHP 27,800 total is correct but the plan cites `as_lal`, `as_bof`, `as_int` as the source when the correct total requires all 4 campaign-specific files (`as_120225*.json`). The evidence citation is slightly misleading but the number is accurate.

**CLAIM-13 (16 loser IDs):** Only 8 of 16 loser IDs are hardcoded in the plan; the other 8 are `*(to be looked up)*`. The 8 hardcoded ones all verify correctly. Not a discrepancy — the plan is explicit about this.

### UNVERIFIABLE Claims (no on-disk evidence)

**CLAIM-9 (April 20 hourly spend):** No April 20 hourly data saved to disk. The `hourly_breakdown.json` covers Jan-Feb 2026. The specific PHP 9,106 / PHP 865 / PHP 0 pattern cannot be verified.

**CLAIM-11 (campaign objectives):** The 3 paused campaigns (awareness/engagement/traffic) have no on-disk snapshot. Their names and objectives cannot be verified from saved files.
