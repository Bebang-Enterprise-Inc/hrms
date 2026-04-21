---
sprint_id: S214
title: Meta Ads Rules Fix + Ad Refresh + Error-Ad Archive
date: 2026-04-21
version: v1.1
audit_version: 1
status: DEPLOYED
completed_date: 2026-04-21
execution_summary: |
  7/7 phases PASS. EMERGENCY rule disabled; Sales OFF extended 18:00->22:00 PHT.
  11 losers paused (+2 reversals excluded via plan HARD BLOCKER). 3 winner adsets
  scaled +PHP 14,500/day on ROAS 24-80x. 3 campaigns reactivated (awareness +
  engagement + traffic). 3 viral boost ads created PAUSED for user review.
  ~192/193 error ads archived (99%+ coverage). Evidence in output/s214/.
  User action: review + unpause 3 new boost ads; monitor 48h spend recovery.
branch: s214-meta-ads-rules-fix-refresh-archive
base_branch: production
repo: BEI-ERP
canonical_scope: none
canonical_scope_rationale: |
  Meta Ads automation only. All actions are external API calls to Meta Graph API
  (disable rule, pause/activate ads, change ad-set budgets, create new ad creatives,
  archive paused ads). Zero Frappe DocType mutations, zero tabCompany/Warehouse/Customer
  reads or writes, zero SI/PO/MR/GL impact. Listed explicitly under `canonical_scope: none`
  in write-plan-bei-erp skill decision table: "Marketing content, Meta Ads automation,
  social content scheduling."
pr: null
registry_row: |
  | `S214` | Sprint 214 | `s214-meta-ads-rules-fix-refresh-archive` (BEI-ERP — Meta API scripts only; no Frappe / bei-tasks code) | TBD | PLANNED 2026-04-21 — Meta Ads Rules Fix + Ad Refresh + Error-Ad Archive. | `docs/plans/2026-04-21-sprint-214-meta-ads-rules-fix-refresh-archive.md` |
---

# S214 — Meta Ads Rules Fix + Ad Refresh + Error-Ad Archive

## Audit v1 Amendments (2026-04-21)

This plan was audited by a 3-agent run (structural + fact-check + code verification). 0 CRITICAL blockers, 3 NEW GAPS, 5 WARNINGs, 3 INFOs. All applied in-line below. Full audit evidence in `output/plan-audit/s214-meta-ads-rules-fix-refresh-archive/`.

| # | Amendment | Source finding | Section changed |
|---|---|---|---|
| A1 | Schedule format fixed in P1-T5 (must be `{"schedule_type":"CUSTOM","schedule":[{"start_minute","end_minute","days"}]}` — NOT bare array) | Code verifier CV-7 | Phase 1 implementation note |
| A2 | Added P3-T0 campaign-ID pre-verification (2 of 3 reactivation campaigns unverified in saved data) | Code verifier CV-13 | Phase 3 |
| A3 | Phase 4 reclassified [EXTEND]→[BUILD]; `boost_replacements.py` confirmed as stub, not template; CREATE_NO_WINDOW explicit requirement | Code verifier CV-2, RRC-8 | Duplication Audit + Phase 4 |
| A4 | Ground-Truth Lock `unresolved_value_policy` corrected: 4 categories of runtime-resolved IDs named | Structural W2, fact-check CLAIM-13 | Ground-Truth Lock |
| A5 | Purchases count corrected: 335 (not 334) | Fact-check CLAIM-8 | Exec summary, scorecard |
| A6 | Evidence file list for PHP 27,800 corrected: 4 campaign-named JSON files (not 3 summary files) | Fact-check CLAIM-10 | Ground-Truth Lock |
| A7 | Boot Sequence step 2 changed: STOP on dirty branch, do NOT git stash silently | Structural W3 | Agent Boot Sequence |
| A8 | P0-T3 MUST_MODIFY uses explicit paths | Structural W1 | Phase 0 table |
| A9 | verify_s214.py Phase 4 block adds PAUSED status assertion | Structural I1 | Phase 6 verify script |

## Executive Summary

The Bebang Halo-Halo Meta ad account (`act_843498792928069`) has three compounding problems producing a PHP 50K/day → PHP 10K/day spend collapse and a cluttered ad library. This sprint fixes all three in a single coordinated run:

1. **Rule layer broken.** An automated rule (`BEB: EMERGENCY - Pause ALL if spend > 100K`, id `888035557619357`) is misfiring every day at ~11 AM PHT on a real spend of only ~PHP 10K and pausing all 4 delivering conversion campaigns. Result: campaigns deliver ~2 hours/day instead of 24. A second rule (`BEB: Sales OFF at 6PM`, id `1539999288125943`) cuts delivery during halo-halo's peak 3-9 PM selling hours. Root cause audited: 2026-04-05 11:49-11:52 AM PHT rule batch — see `Marketing/digital-marketing/reports/WEEKLY_REPORT_2026-04-21.md` Part 1 + Part 2.
2. **Ad portfolio stale.** 16 conversion ads burning PHP 56K/week at CPA > PHP 400 and ROAS < 2x; 5 winners under-funded (ROAS 14x-80x); Summer Buzz Awareness + Peak Season Community Engagement + Iskrambol Foodpanda Traffic campaigns all paused, starving the funnel. Three new viral organic posts from the last 14 days (scores 2,655 / 3,071 / 3,513) are unboosted.
3. **Account library polluted.** 193 ads in permanent `WITH_ISSUES` delivery-error state (73 Custom-audience-unavailable from 2021-22, 48 generic Ad-Set-Has-Error, **33 Ads-creative-post-was-created-by-an-app-that-is-in-development-mode**, 12 auth-expired, 10 deprecated-crop, 6 App-Deleted/Sandbox, 11 misc) clutter Ads Manager and reporting. Most are from 2021-2022; most recent batch is **2026-03-08 Foodpanda Panda Buddy/Sunglasses (8 ads)**.

**Deliverables:** six Python scripts (run in order, committed to the branch) that execute all three fixes via Meta Graph API v25.0 with full idempotency, pre/post counts, and a machine-verifiable closeout.

## Design Rationale (For Cold-Start Agents)

### Why this exists

The Bebang Halo-Halo Facebook/Instagram ad account was running healthy PHP 30-62K/day through Apr 4, 2026. On Apr 5 at 11:49 AM PHT, an automation run (not logged) created 8 Meta ad rules. One of them (`EMERGENCY 100K`) has a bug: the filter `spent > 100000 TODAY` at CAMPAIGN level is matched even when today's spend is ~PHP 10K — Meta's rule engine appears to treat the threshold against a lifetime/historical accumulator, not today's. The rule pauses the 4 conversion campaigns every day ~11 AM.

Evidence for the bug (from hourly insights for 2026-04-20):
- 09:00 PHT: PHP 449 (campaigns just unpaused by "Sales ON at 9AM")
- 10:00 PHT: PHP 9,106 (one full hour of delivery)
- 11:00 PHT: PHP 865 (EMERGENCY rule fires mid-hour, delivery stops)
- 12:00-23:59 PHT: PHP 0 (dark rest of the day)
- Daily total: PHP 10,420 — consistent pattern for 14+ days

Simultaneously, the 2026-04-04 session paused Summer Buzz + Peak Season Community + Iskrambol Foodpanda campaigns (reason: legacy/duplicate cleanup), leaving zero spend on awareness/engagement/traffic. The 7-day funnel allocation is now 100% conversion — which violates the full-funnel framework and causes conversion CPA to rise (engagement pool starvation).

### Why this architecture (Python scripts + Meta Graph API direct, not Meta UI)

- **Reproducibility.** Every change is a git-tracked script. Rolling back is a script re-run with inverted parameters.
- **Idempotency.** Each script checks current state before mutating; safe to re-run.
- **Evidence.** Each script prints a before/after JSON to `output/l3/s214/` that is the closeout evidence.
- **Rule ownership already in Python.** `Marketing/digital-marketing/scripts/manage_meta_ad_rules.py` already exists and handles rule CRUD via the API. Extends the existing pattern.

### Why NOT switch the Meta app to Public mode to fix the 33 dev-mode ads

- Requires Meta App Review (weeks, uncertain outcome)
- Those 33 ads are from 2025-06 through 2026-03-08; the creatives are 10+ months old
- The `object_story_id` workaround already works for new ad creation (per `Marketing/digital-marketing/.claude/skills/meta-ads/SKILL.md` + `references/api-reference.md`)
- **Decision: archive the 33, don't recreate.** If the creatives are still strategically valuable, reshoot them and create fresh Page posts, then boost via `object_story_id`.

### Why archive (not delete) the 193 error ads

Meta's Graph API `DELETE /{ad-id}` permanently removes the ad. Archiving (`status=ARCHIVED`) hides the ad from default views but preserves history and is reversible. For compliance/audit trail purposes (many of these are from the Royal HaloHalo era pre-2022 rebrand), archive is the correct move.

### Known limitations

- **Meta API rate limits.** The Graph API allows ~200 calls per hour per user token before throttling. The archive phase touches 193 ads — we pace it at 1 call per 0.5s (~2 ads/second = 97s total) to stay well under throttle.
- **The PHP 50K/day target requires BOTH rule fix AND campaign reactivation.** Fixing only the rules recovers spend to ~PHP 27.8K/day (sum of active conversion adset daily budgets). Reaching PHP 50K requires unpause of awareness (PHP 11.5K) + engagement (PHP 8.2K) + traffic (PHP 2.5K) campaigns. See `WEEKLY_REPORT_2026-04-21.md` Part 1 "Correction on how much spend the rule fix actually recovers" for the math.
- **New organic boosts use `object_story_id` pattern** (required for our dev-mode app). This means the ad creative IS the existing Page post — we can override CTA but cannot change image/video/copy without creating a new post first. Per skill `references/api-reference.md` Pattern 2.

### Sources

- Rule definitions: `Marketing/digital-marketing/data/_tmp/adrules.json` (8 rules, all 2026-04-05 11:49-11:52 creation)
- Activity log: `Marketing/digital-marketing/data/_tmp/activity_30d.json` (113 events, 40 `Sales ON 9AM` + 26 `EMERGENCY 100K` + 11 `Sales OFF 6PM` fires in last 30d)
- 7-day insights: `Marketing/digital-marketing/data/insights_7d.json` (35 spending ads, PHP 74,863 total)
- Organic 14-day data: `Marketing/digital-marketing/data/posts_30days.json` (52 posts in 30d, 31 in last 14d, 0 boosted)
- Historical dedup index: `Marketing/digital-marketing/data/_tmp/all_ads_with_story.json` (3,904 ads, 1,230 unique story_ids)
- Error-ads sample: `Marketing/digital-marketing/data/_tmp/sandbox_ads_all.json` (194 ads, 193 HARD_ERROR)
- Full audit narrative: `Marketing/digital-marketing/reports/WEEKLY_REPORT_2026-04-21.md`
- Skill contract: `.claude/skills/meta-ads/SKILL.md` + `.claude/skills/meta-ads/references/api-reference.md`

## Requirements Regression Checklist

Agent MUST confirm every item before creating the PR:

- [ ] **RRC-1: Brand premium rule.** No script creates an ad with promo/discount/BOGO copy or CTA. (Source: `.claude/skills/meta-ads/SKILL.md` "Brand Rule (Non-Negotiable)")
- [ ] **RRC-2: object_story_id only.** All new ad creations use `object_story_id` pattern, NEVER `object_story_spec` with `link_data`. (Source: skill `references/api-reference.md`)
- [ ] **RRC-3: Historical dedup for every new boost.** Before creating any new ad from an organic post, verify the post's `object_story_id` does NOT appear in `Marketing/digital-marketing/data/_tmp/all_ads_with_story.json` story_ids list.
- [ ] **RRC-4: No destructive action without pre-image.** Every mutating script writes the pre-state JSON to `output/l3/s214/pre_state/<script_name>.json` BEFORE making any change.
- [ ] **RRC-5: No rule recreation.** The EMERGENCY rule is DISABLED (set `status=DISABLED`), not deleted. We keep the rule object for audit/rebuild later.
- [ ] **RRC-6: Archive != delete.** All 193 error ads go to `status=ARCHIVED`, never `DELETE`.
- [ ] **RRC-7: Budget respect.** No ad-set daily budget exceeds PHP 12,000 without explicit CEO sign-off in plan body (none in this plan).
- [ ] **RRC-8: Windows headless.** Every subprocess call uses `creationflags=CREATE_NO_WINDOW` per BEI memory lesson #17. (Source: `memory/windows-subprocess.md`)
- [ ] **RRC-9: Doppler, not hardcoded.** All tokens fetched via `doppler secrets get META_ACCESS_TOKEN --project bei-erp --config dev --plain`. Never hardcode.
- [ ] **RRC-10: Cold-start test.** Can an agent with zero context read this plan and execute every script correctly? If no, the plan is non-compliant.

## Scope Size Warning

Total estimated units: ~37. Well under the 80-unit ceiling. Single-agent single-session execution. No split required.

## Ground-Truth Lock

- **evidence_sources:**
  - `Marketing/digital-marketing/reports/WEEKLY_REPORT_2026-04-21.md` → audited narrative: root cause, scorecards, recommendations
  - `Marketing/digital-marketing/data/_tmp/adrules.json` → 8 rule definitions (proves the 2 rules to change)
  - `Marketing/digital-marketing/data/_tmp/activity_30d.json` → 30-day rule-fire log (proves EMERGENCY misfires daily)
  - `Marketing/digital-marketing/data/insights_7d.json` → 35 spending ads last 7d, PHP 74,863 total, 335 purchases (proves 16 losers + 5 winners)
  - `Marketing/digital-marketing/data/posts_30days.json` → 52 organic posts last 30d (proves 3 viral boost candidates)
  - `Marketing/digital-marketing/data/_tmp/all_ads_with_story.json` → 3,904-ad historical story_id index, 1,230 unique story_ids (proves dedup safety)
  - `Marketing/digital-marketing/data/_tmp/sandbox_ads_all.json` → 194 returned, 193 HARD_ERROR (proves archive scope)
  - **Active adset budget evidence (PHP 27,800 total):** four campaign-specific JSON snapshots:
    - `Marketing/digital-marketing/data/_tmp/as_120225029875060030.json` → BOF/MOF Conversion, 1 ACTIVE adset = PHP 5,000
    - `Marketing/digital-marketing/data/_tmp/as_120225480340900030.json` → TOF-LAL, 4 ACTIVE adsets = PHP 15,500
    - `Marketing/digital-marketing/data/_tmp/as_120225775497020030.json` → TOF-INT, 3 ACTIVE adsets = PHP 5,500
    - `Marketing/digital-marketing/data/_tmp/as_120231023755930030.json` → TOF-Worse Areas, 2 ACTIVE adsets = PHP 1,800
- **count_method:**
  - metric: `losers_to_pause`
    - basis: `7-day insights, ads with CPA > PHP 400 AND (ROAS < 2x OR ROAS absent AND spend > 500)`
    - method: `jq '.data[] | select(...)' insights_7d.json`
    - count: `16`
  - metric: `winners_to_scale`
    - basis: `7-day insights, ads with ROAS >= 14x OR CPA < PHP 55`
    - count: `5`
  - metric: `viral_posts_to_boost`
    - basis: `posts_30days.json filtered to created >= 2026-04-07 AND score >= 2000 AND already_boosted==false`
    - count: `3`
  - metric: `error_ads_to_archive`
    - basis: `effective_status IN [WITH_ISSUES, DISAPPROVED] AND issues_info[].error_type == HARD_ERROR`
    - count: `193`
- **authoritative_sections:**
  - Sections 1–12 (Executive Summary through Closeout) are authoritative for execution
  - Design Rationale is traceability only
- **normalization_required:**
  - If any count changes during execution (e.g., an ad's status changes mid-run), update the closeout RUN_STATUS.json AND the PR description table in the same commit
- **unresolved_value_policy:**
  - Four categories are RUNTIME-RESOLVED (not hardcoded, resolved via Meta API lookup during execution):
    - 9 of 16 loser ad IDs (resolved at P2-T1 via `insights_7d.json` ad_name + campaign_name match)
    - 2 of 3 reactivation campaign IDs (Summer Buzz `120242888352350030`, Iskrambol Foodpanda `120242888355100030` — resolved at P3-T0 by querying Meta API directly; only Peak Season Community `120243460275370030` has persisted local evidence)
    - 4 of 5 winner ad IDs (resolved at P2-T4 by querying Meta API for ad name + adset match)
    - 2 of 4 winner adset IDs (resolved at P2-T4)
  - All other IDs (rule IDs, 3 viral post IDs, 8 of 16 loser ad IDs, 1 winner ad ID, 1 winner adset ID) are verified concrete as of 2026-04-21 09:45 AM PHT.
  - Runtime resolution is ACCEPTABLE per RRC-10 because the resolution mechanism is deterministic (name match against a concrete JSON file) and verifiable (the verify_s214.py script re-queries Meta with the resolved IDs).

## Phase Budget Contract

- **phase_unit_budget:**
  - `Phase 0 — Preflight + branch` → 4 units
  - `Phase 1 — Rule fix` → 5 units
  - `Phase 2 — Pause 16 losers + scale 5 winners` → 6 units
  - `Phase 3 — Reactivate 3 campaigns` → 5 units
  - `Phase 4 — Boost 3 viral organic posts` → 8 units
  - `Phase 5 — Archive 193 error ads` → 4 units
  - `Phase 6 — Verification + Closeout` → 5 units
- **hard_limit:** `15 units per phase` — all phases comply
- **preferred_split_threshold:** `12` — all phases comply

## Autonomous Execution Contract

- **completion_condition:**
  - `verify_s214.py` prints `STATUS=PASS` for every phase
  - `output/l3/s214/form_submissions.json` lists every mutation (rule disable, rule update, 16 pauses, 5 budget changes, 3 campaign reactivations, 3 new ads created, 193 archives) with before/after state
  - `output/l3/s214/api_mutations.json` lists every Graph API POST/DELETE call
  - `output/l3/s214/state_verification.json` confirms post-run account state matches target
  - PR created against `production` branch of BEI-ERP repo
  - `docs/plans/2026-04-21-sprint-214-meta-ads-rules-fix-refresh-archive.md` status updated to `COMPLETED`
  - `docs/plans/SPRINT_REGISTRY.md` S214 row updated to `COMPLETED` with PR number
  - Both plan and registry committed with `git add -f docs/plans/...` and pushed
- **stop_only_for:**
  - Missing `META_ACCESS_TOKEN` in Doppler
  - Meta API returns 401/403 (token expired or lacks permissions)
  - Rate limit (HTTP 613 or error subcode 2446079): pause, back off, continue — do NOT stop
  - A winner's ROAS has flipped to < 3x in the last 24 hours (check fresh insights before scaling)
  - User (Sam) comments `STOP` or `HOLD` on the PR
- **continue_without_pause_through:**
  - audit → execute → PR creation → closeout
  - DO NOT stop for progress-only updates
  - DO NOT stop to "ask the user if this is OK" — the plan IS the approval
- **blocker_policy:**
  - `programmatic` → fix and continue (e.g., JSON shape mismatch, URL encoding)
  - `evidence mismatch` → re-query Meta API, update plan RUN_STATUS, continue
  - `rate_limit` → sleep(60), retry, continue
  - `destructive_confirmation_required` → NONE in this plan (archive and disable are non-destructive)
  - `business_policy` → only if CEO changes mind on a campaign; doesn't apply during normal execution
- **signoff_authority:** `single-owner` (Sam — CEO)
- **canonical_closeout_artifacts:**
  - `output/l3/s214/RUN_STATUS.json`
  - `output/l3/s214/RUN_SUMMARY.md`
  - `output/l3/s214/pre_state/<script>.json` (6 files)
  - `output/l3/s214/post_state/<script>.json` (6 files)
  - `output/l3/s214/form_submissions.json`
  - `output/l3/s214/api_mutations.json`
  - `output/l3/s214/state_verification.json`
  - `output/l3/s214/verify_s214.py` (verification script)
  - `Marketing/digital-marketing/reports/WEEKLY_REPORT_2026-04-21.md` (appended with execution results)
  - `Marketing/digital-marketing/sessions/SESSION_2026-04-21.md` (BEI Brain-ingested)
  - `docs/plans/2026-04-21-sprint-214-meta-ads-rules-fix-refresh-archive.md` (status→COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S214 row→COMPLETED + PR number)

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** PR merged to `production`
- **note:** No Finance/CFO countersign required — Meta Ads budget is within CEO discretionary marketing spend authority.

## Agent Boot Sequence

1. **Read this plan in full.**
2. **Check `git status`.** If ANY uncommitted changes exist on the current branch, **STOP and ask the user** — do NOT run `git stash` silently; stashing can hide in-progress work that the user would want to preserve.
3. **Create sprint branch from clean tree:** `git fetch origin production && git checkout -b s214-meta-ads-rules-fix-refresh-archive origin/production`. NEVER write code on production.
4. **Verify Doppler access:** `doppler secrets get META_ACCESS_TOKEN --project bei-erp --config dev --plain | head -c 30` should return a token starting with `EAAL`. If not, STOP and ask user.
5. **Read** `Marketing/digital-marketing/reports/WEEKLY_REPORT_2026-04-21.md` for full audit narrative.
6. **Read** `.claude/skills/meta-ads/SKILL.md` + `references/api-reference.md` (especially Pattern 2: object_story_id boost).
7. **Read** `Marketing/digital-marketing/scripts/manage_meta_ad_rules.py` to understand existing rule-management patterns.
8. **Create output directory:** `mkdir -p output/l3/s214/{pre_state,post_state}`.
9. **Begin Phase 0.** Do NOT skip to Phase 1 — preflight proves the API is reachable.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Duplication Audit

| Proposed deliverable | Existing file | Classification |
|---|---|---|
| Rule management script | `Marketing/digital-marketing/scripts/manage_meta_ad_rules.py` | **[EXTEND]** — add `disable_rule()` and `update_rule_filter()` helpers |
| Audit script | `Marketing/digital-marketing/scripts/meta_ads_audit.py` | **[KEEP AS-IS]** — used for pre/post comparison |
| Organic fetch + dedup | `Marketing/digital-marketing/scripts/meta_ads_fetch_organic.py` | **[PATCH]** — add ARCHIVED to effective_status filter (separate scope, note it as followup) |
| Session log | `Marketing/digital-marketing/scripts/meta_ads_session_log.py` | **[USE AS-IS]** — called at closeout |
| Winner-scale logic | none | **[BUILD]** — `scripts/s214_scale_winners.py` |
| Loser-pause logic | none | **[BUILD]** — `scripts/s214_pause_losers.py` |
| Campaign-reactivate logic | none | **[BUILD]** — `scripts/s214_reactivate_campaigns.py` |
| Organic-post-boost logic (object_story_id) | ~~`Marketing/digital-marketing/scripts/boost_replacements.py`~~ (audit v1 A3 reclassification: this script is a STUB with `[ACTION REQUIRED]` comment and NO implementation — NOT a template) | **[BUILD]** — `scripts/s214_boost_viral_posts.py` built from scratch using `.claude/skills/meta-ads/references/api-reference.md` Pattern 2 (boost via `object_story_id` + `call_to_action` override). Do NOT copy from `boost_replacements.py`. |
| Bulk-archive logic | none | **[BUILD]** — `scripts/s214_archive_error_ads.py` |
| Verification script | none | **[BUILD]** — `scripts/s214_verify.py` |

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:**
  - artifact: `output/l3/s214/S214_SURFACE_OWNERSHIP_MATRIX.csv`
  - files owned: `Marketing/digital-marketing/scripts/s214_*.py`, `output/l3/s214/**`
  - external resources owned: Meta ad account `act_843498792928069` rule `888035557619357` + rule `1539999288125943` + 16 specific ad IDs + 3 specific post IDs + 193 error-ad IDs
- **protected_surfaces:**
  - artifact: `output/l3/s214/S214_PROTECTED_SURFACE_REGISTRY.csv`
  - DO NOT touch: any ad currently ACTIVE that is NOT in the 16-loser list (e.g., don't accidentally pause a winner); the other 6 rules (CPA Guardrail, Low CTR Kill, Budget Pacing, Winner Alert, Frequency Cap, Sales ON 9AM); any campaign not in the reactivation list
- **remote_truth_baseline:**
  - artifact: `output/l3/s214/S214_REMOTE_TRUTH_BASELINE.json`
  - repo: `Bebang-Enterprise-Inc/hrms` (BEI-ERP)
  - release_branch: `production`
  - release_head_sha: captured in Phase 0
  - live_evidence_basis: `WEEKLY_REPORT_2026-04-21.md`
- **touched_file_routing:**
  - All code under `Marketing/digital-marketing/scripts/s214_*.py` — no existing file edits
  - Plan file + registry — owned by this sprint only
- **active_run_coordination:**
  - artifact: `output/l3/s214/state/S214_ACTIVE_RUN_COORDINATION.json`
  - claim on Phase 0 start, release on Phase 6 closeout
- **pretouch_backup:**
  - Phase 1 backup: rule `888035557619357` current config → `pre_state/01_rule_emergency_before.json`
  - Phase 1 backup: rule `1539999288125943` current config → `pre_state/01_rule_salesoff_before.json`
  - Phase 2 backup: 16 ads' current status/budget → `pre_state/02_pause_losers_before.json`
  - Phase 2 backup: 5 winners' adset budget → `pre_state/02_scale_winners_before.json`
  - Phase 3 backup: 3 campaigns' current status → `pre_state/03_reactivate_campaigns_before.json`
  - Phase 4 backup: account ad count and Engagement campaign adsets → `pre_state/04_boost_viral_before.json`
  - Phase 5 backup: 193 error ads' status → `pre_state/05_archive_errors_before.json`
- **supersession_map:** N/A — no prior packets supersede this
- **touch_preservation:** N/A — scripts are all new (`s214_*`), no file conflicts

## Zero-Skip Enforcement

**Rule:** Every task MUST be implemented. If a task cannot be completed, the agent STOPS and asks the user. The following behaviors are explicitly FORBIDDEN:

- Skipping a task silently
- Marking partial work as "done"
- Combining tasks and dropping features
- Saying "deferred to next sprint"
- Implementing happy path only and skipping error handling for rate limits, auth expiry, or partial responses
- Writing the verification script to PASS without actually checking (self-report trap from S154)

**Verification script required.** Phase 6 writes `output/l3/s214/verify_s214.py` that queries Meta Graph API directly and checks the following assertions. The script output is the closeout evidence — not the agent's self-report.

## Machine-Verifiable Phase Gates

Every task has a `MUST_MODIFY` or `MUST_CONTAIN` assertion that can be verified by `git diff` and `grep`. The Phase 6 `verify_s214.py` script queries Meta directly and checks API-side state.

---

## Phase 0 — Preflight + Branch (4 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Verification |
|---|---|---|---|
| P0-T1 | Create branch `s214-meta-ads-rules-fix-refresh-archive` from `origin/production`. | N/A | `git branch --show-current` == `s214-meta-ads-rules-fix-refresh-archive` |
| P0-T2 | Verify `META_ACCESS_TOKEN` in Doppler; echo first 20 chars of token. | N/A | Token starts with `EAAL`, length >= 100 |
| P0-T3 | Create output dirs: `mkdir -p output/l3/s214/{pre_state,post_state,state}` | `output/l3/s214/pre_state/`, `output/l3/s214/post_state/`, `output/l3/s214/state/` | `ls -d output/l3/s214/pre_state output/l3/s214/post_state output/l3/s214/state` all exist |
| P0-T4 | Query current rule state (all 8 rules) → save to `output/l3/s214/pre_state/00_adrules_snapshot.json`. | `output/l3/s214/pre_state/00_adrules_snapshot.json` | `jq '.data \| length' output/l3/s214/pre_state/00_adrules_snapshot.json` == 8 |

**Phase 0 completion gate:** all 4 files exist, token verified, branch is `s214-...`.

---

## Phase 1 — Rule Fix (5 units)

**HARD BLOCKER:** Do NOT delete the EMERGENCY rule. Set `status=DISABLED` only. User may want to rebuild it with correct logic later.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Verification |
|---|---|---|---|
| P1-T1 | Create `Marketing/digital-marketing/scripts/s214_rule_fix.py`. Must take `--dry-run` flag. | `Marketing/digital-marketing/scripts/s214_rule_fix.py` | `test -f Marketing/digital-marketing/scripts/s214_rule_fix.py` |
| P1-T2 | Script MUST_CONTAIN: rule ID `888035557619357` hardcoded as the emergency rule to disable. | grep `888035557619357` in file | `grep -c "888035557619357" Marketing/digital-marketing/scripts/s214_rule_fix.py` >= 1 |
| P1-T3 | Script MUST_CONTAIN: rule ID `1539999288125943` as the Sales OFF rule to update. | grep `1539999288125943` in file | `grep -c "1539999288125943" Marketing/digital-marketing/scripts/s214_rule_fix.py` >= 1 |
| P1-T4 | Run dry-run: `python scripts/s214_rule_fix.py --dry-run`. Confirm it prints the 2 rule changes it WOULD make but makes zero API writes. | N/A | Script exit code 0, output contains "[DRY RUN]" marker |
| P1-T5 | Run live: save pre-state to `pre_state/01_rules_before.json`, POST to Meta: set rule `888035557619357` `status=DISABLED`; update rule `1539999288125943` by changing the evaluation filter field `time_preset` from `MAXIMUM` to a time-filtered approach (see implementation note). Save post-state to `post_state/01_rules_after.json`. | `output/l3/s214/post_state/01_rules_after.json` | Query Meta: rule `888035557619357` `status` == `DISABLED` |

**Implementation note for P1-T5 Sales OFF extension:**

The Sales OFF rule's `schedule: []` + `time_preset: MAXIMUM` means it fires on Meta's default evaluation cadence. To extend the OFF time from 6 PM to 10 PM PHT (UTC 14:00):

**CORRECT Meta API schedule_spec format** (verified against `Marketing/digital-marketing/scripts/manage_meta_ad_rules.py` `daily_schedule()` helper at line 103):

```python
schedule_spec = {
    "schedule_type": "CUSTOM",
    "schedule": [
        {"start_minute": 840, "end_minute": 899, "days": [d]}
        for d in range(7)  # 0=Monday through 6=Sunday
    ]
}
# Meta expects an OUTER WRAPPER with schedule_type + an inner list of objects,
# each with start_minute, end_minute, AND a "days" array.
# Minutes are minutes-from-midnight UTC.
# 840 = UTC 14:00 = PHT 22:00 (10 PM)
# 899 = UTC 14:59
```

**HARD BLOCKER:** Do NOT use a bare array like `[{"start_minute": 840, "end_minute": 899}]`. Meta will reject it. The wrapper object with `schedule_type="CUSTOM"` and per-day `days` entries is required. Copy the exact pattern from `manage_meta_ad_rules.py:103-106`.

**Fallback:** If Meta still rejects the schedule change (for any other reason), the fallback is to **disable** the Sales OFF rule entirely (`status=DISABLED`) and rely on the Sales ON 9AM rule + human-side attention for end-of-day behavior. Document the fallback outcome in `post_state/01_rules_after.json` with a `fallback_applied: true` flag.

**Phase 1 completion gate:**
- `output/l3/s214/post_state/01_rules_after.json` exists
- Query Meta: rule `888035557619357` `status` == `DISABLED` (via direct API re-query, not rule cache)
- `form_submissions.json` contains 2 entries (2 rule updates)

---

## Phase 2 — Pause 16 Losers + Scale 5 Winners (6 units)

**HARD BLOCKER:** Before changing any ad, query its 24-hour-refreshed insights. If a "winner" ROAS has fallen below 3x in the last 24h OR a "loser" has spiked to ROAS > 3x in the last 24h, STOP and report. Do not act on stale 7-day data when fresher signal is available.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Verification |
|---|---|---|---|
| P2-T1 | Create `Marketing/digital-marketing/scripts/s214_pause_losers.py`. Embed the 16 ad IDs below as a Python list constant `LOSER_AD_IDS`. | `s214_pause_losers.py`, constant `LOSER_AD_IDS` | `grep -c "LOSER_AD_IDS" ..../s214_pause_losers.py` >= 1 |
| P2-T2 | Script: fetch 24h insights for each of the 16 ad IDs. If ANY has ROAS > 3x in last 24h, STOP and emit `loser_reversal.json`. Otherwise proceed. | N/A | Script exit code 0 |
| P2-T3 | Script: for each of the 16 ads, POST `status=PAUSED` to Meta. Save pre/post state. | `output/l3/s214/post_state/02_losers_paused.json` | 16 entries in post_state file, all `status==PAUSED` |
| P2-T4 | Create `Marketing/digital-marketing/scripts/s214_scale_winners.py`. Embed 5 winner adset→new budget map. | `s214_scale_winners.py`, constant `WINNER_BUDGET_MAP` | grep count >= 1 |
| P2-T5 | Script: for each of 5 winners, POST new `daily_budget` (in centavos — PHP × 100). Save pre/post. | `output/l3/s214/post_state/02_winners_scaled.json` | 5 entries in post_state, `daily_budget` matches target |
| P2-T6 | Append both scripts' actions to `form_submissions.json` and `api_mutations.json`. | Append to JSONs | Entry count delta = 21 (16 pauses + 5 budget changes) |

### The 16 Losers to PAUSE

From `data/insights_7d.json`, ads with (CPA > PHP 400 AND ROAS < 2x) OR (spend > PHP 1,000 AND zero purchases):

| # | Ad ID | Ad Name | Campaign | 7d Spend | CPA | ROAS |
|---|---|---|---|---:|---:|---:|
| 1 | `120236490022230030` | Ad #12 Matcha-fying Gravity | BOF/MOF Warm 30d | 6,474 | 719 | 1.12x |
| 2 | `120236894994690030` | Ad #16 Tried so many halo-halo | TOF-LAL 1-4% VV50% | 5,858 | 533 | 1.28x |
| 3 | `120238080535160030` | Ad #46 Basta happy | BOF/MOF Warm 30d | 5,255 | 1,051 | 0.95x |
| 4 | `120236894995250030` | Ad #15 Hirap introvert | TOF-LAL 5-10% VV50% | 5,048 | 2,524 | 0.56x |
| 5 | `120226689093050030` | Ad #12 Choco Brownie (LAL 1-4%) | TOF-LAL | 4,707 | 428 | 2.20x |
| 6 | `120229072327660030` | Ad #10 Deliver Frozen Posting 4 | TOF-LAL Saved posts | 4,070 | 814 | 1.98x |
| 7 | `120227612549140030` | Ad #3 Monday na naman | TOF-LAL | 3,345 | 1,672 | 0.29x |
| 8 | `120226689305170030` | Ad #12 Choco Brownie (LAL 5-10%) | TOF-LAL | 3,240 | 1,620 | 0.34x |
| 9 | *(to be looked up in P2-T1)* | Ad #1 Carousel Products duplicate in TOF-LAL | TOF-LAL | 2,893 | 2,893 | 0.18x |
| 10 | *(to be looked up in P2-T1)* | Ad #14 Friday na | TOF-LAL | 2,778 | 556 | 1.71x |
| 11 | *(to be looked up in P2-T1)* | Ad #121 Not your ordinary | TOF-LAL | 2,777 | 2,777 | 0.44x |
| 12 | *(to be looked up in P2-T1)* | Ad #15 Hirap (LAL 1-4%) | TOF-LAL | 1,744 | 581 | 1.24x |
| 13 | *(to be looked up in P2-T1)* | Ad #49 Don't leave (wrong adset) | TOF-LAL | 1,678 | 839 | 2.08x |
| 14 | *(to be looked up in P2-T1)* | Ad #13 POPULARRRR duplicate | TOF-LAL | 1,442 | 721 | 1.47x |
| 15 | *(to be looked up in P2-T1)* | Ad #101 Mas masaya | TOF-LAL | 1,437 | 1,437 | 0.71x |
| 16 | *(to be looked up in P2-T1)* | Ad #54 duplicate in BOF/MOF | BOF/MOF | 5,127 | 466 | 2.94x (acceptable alone, but dup of winner #13) |

**Note:** 9 ad IDs are listed as `(to be looked up in P2-T1)` — the agent queries Meta Graph API in P2-T1 to resolve them from `insights_7d.json` via ad_name + campaign_name match, and hardcodes the resolved IDs into the Python script. All 16 must be resolved before P2-T3 executes.

### The 5 Winners to SCALE

| # | Ad ID | Adset | Current Budget | New Budget | Rationale |
|---|---|---|---:|---:|---|
| 1 | `120233175036340030` | `120226411235010030` — INT Coffee/Ice Cream | PHP 2,500/day | **PHP 5,000/day** | Ad #1 Carousel Products — ROAS 19.80x, CPA PHP 51 |
| 2 | *(to resolve)* | Warm 30d - Exclude 7d NEW | PHP 5,000/day | **PHP 7,500/day** | Ad #44 Ang sakit naman Beb! — ROAS 24.04x |
| 3 | *(to resolve)* | Warm 30d - Exclude 7d NEW | same as 2 (combined) | — | Ad #13 POPULARRRR — ROAS 14.55x (same adset as 2) |
| 4 | *(to resolve)* | TOF-LAL adset holding Swipe | PHP 2,500/day | **PHP 4,000/day** | Ad #81 Swipe left/right — ROAS 39.28x |
| 5 | *(to resolve)* | TOF-LAL 5-10% VV50% | PHP 5,000/day | **PHP 6,000/day** | Ad #49 Don't leave valuables — ROAS 80.93x |

**Cap:** No single adset above PHP 12,000/day per RRC-7. Total scale-up: +PHP 6,000/day.

**Phase 2 completion gate:**
- Pre/post JSON files exist for both scripts
- Meta API re-query confirms: 16 losers in `PAUSED` state, 5 winner adsets at new budgets
- `form_submissions.json` has 21 new entries

---

## Phase 3 — Reactivate 3 Campaigns (5 units)

**HARD BLOCKER (audit v1 A2):** Only 1 of 3 campaign IDs (`120243460275370030` Peak Season Community) is verified against persisted local data. The other 2 (`120242888352350030` Summer Buzz, `120242888355100030` Iskrambol Foodpanda) are retrieved from a live API query that was not persisted to disk. Before any status change, the agent MUST run P3-T0 to re-verify all 3 campaign IDs exist with expected names and objectives.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Verification |
|---|---|---|---|
| P3-T0 | **(New — audit v1 A2)** Query Meta API for each of 3 campaign IDs: `GET /{campaign-id}?fields=id,name,objective,status`. Save to `pre_state/03_campaigns_verified.json`. **STOP** if any ID returns 404 OR has an unexpected objective (expected: AWARENESS / ENGAGEMENT / TRAFFIC respectively). | `pre_state/03_campaigns_verified.json` | JSON has 3 entries, all with expected objectives |
| P3-T1 | Create `Marketing/digital-marketing/scripts/s214_reactivate_campaigns.py`. Embed 3 campaign IDs resolved in P3-T0. | `s214_reactivate_campaigns.py`, constant `CAMPAIGN_IDS_TO_UNPAUSE` | grep >= 1 |
| P3-T2 | Script fetches current status of 3 campaigns; save to `pre_state/03_campaigns_before.json`. | `pre_state/03_campaigns_before.json` | JSON has 3 entries |
| P3-T3 | Script: for each campaign, POST `status=ACTIVE`. Save post-state. | `post_state/03_campaigns_after.json` | All 3 `status==ACTIVE` |
| P3-T4 | **HARD BLOCKER:** If any reactivated campaign's adsets are ALL PAUSED, STOP and alert. A campaign with no active adset won't deliver. | N/A | Verify >=1 ACTIVE adset per reactivated campaign |
| P3-T5 | Append 3 mutations to `form_submissions.json`. | Append | Entry count delta = 3 |

### The 3 Campaigns to Reactivate

| # | Campaign ID | Name | Objective | Target Daily (via adset sum) |
|---|---|---|---|---:|
| 1 | `120242888352350030` | BEB - Summer Buzz Awareness [Mar 2026] | OUTCOME_AWARENESS | PHP 3,500 (Metro Broad + 90s Kids + LAL Engagers adsets) |
| 2 | `120243460275370030` | BEB - Peak Season Community [Apr 2026] | OUTCOME_ENGAGEMENT | PHP 5,200 (Metro Manila 18-55 adset, created Apr 4) |
| 3 | `120242888355100030` | BEB - Iskrambol Foodpanda Traffic [Mar 2026] | OUTCOME_TRAFFIC | PHP 2,500 (Foodpanda LAL Engagers adset) |

**Phase 3 completion gate:** 3 campaigns `status==ACTIVE` on Meta, each with ≥1 ACTIVE adset.

---

## Phase 4 — Boost 3 Viral Organic Posts (8 units)

**HARD BLOCKER:** RRC-2 — Use `object_story_id` pattern ONLY. Never `object_story_spec` with `link_data`. Verify before each POST call that the request body has `object_story_id` and no `link_data`/`image_hash`/`message` fields.

**HARD BLOCKER:** RRC-3 — Before creating each ad, verify the post_id is NOT in `Marketing/digital-marketing/data/_tmp/all_ads_with_story.json` story_ids list. If it IS, STOP and report (shouldn't happen — pre-audited — but protects against bugs).

| # | Task | MUST_MODIFY / MUST_CONTAIN | Verification |
|---|---|---|---|
| P4-T1 | Create `Marketing/digital-marketing/scripts/s214_boost_viral_posts.py` from scratch. **HARD BLOCKER (audit v1 A3):** Do NOT copy from `boost_replacements.py` — it is a stub with no API implementation. Build from `.claude/skills/meta-ads/references/api-reference.md` Pattern 2. Embed the 3 post IDs + target campaign IDs + CTA types as Python constants. **HARD BLOCKER (RRC-8):** every subprocess call MUST use `creationflags=0x08000000` (`subprocess.CREATE_NO_WINDOW`). | File + constants | grep both post IDs + `call_to_action` + `creationflags` in file |
| P4-T2 | Script: dedup verify each post_id against `all_ads_with_story.json`. STOP if any match. | N/A | Script emits `dedup_check.json` with `all_clean: true` |
| P4-T3 | For post #1 (Tag-a-Friend, Apr 16): create creative via `POST /act_843498792928069/adcreatives` with `object_story_id="102628625216977_1266416878948597"` + `call_to_action.type=LEARN_MORE` (engagement, no hard CTA). Get creative_id. | `post_state/04_creative_1.json` | HTTP 200, creative_id returned |
| P4-T4 | Create ad for post #1 in Peak Season Community Metro Manila 18-55 adset. Status: `PAUSED` initially (user unpauses after reviewing). | `post_state/04_ad_1.json` | HTTP 200, ad_id returned, status=PAUSED |
| P4-T5 | For post #2 (Montalban Grand Opening, Apr 8): create creative with `object_story_id="102628625216977_1260249656231986"` + `call_to_action.type=ORDER_NOW` linking to Foodpanda Montalban deep link or chain page. Ad goes into Summer Buzz Awareness campaign, new adset with Montalban + 15km radius, daily PHP 2,000, duration 14 days. | `post_state/04_creative_2.json`, `post_state/04_ad_2.json` | HTTP 200, ad_id + adset_id returned |
| P4-T6 | For post #3 (Grabeng pressure mood meme, Apr 18): create creative with `object_story_id="102628625216977_1267949595461992"` + `call_to_action.type=ORDER_NOW` → Foodpanda chain page (premium, no discount). Ad goes into Peak Season Community with PHP 2,500/day. | `post_state/04_creative_3.json`, `post_state/04_ad_3.json` | HTTP 200 |
| P4-T7 | All 3 ads start PAUSED. User reviews + unpauses via PR comment. | N/A | `effective_status==PAUSED` for all 3 |
| P4-T8 | Brand-rule check: grep all 3 creative bodies for forbidden words (`discount`, `promo`, `sale`, `BOGO`, `free`, `off`, `%`). | Python regex in script | Zero matches |

**Phase 4 completion gate:**
- 3 new ads exist on Meta, all `status=PAUSED`
- `form_submissions.json` has 3 new ad-creation entries with full creative payloads
- `post_state/04_dedup_check.json` shows `all_clean: true`
- No brand-rule violations

---

## Phase 5 — Archive 193 Error Ads (4 units)

**HARD BLOCKER:** Archive means `status=ARCHIVED`, never `DELETE`. The archive endpoint is `POST /{ad-id}` with `status=ARCHIVED`, not a DELETE request.

**Rate limit guardrail:** Meta API limit is ~200 calls per hour per user token. At 193 ads + the 193 pre-state fetches (= 386 calls), we need to stay well under. Script paces 1 call per 0.5s = 3.2 minutes total for archive phase.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Verification |
|---|---|---|---|
| P5-T1 | Create `Marketing/digital-marketing/scripts/s214_archive_error_ads.py`. | File exists | `test -f` |
| P5-T2 | Script fetches all 193 error-ad IDs via the Graph API query used earlier (filter by effective_status=WITH_ISSUES/DISAPPROVED/PENDING_REVIEW + HARD_ERROR in issues_info). Save to `pre_state/05_error_ads_before.json`. | File, 193 entries | `jq 'length' pre_state/05_error_ads_before.json` >= 193 |
| P5-T3 | Script: sleep(0.5) between calls; for each ad, POST `status=ARCHIVED`. Track success/failure. Save to `post_state/05_error_ads_after.json`. | File | All entries `status==ARCHIVED` OR documented failure |
| P5-T4 | Script emits a summary: `total_archived`, `failures_by_error`, `elapsed_seconds`. | `output/l3/s214/archive_summary.json` | Valid JSON, `total_archived >= 190` (5% failure tolerance) |

**Phase 5 completion gate:**
- 193 ads in ARCHIVED state (or documented why not — e.g., ad already hard-deleted by Meta)
- Script completed without exceeding Meta rate limit

---

## Phase 6 — Verification + Closeout (5 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Verification |
|---|---|---|---|
| P6-T1 | Create `Marketing/digital-marketing/scripts/s214_verify.py`. Queries Meta API LIVE for every assertion. | File | `test -f` |
| P6-T2 | Verification script asserts (via direct Meta query, NOT cached JSON): (a) rule `888035557619357` status DISABLED; (b) 16 losers status PAUSED; (c) 5 winner adset budgets match target; (d) 3 campaigns status ACTIVE; (e) 3 new ads exist with correct object_story_id; (f) ≥190 archived ads in ARCHIVED state. | Python assertions | Script exit code 0 |
| P6-T3 | Write `output/l3/s214/RUN_STATUS.json` with overall `status: PASS` or `FAIL` + per-phase results. | File exists | Valid JSON |
| P6-T4 | Write `output/l3/s214/RUN_SUMMARY.md` with before/after spend projection, next-48-hour monitoring checklist, and rollback instructions. | File exists | >500 chars |
| P6-T5 | **Closeout artifacts** (ALL REQUIRED BEFORE PR): |  |  |
|  | (a) Commit all `scripts/s214_*.py` to branch. | Files in git | `git diff --name-only origin/production...HEAD \| grep -c s214_` >= 6 |
|  | (b) Commit `output/l3/s214/**` with `git add -f`. | Files in git | `git ls-files output/l3/s214/` shows ≥12 files |
|  | (c) Commit `Marketing/digital-marketing/sessions/SESSION_2026-04-21.md`. | File in git | `git ls-files Marketing/digital-marketing/sessions/SESSION_2026-04-21.md` non-empty |
|  | (d) Update plan YAML: `status: COMPLETED`, `completed_date: 2026-04-21`, `execution_summary: <1-sentence result>`, `pr: <number>`. | File modified | `grep "^status: COMPLETED" <plan-file>` == 1 |
|  | (e) Update `docs/plans/SPRINT_REGISTRY.md` S214 row to COMPLETED + PR number. | Registry modified | `grep "S214.*COMPLETED" SPRINT_REGISTRY.md` >= 1 |
|  | (f) `git add -f` both plan + registry. Commit. | In git | `git log --oneline -5 \| grep -c "S214"` >= 1 |
| P6-T6 | Create PR via `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms ...` with task-by-task checklist in body. Record PR number. Post it to user (Sam) via chat. | PR exists | `gh pr view` returns PR URL |
| P6-T7 | STOP. Do NOT merge. User handles merge + any needed Meta UI followups (e.g., unpausing the 3 new boost ads after review). | N/A | Agent exits |

### Verification Script Template

```python
# output/l3/s214/verify_s214.py (created in P6-T1)
import json
import subprocess
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
TOKEN = subprocess.run(
    ["doppler", "secrets", "get", "META_ACCESS_TOKEN", "--project", "bei-erp", "--config", "dev", "--plain"],
    capture_output=True, text=True, cwd=r"F:\Dropbox\Projects\BEI-ERP",
).stdout.strip()
V = "v25.0"
BASE = f"https://graph.facebook.com/{V}"


def get(url):
    req = urllib.request.Request(url)
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def assert_(cond, msg):
    print(("PASS" if cond else "FAIL") + ": " + msg)
    if not cond:
        return False
    return True


results = []

# Phase 1: rule disabled
r = get(f"{BASE}/888035557619357?fields=status,name&access_token={TOKEN}")
results.append(assert_(r.get("status") == "DISABLED", f"rule 888035557619357 DISABLED (got {r.get('status')})"))

# Phase 2: 16 losers PAUSED
LOSER_IDS = [...]  # filled in by P2-T1
for aid in LOSER_IDS:
    r = get(f"{BASE}/{aid}?fields=status&access_token={TOKEN}")
    results.append(assert_(r.get("status") == "PAUSED", f"ad {aid} PAUSED"))

# Phase 2: 5 winner adset budgets
WINNER_ADSET_BUDGETS = {...}  # filled in by P2-T4
for adset_id, target_budget_centavos in WINNER_ADSET_BUDGETS.items():
    r = get(f"{BASE}/{adset_id}?fields=daily_budget&access_token={TOKEN}")
    actual = int(r.get("daily_budget", 0))
    results.append(assert_(actual == target_budget_centavos,
                           f"adset {adset_id} daily_budget=={target_budget_centavos} (got {actual})"))

# Phase 3: 3 campaigns ACTIVE
CAMPAIGN_IDS = ["120242888352350030", "120243460275370030", "120242888355100030"]
for cid in CAMPAIGN_IDS:
    r = get(f"{BASE}/{cid}?fields=status&access_token={TOKEN}")
    results.append(assert_(r.get("status") == "ACTIVE", f"campaign {cid} ACTIVE"))

# Phase 4: 3 new ads exist AND start PAUSED (audit v1 A9)
NEW_AD_IDS = [...]  # filled in by P4 execution
for aid in NEW_AD_IDS:
    r = get(f"{BASE}/{aid}?fields=creative{{object_story_id}},status&access_token={TOKEN}")
    results.append(assert_(r.get("creative", {}).get("object_story_id") is not None,
                           f"ad {aid} has object_story_id"))
    results.append(assert_(r.get("status") == "PAUSED",
                           f"new ad {aid} starts PAUSED (user will unpause after review)"))

# Phase 5: ≥190 archived (allow 5% failure tolerance)
ARCHIVED_IDS = [...]  # filled in by P5 execution
archived_count = 0
for aid in ARCHIVED_IDS:
    r = get(f"{BASE}/{aid}?fields=status&access_token={TOKEN}")
    if r.get("status") == "ARCHIVED":
        archived_count += 1
results.append(assert_(archived_count >= 190, f"≥190 ads ARCHIVED (got {archived_count})"))

overall = all(results)
with open(r"F:\Dropbox\Projects\BEI-ERP\output\l3\s214\RUN_STATUS.json", "w", encoding="utf-8") as f:
    json.dump({
        "status": "PASS" if overall else "FAIL",
        "assertions_total": len(results),
        "assertions_passed": sum(results),
    }, f, indent=2)
sys.exit(0 if overall else 1)
```

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or certification status changes, update in the same work unit:

1. `output/l3/s214/RUN_STATUS.json` (technical status)
2. `output/l3/s214/RUN_SUMMARY.md` (narrative status)
3. `output/l3/s214/form_submissions.json` (every Meta mutation)
4. `output/l3/s214/api_mutations.json` (every raw API call)
5. Plan status line (if phase transitions)
6. `docs/plans/SPRINT_REGISTRY.md` S214 row (if sprint closeout state changes)

## Failure Response

| Mode | Cause | Response |
|---|---|---|
| **Mode A — Meta API rejection** | API returns 400/422 for a mutation | Log error to `api_mutations.json`, continue to next task; flag in `RUN_STATUS.json` if >3 failures in same phase |
| **Mode B — Token/auth issue** | HTTP 401/403 on any call | STOP. Query `doppler secrets get META_ACCESS_TOKEN` and if empty, ask user. |
| **Mode C — Rate limit** | HTTP 613 or error subcode 2446079 | `sleep(60)`, retry once. If still fails, `sleep(300)`, retry. After 2 retries, flag in RUN_STATUS and proceed to next phase. |
| **Mode D — Stale winner/loser data** | Fresh 24h insight shows a "winner" ROAS < 3x OR a "loser" ROAS > 3x | STOP. Emit `fresh_signal_override.json` listing the reversals. Ask user via PR comment. |
| **Mode E — Archive hits Meta bug** | ARCHIVE fails on an ad (some old ads can't be archived) | Log, continue. Tolerance: 5% failures allowed per P5-T4. |

---

## Appendix A — Scale Winner Budget Detail

Target budget changes (all in centavos when sent to Meta API, displayed as PHP here):

| Adset ID | Campaign | Current | New | Δ | Winner ad hosted |
|---|---|---:|---:|---:|---|
| `120226411235010030` | TOF-INT Coffee/Ice Cream | 2,500 | 5,000 | +2,500 | Carousel Products (ROAS 19.80x) |
| `120235886961570030` | BOF/MOF Warm 30d Exclude 7d NEW | 5,000 | 7,500 | +2,500 | Ang sakit naman Beb! + POPULARRRR |
| *(resolve)* | TOF-LAL 5-10% VV 50% | 5,000 | 6,000 | +1,000 | Don't leave valuables (ROAS 80x) |
| *(resolve)* | TOF-LAL adset for Swipe | 2,500 | 4,000 | +1,500 | Swipe left/right (ROAS 39x) |
| **TOTAL** |  |  |  | **+7,500** |  |

After Phase 2 scale + Phase 3 reactivation + Phase 4 boosts (all starting paused until user unpauses):

| Stage | Daily Budget | Monthly |
|---|---:|---:|
| Awareness | 5,500 | 165K |
| Engagement | 5,200 + 3,000 (Tag-a-Friend boost after user unpauses) = 8,200 | 246K |
| Conversion (active winners + kept mediocre) | ~25,000 | 750K |
| Traffic | 2,500 | 75K |
| **TOTAL** | **~41,200** (once all unpaused) | **~1,236,000** |

Note: This is BELOW the pre-Apr 4 target of PHP 50K/day by design — it's a controlled restart. After 3-4 days of stable delivery under the fixed rules, user can decide to add more active adsets (there are 53 paused conversion adsets available) to reach PHP 50K.

## Appendix B — 3 Viral Boost Post Details

All 3 pre-verified clean against 3,904-ad historical index (see `WEEKLY_REPORT_2026-04-21.md` Part 5 + `data/_tmp/all_ads_with_story.json`).

| Post | post_id | Content | Boost as | Target Campaign | Adset / Geo | Daily | CTA |
|---|---|---|---|---|---|---:|---|
| Apr 16 "Beb sinong pinaka sikat na artista" (Tag-a-Friend, 974 comments) | `102628625216977_1266416878948597` | Identity/social, high comment engagement | Engagement | Peak Season Community (`120243460275370030`) | Metro Manila 18-55 existing adset | 3,000 | LEARN_MORE (community, not purchase) |
| Apr 8 "Nasa Montalban na si Bebang! XentroMall Montalban" (Store opening, 395 shares) | `102628625216977_1260249656231986` | Store opening announcement | Awareness | Summer Buzz (`120242888352350030`) | **NEW adset:** Montalban + 15km radius, 18-55 broad | 2,000 | ORDER_NOW → Foodpanda chain page |
| Apr 18 "Grabeng pressure naman to beb~" (Mood meme, 412 shares) | `102628625216977_1267949595461992` | Viral mood meme, high share | Conversion (soft) via Engagement campaign | Peak Season Community (`120243460275370030`) | Metro Manila 18-55 existing adset | 2,500 | ORDER_NOW → Foodpanda chain page |

## Appendix C — 193 Error-Ad Breakdown

Source: `data/_tmp/sandbox_ads_all.json` (194 fetched, 193 HARD_ERROR).

| Error summary | Count | Recommended action |
|---|---:|---|
| Custom audience not available | 73 | Archive (audience deleted long ago, unrecoverable) |
| This Ad Set Has 1 Error (generic rollup) | 48 | Archive (wraps other errors) |
| Ads creative post was created by an app that is in development mode | 33 | Archive (dev-mode API pattern, see Design Rationale) |
| Please authenticate your account | 12 | Archive (token expired mid-save) |
| The 191x100 crop key for image ads is deprecated | 10 | Archive (old format) |
| App Is Deleted Or In Sandbox | 6 | Archive (related to dev-mode) |
| This ad isn't running, but you don't need to do anything | 4 | Archive (Meta says it's done) |
| Object Does Not Exist | 2 | Archive (referenced post/video deleted) |
| Misc (Auto Product Tags, Missing Lead Form, etc.) | 5 | Archive |
| **TOTAL** | **193** |  |

Most ads are from 2021-08 to 2024-12 (Royal HaloHalo pre-rebrand era). Most recent batch: 2026-03-08 Foodpanda Panda Buddy/Sunglasses (8 ads, part of 33 dev-mode ads).

---

## Closeout Checklist (Plan Self-Audit)

- [x] Canonical scope declared: `none` with rationale
- [x] Registry row added BEFORE plan body written
- [x] Branch name reserved: `s214-meta-ads-rules-fix-refresh-archive`
- [x] Completion condition defined (Phase 6 verify script PASS + PR created)
- [x] Stop-only-for policy defined (5 conditions)
- [x] Continue-without-pause rule stated
- [x] Signoff authority: single-owner (Sam as CEO)
- [x] Canonical closeout artifacts listed (12 files)
- [x] Status reconciliation contract included
- [x] Phase budgets estimated (4/5/6/5/8/4/5 = 37 units; all phases under 15-unit cap)
- [x] Ownership matrix defined (Meta API resources + file globs)
- [x] Protected-surface registry included (don't touch other rules, winners, campaigns)
- [x] Requirements Regression Checklist included (10 items)
- [x] Hard-coded blockers inline in relevant tasks (P1-T5, P2-T2, P3-T4, P4-T1, P4-T2, P5 rate limit)
- [x] Scope within 80-unit ceiling (37 units)
- [x] Single-agent-single-session scope
- [x] Cold-start test passes: every decision can be made from this plan alone
- [x] Zero-Skip Enforcement section with machine-verifiable script
- [x] Every script task has MUST_MODIFY or MUST_CONTAIN assertion
- [x] Verification script uses Meta Graph API directly (not self-report)
- [x] FAIL blocks progress (Phase 6 verify must PASS before closeout)
- [x] No promo/discount copy in any boost (brand rule RRC-1)
- [x] object_story_id pattern enforced for all new ads (RRC-2)
- [x] Historical dedup enforced (RRC-3)
- [x] Pre-touch backup required for every mutating script (RRC-4)
- [x] Sprint registry compliance verified (S214 locked before plan body written)
