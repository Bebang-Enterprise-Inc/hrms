# S258 Phase 2.0 + 2.4 + 2.5 + 2.6 + Phase 3 Cold-Start Handoff

> **For an agent entering Phase 2.0 (migration map + stub seeds) and onward from a
> fresh session.** Prior session completed Phases 0+1 fully (with 2 documented
> deferrals to Phase 3) and Phase 2 templates 2.1+2.2+2.3.

---

## Prior session status (2026-06-04)

| Phase | Subtask | Result |
|---|---|---|
| 0 | All | PASS (commit `8a66a0ecd`) |
| 1 | A1 — default_inventory_account on 43/44 | PASS (III deferred — D1-3) |
| 1 | A2 — L77 stock_received_but_not_billed | PASS |
| 1 | A3 — ROBDA + XMM round_off dedup | PASS (deviation D1-1: disable-don't-delete) |
| 1 | 1.3.5 BEI round_off canonicalization | DEFERRED (D1-2) → Phase 3c |
| 1 | A4 — extract canonical store template | PASS |
| 1 | A5 — BFI2 → BFT abbr rename | PASS (via SSM) |
| 1 | verify_phase1.py | PASS |
| 2 | 2.1 Head Office template | PASS (114 rows) |
| 2 | 2.2 Commissary template | PASS (113 rows) |
| 2 | 2.3 Franchisor template | PASS (115 rows) |

**Branch:** `s258-coa-gl-finalization-bridge-handoff` (pushed)
**Last commit:** Phase 2 templates commit (after `b80f47de6` Phase 1 commit)

## Critical constraint discovered (impacts all remaining Phase 2 + Phase 3 work)

**ERPNext root_company_validation cascade.** Creating accounts on a child Company
via REST API fails because ERPNext tries to cascade-create on all siblings, and any
sibling missing the parent_account chain fails. The `ignore_root_company_validation`
flag is server-side only — must be set via bench execute, NOT REST API.

**Affected:**
- D1-2 — 1.3.5 BEI round_off CREATE
- D1-3 — A1-on-III default_inventory_account CREATE
- 2.4 B1 — Seed BFC accounts (BFC has 0 accounts; child of BEI which is child of III)
- 2.5 B2 — Seed BFT accounts (0 accounts; child of BEI)
- 2.6 B3 — Seed 4 BEI-TIN stub stores (12 accounts each; children of BEI)
- 3a — Per-Company 5-root tree seed loop (designed for bench execute already — plan §3a.2)

**Resolution path:** Phase 3a runs FIRST and uses bench execute with the flag. Once
the canonical 5-root tree exists on all 58 Companies, the subsequent stub seeds
(2.4/2.5/2.6) can be done via the same bench-execute pattern using the seeded roots
as parents.

**Recommended re-ordering for next session:**
1. Phase 2.0 — Build BEI/BKI/III migration maps (READ-only Frappe queries, no cascade issue).
2. Phase 3a — Per-Company 5-root tree seed via SSM bench execute (the plan's own design).
3. Phase 1.3.5 retry, A1-on-III retry, 2.4 B1, 2.5 B2, 2.6 B3 — all via bench execute against the now-seeded roots.
4. Phase 3b — BKI rewrite using migration_map_BKI.csv.
5. Phase 3c — BEI rewrite using migration_map_BEI.csv (includes BEI round_off canonicalization absorbed here).
6. Phase 3.5 — BEI AP/AR suffix.
7. Phase 4 — 4000900 discount renumber (all 58).
8. Phase 5 — UPPER + drop number prefix (all 58).
9. Phase 6 — Bridge handoff package.
10. Phase 7 — Closeout + PR.

## Read-first sequence for fresh agent

```
1. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/docs/plans/2026-06-04-sprint-258-coa-gl-finalization-bridge-handoff.md  (full plan)
2. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/output/s258/PHASE_GATES.md  (running status)
3. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/output/s258/DEFECTS.md  (all D0-* and D1-* findings)
4. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/output/s258/baseline_state.json  (58 Companies)
5. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/data/_FINAL/COA_HEALTHY_REFERENCE.csv  (114-stem store template)
6. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/data/_FINAL/COA_TEMPLATE_*.csv  (Head Office + Commissary + Franchisor templates)
7. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/scripts/coa_fix/_lib.py  (REST API helpers)
8. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/scripts/coa_fix/A5_rename_bfi2_to_bft.py  (SSM bench-execute reference implementation)
9. F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff/scripts/verify_canonical_structure.py  (SSM pattern for Frappe v2 commands)
10. Plan §Phase 3 Cold-Start Handoff Prompt (line 770+) — the plan's own embedded handoff for Phase 3
```

## Cold-start prompt (copy verbatim to fresh session)

```
/execute-plan-bei-erp docs/plans/2026-06-04-sprint-258-coa-gl-finalization-bridge-handoff.md

You are continuing S258. Phase 0 + Phase 1 + Phase 2 templates COMPLETE.
Resume from Phase 2.0 (migration map build) via output/s258/PHASE2_3_HANDOFF.md.

Branch: s258-coa-gl-finalization-bridge-handoff
Worktree: F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff (already exists)
Last commit: see git log

Critical finding from prior session: ERPNext root_company_validation forces all
CREATE-on-child-Company operations through bench execute (SSM pattern). Plan
already designed Phase 3a around this. Re-order remaining work:
  2.0 migration map (read-only) →
  3a per-Company 5-root tree seed via SSM →
  1.3.5 + A1-III + 2.4 B1 + 2.5 B2 + 2.6 B3 batched via SSM (now that roots exist) →
  3b BKI rewrite →
  3c BEI rewrite (absorbs 1.3.5 BEI round_off canonicalization) →
  3.5 BEI suffix → 4 discount → 5 UPPER → 6 Bridge → 7 closeout.

Reference implementations:
  - scripts/coa_fix/A5_rename_bfi2_to_bft.py (SSM bench-execute pattern)
  - scripts/coa_fix/_lib.py (REST API helpers + submit_doc + account_exists fix)
  - scripts/coa_fix/A3_dedupe_round_off.py (JE pattern + disable-don't-delete deviation D1-1)

Then continue end-to-end through Phase 7 closeout (or split at the embedded Phase 3
Cold-Start Handoff Prompt in the plan if context budget runs short).
```

---

## Approximate remaining work-unit budget

| Phase | Subtasks remaining | Est wall-clock | SSM calls | REST calls |
|---|---|---|---|---|
| 2.0 | Migration map builder + 3 CSVs | 10 min | 0 | ~700 (queries) |
| 3a | 5-root tree seed on 58 Companies | 8 min | 1-3 | 0 |
| 1.3.5 + A1-III + 2.4 + 2.5 + 2.6 | Batched SSM seed | 15 min | 1-5 | 0 |
| 3b | BKI rewrite (~280 renames) | 20 min | 5-10 | 0 |
| 3c | BEI rewrite (~280 renames + 4 orphan reparent) | 25 min | 5-10 | 0 |
| 3.5 | BEI AP/AR suffix | 5 min | 1 | 0 |
| 4 | 4000900 renumber all 58 | 20 min | 1-2 | 0 |
| 5 | UPPER + drop prefix all 58 (~5500 renames) | 30 min | 5-10 | 0 |
| 6 | Bridge handoff package + Drive upload | 15 min | 0 | ~700 |
| 7 | Closeout + PR | 5 min | 0 | 0 |
| **Total remaining** | **~70u** | **~2.5 hr wall** | **~25 SSM** | **~1400 REST** |

Prior session done: ~30u (Phase 0 12u + Phase 1 10u + Phase 2 templates 3u + ~5u
overhead like probes/library setup).
