# S258 — Running Summary

**Status:** IN-PROGRESS — Phases 0 + 1 + 2 (templates) DONE; Phase 2.0 migration map + Phase 2.4/2.5/2.6 stub seeds + Phases 3-7 PENDING.

**Branch:** `s258-coa-gl-finalization-bridge-handoff` (pushed to origin)
**Worktree:** `F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff`
**Base SHA:** `94443fa79` (origin/production)

## Commits on branch

1. `8a66a0ecd` — `feat(S258 P0): Boot + Preflight + Audit + Canonical DECISIONS.md ratification`
2. `84635b8ad` — `feat(S258 P1 partial): A4 template extract + probes + scripts library + Phase 1 handoff`
3. `b80f47de6` — `feat(S258 P1): Safe sync — A1+A2+A3+A4+A5 LIVE PASS; 1.3.5 + A1-on-III deferred`
4. (this commit, pending) — `feat(S258 P2 partial): 3 NEW canonical templates + Phase 2.0/3 handoff`

## What's done

### Phase 0 — Boot + Preflight + Audit (12u, PASS)

- Worktree spawned from origin/production (SHA 94443fa79).
- Canonical preflight: 49 stores, 0 violations.
- 20 cleanroom COA-175-001..020 transcribed into `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` (canonical 6-column table format; gate adjusted from ≥23 to ≥20 — D0-1).
- Live state audit with GL counts: HEALTHY=6, PARTIAL=46, MINIMAL=4, MISSING=2 (matches plan exactly). III=338 accts/**0 GL** (D0-2 — true zero-GL holdco, v1.1 over-corrected).
- Baseline evidence + provision status + abbr inconsistency audit + active-run claim + protected surface registry (4 VERIFIED, 1 REMOVED-STALE) all written.
- `verify_phase0.py` PASS.

### Phase 1 — Safe Sync (10u, 5 of 6 subtasks PASS; 2 individual targets deferred)

- **A1 PASS 43/44** — `Stock In Hand - <ABBR>` SET on 43 PARTIAL Companies (existed pre-Phase 1). III deferred (D1-3 — root cascade).
- **A2 PASS** — L77 `stock_received_but_not_billed` set.
- **A3 PASS (with deviation D1-1)** — ROBDA + XMM round_off pointers canonicalized; ROBDA JE `ACC-JV-2026-00014` (0.80 PHP transfer); both legacy Liability dupes SET disabled=1. Deviation: followed canonical Rule 2 disable-don't-delete instead of plan v1.2 P0-3 DELETE-with-ignore_links.
- **A4 PASS** — `data/_FINAL/COA_HEALTHY_REFERENCE.csv` (114 stems, 82 in all 6 HEALTHY).
- **A5 PASS** — `BEBANG FT INC.` abbr BFI2 → BFT via SSM bench execute; SEC tax_id preserved; 2 Cost Centers renamed.
- **1.3.5 DEFERRED (D1-2)** → Phase 3c. REST API blocked by root_company_validation.
- `verify_phase1.py` PASS.

### Phase 2 — Templates (partial, 3u of 15u)

- **2.1 Head Office template PASS** — `data/_FINAL/COA_TEMPLATE_HEAD_OFFICE.csv` (114 rows).
- **2.2 Commissary template PASS** — `data/_FINAL/COA_TEMPLATE_COMMISSARY.csv` (113 rows).
- **2.3 Franchisor template PASS** — `data/_FINAL/COA_TEMPLATE_FRANCHISOR.csv` (115 rows).
- **2.0 migration map PENDING** — handoff doc PHASE2_3_HANDOFF.md
- **2.4 B1 seed BFC, 2.5 B2 seed BFT, 2.6 B3 seed 4 stubs PENDING** — all require SSM bench execute (root_company_validation constraint).

## Critical constraint surfaced

ERPNext root_company_validation forces ALL CREATE-on-child-Company through bench
execute (SSM). REST API insufficient for: 1.3.5 BEI round_off, A1-III, 2.4 BFC,
2.5 BFT, 2.6 stubs, Phase 3a 5-root seed. The plan already designed Phase 3a around
this. Recommended re-ordering: 2.0 (read-only) → 3a (5-root seed via SSM) → re-run
deferred CREATE attempts under canonical roots → 3b → 3c → … See PHASE2_3_HANDOFF.md.

## Key findings (DEFECTS.md)

- **D0-1**: Cleanroom has 20 COA-175 rows (not 23). Gate adjusted.
- **D0-2**: III gl_entry_count = 0 (v1.0 was correct; v1.1 over-corrected). III IS a true zero-GL holdco.
- **D0-3**: BFC + BFT first_provision_done=0. Phase 2/3 scripts must set `frappe.flags.in_migrate=True`.
- **D0-4**: Abbr inconsistency audit = 0 issues; BFI2→BFT is semantic rename.
- **D0-5**: S238 surface stale (origin/production base).
- **D1-1**: A3 deviation — followed canonical Rule 2 (disable-don't-delete) instead of plan's DELETE-with-ignore_links.
- **D1-2**: 1.3.5 BEI round_off DEFERRED → Phase 3c (REST API cannot bypass `ignore_root_company_validation`).
- **D1-3**: A1-on-III DEFERRED → Phase 3a (same root-cascade constraint).
- **D1-4**: A5 first run had `ignore_permissions` kwarg issue on `rename_doc("Cost Center", ...)` — fixed on retry.
- **D1-5**: A3 first run — `frappe.client.submit` REST endpoint expects form-encoded `doc` — added `submit_doc()` helper to `_lib.py`.

## Next session

Read `output/s258/PHASE2_3_HANDOFF.md` and resume from Phase 2.0 migration map.
Plan's own embedded `Phase 3 Cold-Start Handoff Prompt` (line ~770) covers Phase 3
onward in detail; PHASE2_3_HANDOFF.md handles the Phase 2 → 3 bridge.
