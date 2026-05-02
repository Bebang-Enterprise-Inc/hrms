# S232 Zero-Skip Enforcement Audit (S154)

Plan path: `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`

Severity legend:
- **BLOCKER** — Phase verifier as written cannot detect a corrupt-success scenario; sprint will close with hidden defects.
- **HIGH** — verifier is filesystem-based but loose enough that an agent can pass it with partial work.
- **MEDIUM** — verifier asserts presence but not behavior.
- **NIT** — phrasing improvement only.

## Summary of blockers

| # | Severity | Gap |
|--:|----------|-----|
| 1 | **BLOCKER** | Phases 2-7 do NOT include the verifier source code template. Only Phase 1 has it (lines 343-374). The plan says the agent "will write actual scripts" but with no template the agent may emit prose checklists or skeleton scripts that pass trivially. |
| 2 | **BLOCKER** | Phase 6 verifier task 6.4 is just `MUST_MODIFY: scripts/s232_verify_phase6.py` with NO MUST_CONTAIN, NO assertion list, no description. Cold-start agent can write `print("PHASE 6 VERIFIER: PASS")` and pass it. |
| 3 | **HIGH** | Phase verifier failure-blocks-progress wording exists ONLY at end of Phase 1 ("If verifier fails, do NOT proceed to Phase 2. Fix and re-run." — line 376). Phases 2, 3, 4, 5, 6 have no equivalent statement. The Phase 7 task 7.1 says "Any FAIL halts here" but there's no per-phase gating during execution. |
| 4 | **HIGH** | 8 tasks have `MUST_MODIFY` but ZERO `MUST_CONTAIN`, meaning the agent can create an empty file and pass the verifier. Listed below. |
| 5 | **HIGH** | Task 6.2 has the explicit fallback "If audit finds zero direct queries: mark this task as N/A with explanation in PR description." This IS an authorized skip pattern, but the Zero-Skip section (line 530-534) FORBIDS "marking partial work as DONE" and "deferring to a future sprint without Sam approval". The N/A path needs to either be removed or explicitly allowed in the Zero-Skip exclusions. |

## Detail by audit item from prompt

### 7. Zero-Skip section — 6 forbidden patterns audit

Plan section starts at line 529. Quoting line 534:

> Forbidden: marking partial work as DONE; replacing a task with a simpler version; deferring to a future sprint without Sam approval; combining tasks and dropping features in the merge; implementing happy path only; commenting out failing assertions to make tests pass.

| Required forbidden pattern | Present? |
|---|---|
| Silent skipping | YES — "No silent skipping" line 531 |
| Marking partial as DONE | YES — line 534 |
| Replacing tasks with simpler versions | YES — "replacing a task with a simpler version" line 534 |
| Deferring to next sprint | YES — "deferring to a future sprint without Sam approval" line 534 |
| Combining tasks and dropping features | YES — "combining tasks and dropping features in the merge" line 534 |
| Happy-path-only | YES — "implementing happy path only" line 534 |

**All 6 are present. Bonus 7th pattern: "commenting out failing assertions to make tests pass." Good.**

**Verdict: PASS.** But the existence of an explicit "mark this task as N/A" instruction in Phase 6.2 partially undoes the "no skipping" rule (item 5 above).

### 8. MUST_MODIFY assertion coverage

Counting tasks that modify a specific file vs tasks with explicit `MUST_MODIFY: <file>`.

| Phase | # of file-modifying tasks | # with MUST_MODIFY: | Gap tasks (no MUST_MODIFY) |
|------:|---:|---:|---|
| 0 | 5 | 2 (0.4, 0.5) | 0.1, 0.2, 0.3 are reads/env-setup so OK. Net gap: 0. |
| 1 | 8 (1.1-1.7) | 8 | 0 |
| 2 | 7 (2.1-2.7) | 7 | 0 |
| 3 | 4 (3.1-3.4) | 4 | 0 |
| 4 | 3 (4.1-4.3) | 3 | 0 |
| 5 | 4 (5.1-5.4) | 4 | 0 |
| 6 | 4 (6.1-6.4) | 3 + one "TBD per audit" | 6.2/6.3 say "TBD per audit" — half-assertion |
| 7 | 6 (7.1-7.6) | 5 + 1 env-teardown | 7.6 (worktree cleanup) is env-only, OK |

**Total: 41 file-modifying task rows; ~38 have concrete MUST_MODIFY paths.** Phase 6 has 2 tasks where the file path is "TBD per audit" — a real gap because cold-start agent has nowhere to look. Otherwise excellent.

**Verdict: PASS with 1 HIGH (Phase 6 vagueness, item 5 in list above).**

### 9. MUST_CONTAIN assertion coverage

Counting tasks adding a visible feature vs tasks with explicit `MUST_CONTAIN: <string>`.

| Task | MUST_MODIFY | MUST_CONTAIN | Gap |
|------|-------------|--------------|-----|
| 0.4 | state_before.json | `synthetic_store_check: PASS` | OK |
| 0.5 | state_before.json | three field names | OK |
| 1.1 | 001_*.sql | YES | OK |
| 1.2 | 002_*.sql | YES | OK |
| 1.3 | 003_pos_orders_dedup_fields.sql | YES | OK |
| 1.4 | hrms/utils/pos_dedup.py | YES | OK |
| 1.5 | sync_pos_to_supabase.py | YES | OK |
| 1.5b | mosaic_webhook.py | YES | OK |
| 1.5c | 004_*.sql + .py + .py | YES (`short_order_id`) | OK |
| 1.6 | mosaic_webhook.py | YES | OK |
| 1.7 | s232_verify_phase1.py | YES | OK |
| 2.1 | 003_pos_products.sql | YES | OK |
| 2.2 | s232_seed_pos_products.py | YES | OK |
| 2.3 | POS_PRODUCT_CLASSIFICATION.csv | YES | OK |
| 2.4 | s232_apply_product_classification.py | **NONE** | **GAP** |
| 2.5 | sales_dashboard.py | YES | OK |
| 2.6 | sales_dashboard.py | YES | OK |
| 2.7 | s232_verify_phase2.py | **NONE** | **GAP** |
| 3.1 | timestamp_usage_audit.md | **NONE** | **GAP** |
| 3.2 | mosaic_webhook.py | YES | OK |
| 3.3 | test_mosaic_webhook_timestamps.py | YES | OK |
| 3.4 | s232_verify_phase3.py | **NONE** | **GAP** |
| 4.1 | mosaic_webhook.py | YES (rich list) | OK |
| 4.2 | 005_pos_order_payments_inferred.sql | YES | OK |
| 4.3 | s232_verify_phase4.py | YES | OK |
| 5.1 | s232_backfill_dupes.py | YES | OK |
| 5.2 | 005_views_filter_dupes.sql | YES | OK |
| 5.3 | s232_recount_cups.py | YES | OK |
| 5.4 | s232_verify_phase5.py | **NONE** | **GAP** |
| 6.1 | bei_tasks_cup_query_audit.md | **NONE** | **GAP** |
| 6.2 | (TBD) | **NONE** | **GAP (compound — already item 5)** |
| 6.3 | (TBD) | YES (`Methodology updated 2026-05-02`) | OK |
| 6.4 | s232_verify_phase6.py | **NONE** | **GAP (this is BLOCKER #2)** |
| 7.1 | s232_verify_all_phases.py | **NONE** | **GAP** |
| 7.2 | output/s232/l3/{json files} | **NONE** | **GAP — but L3 evidence is by structure not by string** |
| 7.3 | teardown_complete.json | **NONE** | **GAP** |
| 7.4 | vendor_outreach/...md | **NONE** | **GAP** |
| 7.5 | plan + registry | **NONE** | **GAP — but expected** |

**Tally:**
- 22 tasks have BOTH MUST_MODIFY + MUST_CONTAIN
- 13 tasks have MUST_MODIFY only (no MUST_CONTAIN)

**Of those 13 gaps:** 8 are "verifier scripts and audit markdown" where MUST_CONTAIN may be acceptable as N/A, but at minimum each verifier script should require `assert` and `PHASE N VERIFIER: PASS` strings. The other 5 are real gaps.

**Verdict: HIGH (item 4 above).** The 5 real gaps are: Task 2.4 (apply_product_classification.py), 6.1 (audit markdown — should require >0 entries), 6.4 (verify_phase6 — BLOCKER), 7.3 (teardown_complete.json — should require empty seeded data assertion), 7.4 (vendor_outreach.md — should require Issue 1/2/3 strings).

### 10. Phase verifier scripts are filesystem-based, not prose

Phase 1 has the full Python verifier template (lines 343-374). It does:
- `git diff --name-only origin/production` — file-based
- `assert f in diff_files` — file-based
- `if s not in open(f).read(): sys.exit(1)` — string-based
- exits non-zero on failure

**This is a strong filesystem-based verifier.** ✓

Phases 0, 2, 3, 4, 5, 6 all reference "Phase N verifier" with MUST_MODIFY: `scripts/s232_verify_phaseN.py` BUT only Phase 0 has even a minimal stub (lines 314-324). Phases 2-6 have ZERO verifier code template.

The agent is told "write actual scripts (not prose checklists)" implicitly via the Phase 1 template, but a cold-start agent without procedural discipline can write:

```python
# scripts/s232_verify_phase2.py
print("PHASE 2 VERIFIER: PASS")
```

…and the plan does not stop them. This is the corrupt-success risk MEMORY lesson #25 warns about.

**Verdict: BLOCKER (item 1 above).** Each of phases 2-6 should either:
1. include a stub verifier showing required assertions, OR
2. point to the Phase 1 template and say "use the same shape — file-list grep + git-diff + assertion".

Phase 1 verifier template is good but is not declared as the canonical template for downstream phases. The plan must say so explicitly.

### 11. Phase verifier runs FAIL-blocks-progress

Searched plan for "do NOT proceed" / "halts here" / "stop":

| Phase | Statement |
|------|-----------|
| 0 | None explicitly. |
| 1 | "If verifier fails, do NOT proceed to Phase 2. Fix and re-run." (line 376) ✓ |
| 2 | None. |
| 3 | None. |
| 4 | None. |
| 5 | None. |
| 6 | None. |
| 7 | Task 7.1: "`python scripts/s232_verify_all_phases.py` runs Phase 0-6 verifiers in order. Any FAIL halts here." (line 443) ✓ |

So failure blocking exists at the BOOKEND verifier step (7.1) and the phase-1 boundary, but NOT at Phase 2→3, 3→4, 4→5, 5→6, 6→7 boundaries.

This means a cold-start agent could let Phase 2 verifier fail, push through Phases 3, 4, 5, 6 with bad assumptions, and only discover at 7.1 that everything was off. The fix-and-re-run cost would be cheaper if every phase had the explicit gate.

**Verdict: HIGH (item 3).** Need a note at the bottom of every phase: "If Phase N verifier fails, do NOT proceed to Phase N+1. Fix and re-run."

## Total zero-skip blockers: **2 BLOCKERs, 4 HIGHs**

The 2 BLOCKERs are: (1) verifier templates absent for Phases 2-6, (2) Phase 6.4 verifier with NO MUST_CONTAIN allowing trivial pass.

## Combined view

This plan is unusually well-structured for cold-start (it cites the right line numbers, includes explicit DDL, declares MUST_MODIFY consistently). The corrupt-success risks live almost entirely in the verifier layer — Phases 2-6 don't show their work. A small edit pass adding verifier templates for each phase would push the plan from "execution-ready with caveats" to "execution-ready".
