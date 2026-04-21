# S214 Verified Blockers — After 3-Agent Audit + Fact-Check

**Audit date:** 2026-04-21
**Sources:** `structural_findings.md`, `fact_check.md`, `code_verification.md`

## Severity Counts (Consolidated)

| Severity | Count | Source |
|---|:-:|---|
| CRITICAL (plan-breaking) | 0 | — |
| NEW GAP (fix before execution) | 3 | code_verifier |
| WARNING (correctness) | 5 | structural W1-W3 + fact-check PARTIAL×2 |
| INFO (nice-to-have) | 3 | structural I1-I3 |
| CONTRADICTED (out of scope) | 1 | fact-check CLAIM-16 (CLAUDE.md, not S214) |
| UNVERIFIABLE (no evidence) | 2 | fact-check CLAIM-9/11 |

**Overall verdict:** Plan is executable after applying 8 in-line amendments below. No critical structural problems. All 3 NEW GAPS are implementation-detail fixes that would have caused execution failures — fixing them pre-execution eliminates the risk.

---

## Amendments to Apply (in-line)

### A1 — [NEW GAP CV-7] Schedule format in P1-T5 is incorrect
**What the plan says:** `schedule = [{"start_minute": 840, "end_minute": 899}]`
**Correct Meta API format** (per `manage_meta_ad_rules.py` `daily_schedule()`):
```python
{
  "schedule_type": "CUSTOM",
  "schedule": [
    {"start_minute": 840, "end_minute": 899, "days": [d]}
    for d in range(7)
  ]
}
```
**Impact if not fixed:** API would reject the rule update, failing P1-T5.
**Fix:** Update the P1-T5 implementation note with the correct wrapper format.

### A2 — [NEW GAP CV-13] 2 of 3 reactivation campaign IDs unverified
**What the plan claims:** "every object ID in this plan is verified concrete as of 2026-04-21 09:45 AM PHT"
**Reality:**
- `120243460275370030` (Peak Season Community) — ✓ verified in SESSION_2026-04-04.md
- `120242888352350030` (Summer Buzz Awareness) — NOT in any saved file
- `120242888355100030` (Iskrambol Foodpanda Traffic) — NOT in any saved file
**Impact if not fixed:** Agent could post status change to wrong campaign ID if it's a typo.
**Fix:** Add a P3-T0 pre-verification task that queries Meta API for all 3 campaign IDs and fails fast if any don't exist or have unexpected objectives.

### A3 — [NEW GAP CV-2 + RRC-8] boost_replacements.py is a stub, not a template
**What the plan says:** Duplication Audit classifies `boost_replacements.py` as [EXTEND].
**Reality:** File prints "[ACTION REQUIRED]" and has no actual ad-creation API call. No `object_story_id` in the file. No `CREATE_NO_WINDOW` flag.
**Impact if not fixed:** Agent might copy the stub and produce a non-functional Phase 4 script.
**Fix:**
- Reclassify Phase 4 as [BUILD] (not [EXTEND])
- Point agent to `api-reference.md` Pattern 2 as the template
- Add explicit CREATE_NO_WINDOW requirement in the Phase 4 tasks (RRC-8)

### A4 — [W2 + CLAIM-13 PARTIAL] Ground-Truth Lock `unresolved_value_policy` lies
**What the plan says:** `unresolved_value_policy: None — every object ID in this plan is verified concrete as of 2026-04-21 09:45 AM PHT`
**Reality:** 9 of 16 loser ad IDs + 2 of 3 reactivation campaign IDs + 2-4 winner ad/adset IDs are runtime-resolved.
**Fix:** Update the `unresolved_value_policy` text to name the 4 runtime-resolved categories and say they are resolved at a specific task (P2-T1 for losers, P3-T0 for campaigns).

### A5 — [CLAIM-8 PARTIAL] Purchases count off by 1
**What the plan says:** "334 purchases"
**Reality:** 335 purchases in insights_7d.json
**Fix:** Update Appendix B and the 7-day scorecard section — 335 not 334.

### A6 — [CLAIM-10 PARTIAL] Evidence file list for PHP 27,800
**What the plan says:** `as_lal.json`, `as_bof.json`, `as_int.json` (3 files — these sum to PHP 26,000, not 27,800)
**Reality:** Correct total requires the 4 campaign-named files: `as_120225029875060030.json`, `as_120225480340900030.json`, `as_120225775497020030.json`, `as_120231023755930030.json`
**Fix:** Replace the 3 filenames in Ground-Truth Lock with the correct 4.

### A7 — [W3] Agent Boot Sequence step 2 silently stashes
**What the plan says:** "If not on `production`, run `git stash` first."
**Risk:** Could hide in-progress work silently.
**Fix:** Change to: "Check `git status`. If any uncommitted changes exist, STOP and ask user — do NOT stash silently."

### A8 — [W1] P0-T3 MUST_MODIFY uses prose count
**What the plan says:** `MUST_MODIFY: 3 new directories`
**Fix (cosmetic):** Change to explicit paths: `output/l3/s214/pre_state`, `output/l3/s214/post_state`, `output/l3/s214/state`

### A9 (INFO I1) — verify_s214.py should check PAUSED status for Phase 4 ads
**What's missing:** Verify script checks `object_story_id` but not `status==PAUSED`.
**Fix:** Add a PAUSED assertion to the verify template's Phase 4 block.

---

## Out-of-Scope Findings

### CLAUDE.md / MEMORY.md Employee count drift (not S214)
**What's wrong:** CLAUDE.md says "652 employees" in one place and "696" in another. Actual count in `data/_FINAL/EMPLOYEE_MASTER.csv` is 702.
**Action (separate):** Update CLAUDE.md + MEMORY.md to say 702. Not part of S214.

### meta_ads_audit.py uses v23.0 (everything else is v25.0)
**Action (separate):** Bump version in audit script. Not a S214 blocker.

---

## Claims That Remain UNVERIFIABLE (no on-disk evidence, not blockers)

1. **CLAIM-9:** April 20 hourly spend pattern (PHP 9,106 / PHP 865 / PHP 0). The query was live and not persisted. Plan narrative uses it as supporting evidence, not as a mutation input — acceptable. Agent can re-run the query if doubt arises.
2. **CLAIM-11:** Paused campaign objectives (OUTCOME_AWARENESS, OUTCOME_ENGAGEMENT, OUTCOME_TRAFFIC). The agent should re-query at P3-T0 (per A2 fix).
