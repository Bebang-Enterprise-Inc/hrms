# Structural Audit - S214 Meta Ads Plan

**Plan file:** `docs/plans/2026-04-21-sprint-214-meta-ads-rules-fix-refresh-archive.md`
**Audit date:** 2026-04-21
**Auditor:** Structural compliance agent (Sonnet 4.6)

---

## Summary
- CRITICAL blockers: 0
- WARNING: 3
- INFO: 3

---

## CRITICAL Blockers

None.

---

## WARNING

### W1 — S154: MUST_MODIFY assertion missing for P0-T3 (directory creation)
**Rule:** S154 Machine-Verifiable Phase Gates
**Location:** Phase 0, task P0-T3
The task creates 3 new directories. The MUST_MODIFY column says "3 new directories" (prose), not a filesystem assertion. The verification column correctly uses `ls -d ...` which is machine-verifiable. This passes the spirit of the rule, but the MUST_MODIFY cell should ideally name the artifact paths (as other tasks do with file paths), not the count. Minor inconsistency, not a blocker.
**Fix:** Change MUST_MODIFY from "3 new directories" to the 3 explicit paths: `output/l3/s214/pre_state`, `output/l3/s214/post_state`, `output/l3/s214/state`.

### W2 — S092 L3: verify_s214.py has placeholder stubs for 9 of 16 loser ad IDs
**Rule:** S092 L3 Scenario Contract / S028 Ground-Truth Lock
**Location:** Phase 2 task table (rows 9-16) and verify_s214.py template (`LOSER_IDS = [...]`)
Nine of the 16 loser ad IDs are listed as `*(to be looked up in P2-T1)*` rather than hardcoded concrete IDs. Similarly, the verification script template has `LOSER_IDS = [...]` as a placeholder. The plan instructs the agent to resolve them at P2-T1 runtime from `insights_7d.json`. The Ground-Truth Lock section says "every object ID in this plan is verified concrete as of 2026-04-21 09:45 AM PHT" (`unresolved_value_policy: None`). These two are in direct contradiction.
The 5 winner adset IDs are similarly partially unresolved (2 of 5 `*(to resolve)*` in the table, though Appendix A lists 2 concrete adset IDs with 2 more as `*(resolve)*`).
**Impact:** An agent cannot run P2-T3 (pause 16 losers) cold-start without the P2-T1 resolution step — meaning full cold-start self-containment (RRC-10, S091) is not achieved. The plan documents this as by-design (P2-T1 queries Meta to resolve), but the `unresolved_value_policy: None` claim is incorrect.
**Fix:** Either (a) pre-populate all 16 ad IDs from `insights_7d.json` before plan completion, or (b) change `unresolved_value_policy` to state: "9 of 16 loser ad IDs and 3 of 5 winner adset IDs are resolved at runtime in P2-T1 via Meta API lookup. This is intentional — IDs are verified at query time, not hardcoded."

### W3 — Agent Boot Sequence: step 2 says `git stash` but plan requires fresh branch from production
**Rule:** S099 Branch & PR Reservation Rule
**Location:** Agent Boot Sequence, step 2
Step 2 says "If not on `production`, run `git stash` first." This implies code could exist on a non-production branch at boot time. The correct safety-first language for autonomous agents is: verify no uncommitted changes exist (`git status`); if on a dirty branch, STOP and ask the user rather than silently stashing. `git stash` could hide pre-existing work. The create-branch step (step 3) correctly branches from `origin/production`.
**Fix:** Replace step 2 with: "Check `git status`. If any uncommitted changes exist on the current branch, STOP and ask user — do NOT stash silently. Once clean, proceed to step 3."

---

## INFO

### I1 — Phase 4 boost ads start PAUSED — this is intentional, but verify_s214.py checks effective_status
**Rule:** S154 Machine-Verifiable Phase Gates
**Location:** Phase 4 completion gate and verify_s214.py Phase 4 block
The plan deliberately creates new boost ads in `PAUSED` state (P4-T4, P4-T7) and states "User reviews + unpauses via PR comment." The verify_s214.py script checks `r.get("creative", {}).get("object_story_id") is not None` — it does NOT check `status==PAUSED`. However, the Phase 4 completion gate also asserts `effective_status==PAUSED` for all 3. The verify script should include a PAUSED assertion for Phase 4 ads to be complete. This is a script incompleteness, not a plan violation, but worth flagging so the agent doesn't miss it when writing P6-T1.
**Recommendation:** In P6-T1, add to verify_s214.py: `assert_(r.get("status") == "PAUSED", f"new ad {aid} starts PAUSED")` for the 3 boost ads.

### I2 — form_submissions.json entry-count delta math in P2-T6
**Rule:** S154 Machine-Verifiable Phase Gates
**Location:** Phase 2, task P2-T6
P2-T6 states "Entry count delta = 21 (16 pauses + 5 budget changes)." However, 5 budget changes are adset-level budget PATCHes, not ad-level mutations. Whether these count as single API calls (1 per adset) or ad+adset pairs depends on implementation. The delta of 21 is plausible (16 + 5) but the Verification column just says "Entry count delta = 21" without specifying how winner budget changes are counted. This could cause ambiguity if the agent logs per-API-call vs per-entity.
**Recommendation:** Clarify whether `api_mutations.json` entries are 1-per-call (16 POST ad pause + 5 POST adset budget) = 21, or whether pre-state fetches are also logged (then 32+). The current contract implies mutations-only (no reads in form_submissions.json).

### I3 — S097 Sentry exclusion is correctly classified
**Rule:** S097 Sentry Observability
**Location:** Plan scope
Confirmed: zero `@frappe.whitelist()` endpoints and zero bei-tasks API routes. All scripts are standalone Python hitting Meta Graph API. S097 is not applicable. Classification is correct.

---

## Rules Passed

| Rule | Result | Notes |
|---|---|---|
| **Canonical Gate** | PASS | `canonical_scope: none` declared with full rationale. Plan verified: no `tabCompany`/`tabWarehouse`/`tabCustomer`/`tabSupplier`, no SI/PO/MR/SE/JE/GL, no `hrms/api/` canonical files, no `resolve_store_buyer_entity`, no `scripts/canonical/`. Rationale cites write-plan-bei-erp decision table explicitly. |
| **S099 Branch & PR Reservation** | PASS (with W3 caveat) | `branch: s214-meta-ads-rules-fix-refresh-archive` in YAML. Boot Sequence step 3 has correct `git checkout -b s214-meta-ads-rules-fix-refresh-archive origin/production`. No direct-to-production pattern anywhere. P6-T6 creates PR against `production`. P6-T7 explicitly says STOP before merge. |
| **Sprint Registry Compliance** | PASS | S214 row exists in `SPRINT_REGISTRY.md` (line 313) with matching branch `s214-meta-ads-rules-fix-refresh-archive`. "Next Sprint Reservation" line 316 says `S215`. No collision found: no other plan file or branch uses `s214`. Registry row was added before plan body (confirmed by plan's own closeout checklist). |
| **S089 Requirements Regression Checklist** | PASS | 10-item RRC checklist present (RRC-1 through RRC-10). Covers brand rule, object_story_id, dedup, pre-touch backup, rule preservation, archive-not-delete, budget cap, Windows headless, Doppler, cold-start. HARD BLOCKER strings present inline in Phase 1 (P1 note), Phase 2 (P2 preamble), Phase 3 (P3-T4), Phase 4 (P4 preamble ×2), Phase 5 (P5 preamble). Scope 37 units << 80-unit ceiling. |
| **S091 Cold-Start Self-Containment** | PASS (with W2 caveat) | Design Rationale section present with subsections: Why this exists, Why this architecture, Why NOT switch Meta app, Why archive not delete, Known limitations, Sources. All decisions cite real file paths. 7 evidence files listed with real paths. Known limitations explicit (rate limits, spend recovery math, object_story_id constraints). RRC-10 cold-start test assertion present. 9 unresolved IDs are the W2 concern. |
| **S092 Sprint Closeout Contract** | PASS | Phase 6 exists (5 tasks). YAML has `status`, `completed_date`, `execution_summary`, `pr` fields. Registry update is in `completion_condition` and in P6-T5(e). `git add -f` is explicitly noted in P6-T5(b) and P6-T5(f) for plan/registry commits. `canonical_closeout_artifacts` lists 12 files. |
| **S027 Autonomous Execution Contract** | PASS | `completion_condition` defined (5 conditions including verify PASS, form_submissions, api_mutations, state_verification, PR created, plan COMPLETED, registry updated). `stop_only_for` defined (5 conditions). `continue_without_pause_through` stated. `blocker_policy` fully enumerated (5 modes). `signoff_authority: single-owner (Sam — CEO)`. |
| **S028 Ground-Truth Lock** | PASS (with W2 caveat re: `unresolved_value_policy`) | 7 evidence sources with real file paths. Count method documented for 4 metrics (losers, winners, viral posts, error ads) with jq-style query basis. Authoritative sections declared (Sections 1-12). Normalization policy for count drift defined. `unresolved_value_policy` claim is contradicted by W2. |
| **S029 Phase Budget** | PASS | Budgets: P0=4, P1=5, P2=6, P3=5, P4=8, P5=4, P6=5 = 37 total. Max phase is P4 at 8 units. All phases under both 12 (preferred) and 15 (hard limit). Hard limit confirmation is in the plan body. |
| **S154 Machine-Verifiable Phase Gates** | PASS (with W1 caveat) | Every task in every phase has a MUST_MODIFY or MUST_CONTAIN column. Verification column uses filesystem checks (`test -f`, `grep -c`, `jq 'length'`), git commands, or explicit Meta API re-query descriptions. `verify_s214.py` script is fully templated and queries Meta Graph API directly (6 assertion groups). Script uses `sys.exit(1)` on failure — not self-report. Zero-Skip Enforcement section prohibits self-report trap. Phase 6 verify must PASS before PR. W1 flags P0-T3's prose MUST_MODIFY. |
| **S092 L3 Scenario Contract** | PASS | No operator UI surfaces — classification as API-verification-only L3 is correct. `verify_s214.py` queries Meta live and checks 6 assertion groups (rule status, 16 losers, 5 winner budgets, 3 campaigns, 3 new ads, ≥190 archived). This is adequate for a non-UI Meta API sprint. I1 flags a minor gap in Phase 4 PAUSED assertion within the script. |
| **S097 Sentry Observability** | NOT APPLICABLE | No `@frappe.whitelist()` endpoints, no bei-tasks API routes. All deliverables are standalone Python scripts calling Meta Graph API. Exclusion correctly classified (see I3). |
| **S087 Anti-Rewind Protection** | PASS | Ownership matrix defined (`output/l3/s214/S214_SURFACE_OWNERSHIP_MATRIX.csv`). File globs: `Marketing/digital-marketing/scripts/s214_*.py`, `output/l3/s214/**`. External resources: 2 rule IDs + 16 ad IDs + 3 post IDs + 193 error-ad IDs. Protected surfaces named (don't touch non-loser active ads, 6 other rules, non-reactivation campaigns). Pre-touch backup specified per phase (P1-P5 each name their pre_state backup file). `active_run_coordination` artifact defined. Supersession map N/A. `touch_preservation` N/A (all new files). |
