---
sprint: S196
display: Sprint 196 — Store-First Naming + Data Migration + Delivery Schedule Grid Fix (Audit v3)
branch: s196-store-first-naming-and-migration
branch_v2_note: "Renamed from s195-store-universe-company-ssot at start of Phase 5 (W-7). Before rename, branch had zero commits on top of origin/production."
repo: hrms
status: COMPLETED
created: 2026-04-15
audit_v3_date: 2026-04-15
audit_v3_summary: |
  5-agent audit (frappe-backend + deployment-qa + system-arch + design-review + governance) identified 7 CRITICAL + 12 WARNING gaps. All applied below — nothing deferred, nothing removed. Unit budget 59 → 73 (still ≤ 80). See "Audit v3 Amendments" section for traceability; authoritative phase tables below updated in same edit per S028 normalization rule.
completed_date: 2026-04-16
backend_pr: hrms#585
followup_prs:
  - hrms#588 — SJDM attribution fix (JL Trade OPC store-first + Legacy77 archive)
  - hrms#590 — Data hygiene (Items #2 + #3): delete 3 archived BEBANG Companies + rename 35 legacy `- BEI` warehouses to store-first + fixture regeneration
execution_summary: |
  Phase 1 code prep (26 hardcoded refs + normalizer regex), Phase 2 LIVE data migration via SSM (12 Co renames + 5 wh renames + 3 new Co + 4 wh re-points w/ SLE+GL backfill + 3 Co archive + 5 wh deletes), Phase 3 helpers + get_weekly_schedule rewire, Phase 4 tests (12 unit + 5 integration) — all shipped in PR hrms#585. Final grid count: 7 → 49 orderable warehouses verified via Step J. Follow-ups: PR hrms#588 fixed SJDM attribution (JL Trade OPC is real operator, renamed store-first, Legacy77 archived); PR hrms#590 completed Items #2 + #3 (migrated 3 Customer rows, cascade-deleted 327 Accounts + 6 Cost Centers + 15 Warehouses, deleted 3 archived BEBANG Companies; renamed 35 legacy `- BEI` warehouses; regenerated 2 fixtures). Final verified state: 50 orderable Companies / 50 orderable warehouses / 0 `- BEI` non-BEI leaf warehouses remaining. SHFC restructure remains DEFERRED pending SM San Pablo BIR registration.
depends_on:
  - S181 (Company Master Extension — DEPLOYED, custom fields exist)
  - S188 (Per-Store Company Restructure — DEPLOYED)
  - S190 (Store-Company Integration — DEPLOYED)
supersedes: S195
registry_row: |
  | `S196` | Sprint 196 | `s196-store-first-naming-and-data-migration` (hrms) | hrms#TBD | PLANNED 2026-04-15 — Supersedes S195. Store-First Company Naming + Complete Data Migration + Delivery Schedule Grid Fix. [...] | `docs/plans/2026-04-15-sprint-196-store-first-naming-and-data-migration.md` |
branch_note: |
  Branch `s195-store-universe-company-ssot` (reserved by S195) is reused because the first SSM data round (2026-04-15: 10 deletes, 2 creates, BEI relabel, Sweet Harmony Comment) already landed on it and is preserved as predecessor work. No PR has been created yet — the branch is clean and ready for S196 commits.
---

# Sprint 196 — Store-First Naming + Data Migration + Delivery Schedule Grid Fix

## Audit v3 Amendments — 2026-04-15

Audit via `/audit-plan-bei-erp` (5 agents: frappe-backend, deployment-qa, system-arch, design-review, governance). **Every CRITICAL and WARNING below was applied to the authoritative phase tables in the same edit — nothing deferred, nothing removed.** This table is traceability only; execute from the phase tables.

### CRITICAL (7) — all applied

| # | Finding | Applied to |
|---|---|---|
| CR-1 | `set_value("Warehouse","company",...)` does NOT cascade to `tabStock Ledger Entry.company` or `tabGL Entry.company` denormalized rows. 4 re-pointed warehouses × 500+ SLE each = ~2000+ rows silently stale. | Phase 2 new task **P2-T8** (SLE + GL Entry back-fill SQL per re-point). Phase 4 new test **P4-T6** (SLE continuity). |
| CR-2 | `Company.abbr` preservation across `rename_doc` not addressed. Accounts named `<name> - <abbr>` — abbr collision breaks COA silently. | Phase 2 new task **P2-T9** (abbr invariance check + collision guard). Phase 4 new test **P4-T7** (Account naming preservation). |
| CR-3 | `bench backup` not feasible via current SSM dispatcher (dispatcher runs python directly, never invokes bench CLI). Pre-Phase-2 backup would silently no-op. | Phase 2 new task **P2-T0** (explicit `docker exec $BACKEND bench --site hq.bebang.ph backup` as FIRST action, path captured to `output/s196/state/PRE_PHASE_2_BACKUP.txt`; abort if backup fails). |
| CR-4 | `frappe.db.savepoint()` missing around multi-doc operations — violates DM-2. "Commit per rename" leaves partial state on mid-stream failure. | Phase 2 all steps (A–H) reworded to wrap each logical unit in `frappe.db.savepoint(name)` with `rollback_to_savepoint` on failure. |
| CR-5 | `auto_provision_company` hook at `hrms/overrides/company.py:592-708` fires on Company insert, creates ~40 DocType side-effect rows per Company (warehouse, cost center, 27-account COA, BKI Customer, 2 bank accounts, ADMS, GPS). 3 new Companies × 40 = 120 unaccounted rows. | Phase 2 Step C reworded: insert new Companies with `first_provision_done=1` to suppress hook + document which fields must be populated manually. |
| CR-6 | `_normalize_store_name_for_route` at `store.py:1503-1512` strips only `- BEI`, `- BKI`, `- Bebang Enterprise Inc.`, `- Bebang Kitchen Inc.` suffixes. Auto-provisioned warehouses from CR-5 / renamed warehouses in Step B introduce new patterns (e.g., `- TC-SMC`, `- BPI`, `- BBEFC`, middle `- Tungsten Capital -`). Route map misses → S192 OOS regression. | Phase 1 new task **P1-T7** (normalizer handles all post-migration patterns). Phase 4 new test **P4-T8** (normalizer matrix). |
| CR-7 | `operational_status` NULL-pass-through filter admits misconfigured Companies to grid. | Phase 3 T1 filter changed from `not in ("Permanently Closed",)` to allowlist `in ("Active", "Pre-Opening", "Temporarily Closed", "Pipeline")`. NULL excluded. |

### WARNING (12) — all applied

| # | Finding | Applied to |
|---|---|---|
| W-1 | No `CONFIRM=yes` / `--dry-run` gate on destructive SSM. | Phase 2 T1 script skeleton now requires `CONFIRM=yes` env + supports `--dry-run` flag that prints planned actions without executing. |
| W-2 | Rollback script `scripts/s196_data_rollback.py` referenced but not a phase deliverable. | Phase 2 new task **P2-T2.5** writes the rollback script before any destructive operation runs. |
| W-3 | Phase 0 delete-blocker audit scope under-specified (missed Cost Centers, Accounts, Customers, Bank Accounts, Employees). | Phase 2 new task **P2-T5.5** (pre-delete SQL count per link-type per to-delete Company; abort if any > 0). |
| W-4 | No user-communication plan for Frappe Desk bookmark breakage. | Phase 6 new task **P6-T5** (post Google Chat announcement to finance + SCM channels; template in task body). |
| W-5 | `_NON_STORE_ENTITIES` vs `entity_category` drift risk. | Phase 3 T1 adds `meta.has_field`-style assertion: every key in `_NON_STORE_ENTITIES` must have `entity_category != Store/Commissary` or `frappe.log_error` + raise. Phase 4 new test **P4-T9**. |
| W-6 | Legacy `- BEI` suffix warehouses (Vista Mall Taguig, SM Taytay, SM Clark) owned by non-BEI corps — deferred as "cosmetic" but tie-break sort stability affected. | Scope updated: Phase 2 new task **P2-T2.7** (rename 3 legacy warehouses to store-first `<Store> - <NewCorp>` pattern) + reserved follow-up sprint marker in `SPRINT_REGISTRY.md` for "- BEI" cleanup across remaining 30+ warehouses. |
| W-7 | Branch hygiene — reusing S195 branch is justified but ambiguous. | Phase 5 T1 adds git branch rename: `git branch -m s195-store-universe-company-ssot s196-store-first-naming-and-migration` before push. YAML `branch` updated to `s196-store-first-naming-and-migration` below. Registry row prose already matches this. |
| W-8 | P1-T1 wording "DELETE 3 + ADD 3" is ambiguous — keys are stable S037 store_name strings. | P1-T1 reworded to "UPDATE 15 `_STORE_TO_CHILD` values (12 renames + 3 pointing to replacement Companies)". |
| W-9 | Missing tests: SLE continuity, Account naming, auto-provision suppression, normalizer matrix, grep-gate as CI-runnable Python. | Phase 4 expanded to 15 tests (added P4-T6 through P4-T10 — all five missing cases). |
| W-10 | Rollback DB backup downtime not quantified. | Rollback Contract updated with "Downtime window: 10–30 min; scheduled maintenance announcement required". |
| W-11 | `SPRINT_REGISTRY.md` S196 row prose mentions `s196-store-first-naming-and-data-migration` but YAML says `s195-store-universe-company-ssot`. | W-7 branch rename resolves this — YAML and registry now align. |
| W-12 | Sweet Harmony SHFC restructure tracked only in Frappe Comment `n6gqgqltuq` — not searchable outside timeline. | New sprint reservation: Phase 6 T6 reserves `SPRINT_REGISTRY.md` DEFERRED row "SHFC restructure — triggered by SM San Pablo BIR registration". |

### Unit budget adjustment

- Original: 59 units across 6 phases
- Audit v3 additions: +14 units (P1 +3, P2 +7, P4 +3, P6 +1)
- **New total: 73 units** (still ≤ 80 ceiling)

### Authoritative surface re-numbering

Since Audit v3 adds new tasks (P1-T7, P2-T0 / T2.5 / T2.7 / T5.5 / T8 / T9, P4-T6 through T10, P6-T5 / T6), the numbering below uses decimal suffixes to preserve the original Audit v2 numbering. Where sequence matters, tasks run in numerical order; e.g., P2-T0 runs first, P2-T2.5 runs between T2 and T3.

## TL;DR

The Delivery Schedule grid on `my.bebang.ph/dashboard/scm/delivery-schedule` shows only 7 of 47+ stores because `get_weekly_schedule` in `hrms/api/store.py:6850` filters by a stale hardcoded `company in ["Bebang Enterprise Inc.", "Bebang Kitchen Inc."]`. After S188 created per-store child Companies and S190 re-pointed warehouses, most store warehouses are now owned by 56 franchise/SPV Companies — all excluded by the stale filter.

This sprint delivers a **single consolidated fix** — data + code — that:
1. Renames 12 existing per-store child Companies from `<Corp> - <Store>` to `<Store> - <Corp>` (CEO directive: operators recognize store names, not corp names)
2. Creates 3 new correctly-named per-store children for stores whose ownership was mispointed (Galleria South, SM Caloocan, SM Sangandaan)
3. Re-points 4 warehouses owned by Holding Company parents back to their correct per-store children (all 4 have 500+ SLE — re-point only, never delete)
4. Renames 2 warehouses from corp-first to store-first
5. Deletes 3 cryptic auto-provisioned duplicate warehouses
6. Deletes 3 misnamed legacy `BEBANG <STORE>` Companies + 1 stale Company (JL TRADE OPC)
7. Fixes 26 hardcoded Company-name references across 3 Python files + 2 CSV fixtures + 1 E2E test (so Frappe's rename cascade doesn't leave broken links)
8. Adds `get_orderable_companies()` + `get_orderable_store_warehouses()` helpers reading from Company DocType as SSOT
9. Rewires `get_weekly_schedule` + `get_day_summary` to use the new helpers
10. Ships PR → Sam merges → post-deploy validation confirms grid shows 47 stores

**Naming convention locked (2026-04-15):**
- **Company docname:** `<Store> - <Corp>` (operator-facing). Invoice print format reverses to `<Corp> - <Store>` later (out of scope).
- **Warehouse name:** `<Store> - <Abbr>` (already mostly correct).

## Predecessor work already executed on this branch (2026-04-15, SSM round 1)

Do **not** re-run these — they are already live on production:

| Action | Count | Detail |
|---|---|---|
| Warehouses deleted | 10 | SM Megamall/Manila/Antipolo/Southmall legacies, Sta. Lucia, Robinson Gen Trias, Robinson Imus, Estancia, Megaworld Paseo Center, SM San Pablo (all `- BEI` suffix, all on BEI parent) |
| Warehouses created | 2 | `BB ESTANCIA FOOD CORP. - Ortigas Estancia - BBEFC`, `BEBANG PASEO INC. - Paseo Center - BPI` (NOTE: corp-first; must be renamed in Phase 2 of this sprint) |
| Company field updated | 1 | `Bebang Enterprise Inc.` entity_category `Store` → `Head Office` |
| Frappe Comment added | 1 | `n6gqgqltuq` on `SWEET HARMONY FOOD CORP.` recording SM San Pablo pre-BIR-registration context |

**Baseline verification:**
- `output/s195/state/baseline_get_weekly_schedule_BEFORE.json` — confirmed 7 stores on production API before first round
- `output/s195/state/PRETOUCH_BACKUP.json` — captures production SHA at session start (`01d8556c845ddb4f4d91433fb0b5fd00366ad639`)
- `output/s195/diagnostics/store_entity_mapping.json` — team workbook extraction (49 stores)
- `output/s195/diagnostics/superadmin_stores.json` — Superadmin API (48 live stores)
- `output/s195/diagnostics/company_register.json` — team workbook company register

## Design Rationale (For Cold-Start Agents)

### Why this exists

1. **2026-04-14 incident:** CEO opened Delivery Schedule, saw 7 stores. Expected 47+. The stale `company in [BEI, BKI]` filter at `hrms/api/store.py:6850` predates S188.
2. **2026-04-15 scope expansion (CEO directive):** "Operators are the store; they do not know the fucking corp names." Company docnames must be STORE-FIRST so the operator picking an ordering account sees their store. Billing prints reverse (corp-first) via print-format — separate sprint.
3. **Data hygiene gap found during Phase 0:** 12 existing per-store child Companies (from S188) use corp-first. 3 legacy Companies (`BEBANG ROBINSONS GALLERIA SOUTH`, `BEBANG SM CALOOCAN`, `BEBANG SM SANGANDAAN`) have a store name masquerading as a corp name (with wrong "BEBANG" prefix — not their actual corp). 4 warehouses never got re-pointed from Holding Company parents during S190 P5. 3 cryptic auto-provisioned duplicates exist. 1 stale Company (JL TRADE OPC, abbr BSS2) has 0 transactions and no matching store.

### Why this architecture (Company DocType as SSOT, store-first docname)

**Alternatives considered:**

| Option | Rejected because |
|---|---|
| Create a new `BEI Store` DocType separate from Company | Creates a silo S190 just eliminated. User directive: "let go of all CSVs and hard code everything in Frappe doctypes" — Company DocType with S181 custom fields IS the store master. |
| Keep corp-first Company naming | Operators don't know corp names; "Bebang Enterprise Inc. - SM Manila" confuses them vs "SM Manila - Bebang Enterprise Inc." |
| Delete the 4 warehouses on Holding Company parents | They have 500+ SLE each. Destructive. Re-point is safe (Frappe cascades). |
| Restructure ALL single-store corps (TRICERN, DAY ONES, RED TALDAWA, etc.) into parent+child with store-first naming | Scope creep. Single-store corps have no ambiguity — TRICERN = Vista Mall Taguig. Leave alone; future sprint if needed. |

**Selected:** Company DocType with store-first docname for per-store child Companies; helper reads `entity_category in (Store, Commissary)` + `operational_status != Permanently Closed`; Warehouses re-pointed to the correct per-store child; invoices use print-format reversal for corp-first display.

### Key trade-off decisions

1. **`operational_status` filter excludes only `Permanently Closed`.** Active / Pre-Opening / Temporarily Closed / Pipeline all appear. "Archived" is NOT a valid Select option — don't use it. (Source: `hrms/fixtures/custom_field.json:961-991`.)
2. **Tie-break for multi-warehouse Companies.** Rare post-migration (shouldn't happen after Phase 2 cleanup), but helper implements locale-pinned `sorted(key=lambda w: (route_map_membership, w["name"]))` for determinism.
3. **Phase 1 code prep before Phase 2 rename cascade.** Frappe's `rename_doc` cascades FK references (GL Entry, SLE, Warehouse, Account, Material Request) but NOT hardcoded Python strings or CSV fixtures. Fix strings first.
4. **All 12 existing per-store children are renamed, not just some.** Inconsistency would be worse than rename risk. All 12 have 0 GL Entries per Phase 0 audit.
5. **JL TRADE OPC deleted as stale.** Abbr BSS2 looks like duplicate of BEBANG SM SANGANDAAN (BSS). 0 transactions. Not in team sheet (49 stores) or Superadmin API (48 stores). If Sam identifies it later, recreate under proper naming.
6. **Sweet Harmony Food Corp not restructured.** SM San Pablo is not BIR-registered or operational. Captured in Frappe Comment `n6gqgqltuq`. When SM San Pablo opens, follow S188 playbook to restructure SHFC as is_group=1 parent with per-store children.

### Known limitations and mitigations

| Limitation | Mitigation |
|---|---|
| Frappe `rename_doc` may fail midway if ORM validates on a Link target | Each rename wrapped in try/except + `frappe.db.commit()`; SSM output logs which rename failed for surgical retry |
| Re-pointing a warehouse with 500+ SLE may trigger Bin revaluation | Re-point is `Warehouse.company` field change only (not warehouse name). SLE carries `company` but Frappe cascades via standard Link behavior. Verify by counting SLE before/after on one warehouse first |
| Operators using Frappe Desk might have cached old Company names in filters | Acceptable — clear Desk cache after migration. my.bebang.ph uses fresh API calls |
| `_STORE_TO_CHILD` map changes must match runtime Company names exactly | Phase 1 grep gate catches mismatches before Phase 2 runs |
| The 2 warehouses created in round 1 with corp-first names can't be cleanly deleted + recreated (ordering/inventory may start on them before Phase 2) | Phase 2 renames them via `frappe.rename_doc("Warehouse", ...)` — preserves any data already written to them |
| SM San Pablo branch tax info (partners, TIN status) lives only in Frappe Comment `n6gqgqltuq` | Comment is persistent in Frappe timeline, searchable, user-attributed. Acceptable until BIR registration triggers proper Company records |

### Source references

- `hrms/api/store.py:6782-6902` — `get_weekly_schedule` (target of fix)
- `hrms/api/store.py:6850` — the stale filter
- `hrms/api/store.py:1763-1790` — `_is_orderable_store` (correct, preserve)
- `hrms/api/store.py:1436-1500` — `_CENTRAL_WAREHOUSE_ROUTE_MAP`
- `hrms/api/store.py:1503-1512` — `_normalize_store_name_for_route`
- `hrms/api/company_master.py:503-513` — `_NON_STORE_ENTITIES`
- `hrms/api/company_master.py:592-609` — `_STORE_TO_CHILD` (to be updated in Phase 1)
- `hrms/api/company_master.py:1143-1147` — `populate_s181_fields` pre-seed map
- `hrms/api/company_master.py:1667-1676` — accounting_rule_cache lookup
- `hrms/fixtures/custom_field.json:961-991` — valid Select options for `entity_category` + `operational_status`
- `hrms/fixtures/sales_dashboard_store_mapping.csv` — hardcoded company strings
- `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv` — warehouse_docname references
- `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx:193-222` — frontend (read-only — HARD BLOCKER, do not modify)
- `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts:36` — E2E test hardcoded company
- `docs/plans/2026-04-14-sprint-195-store-universe-company-ssot.md` — superseded predecessor plan (read for S195 audit v2 context)
- `output/s195/plan_phase1_state_inventory.md` — Phase 0 inventory artifact from exploration
- `output/s195/plan_phase1_code_impact.md` — Phase 0 code-impact artifact

## Requirements Regression Checklist

Before opening the PR, the executing agent must verify every item:

- [ ] Phase 1 code prep complete: all 26 hardcoded Company-name references updated (3 maps in `company_master.py`, 2 CSV fixtures, 1 E2E test)
- [ ] Phase 2 SSM ran cleanly: 12 Companies renamed, 3 created, 4 re-pointed, 2 warehouses renamed, 3 duplicate warehouses deleted, 3 legacy Companies deleted, 1 stale Company deleted, BEI relabel preserved from round 1
- [ ] Phase 3 helpers added: `get_orderable_companies` + `get_orderable_store_warehouses` in `hrms/api/company_master.py` with defensive `meta.has_field` + G1 empty-list short-circuit + G3 locale-pinned deterministic sort
- [ ] Phase 3 `get_weekly_schedule` rewired: stale `company in [BEI, BKI]` filter gone; uses new helper; Sentry context `module=scm` preserved; SCM permission gate preserved
- [ ] Phase 3 `get_day_summary` audited (rewire if it has same stale filter, document if not)
- [ ] Phase 4 unit tests pass: 11 cases in `hrms/tests/test_s196_orderable_companies.py`
- [ ] Phase 4 integration test passes: `hrms/tests/test_s196_get_weekly_schedule.py` asserts len(store_meta) >= 47, `Shaw BLVD - BKI` present, no Head Office warehouse present
- [ ] Phase 4 `verify_s196.py` exits 0 with all MUST_MODIFY + MUST_CONTAIN + MUST_NOT_CONTAIN assertions passing
- [ ] Phase 5 post-deploy curl: `get_weekly_schedule` returns `len(store_meta) >= 47`
- [ ] Phase 5 negative test: Head Office warehouses (`BGC CAPITAL HOUSE`, `BRITTANY OFFICE`) NOT in store_meta
- [ ] Phase 5 Sentry: `transaction:hrms.api.store.get_weekly_schedule` tagged `module=scm`
- [ ] Phase 6 closeout: plan YAML + SPRINT_REGISTRY.md updated to COMPLETED; L3 handoff prompt generated for separate session

**Audit v3 additions (must also pass):**

- [ ] **(CR-1)** For every re-pointed warehouse: `SLE.company == Warehouse.company` for 100% of rows (run P4-T6 SLE continuity test)
- [ ] **(CR-2)** All 12 renamed Companies preserved their `abbr` field (P2-T9 abbr invariance); sample Accounts still resolve (P4-T7)
- [ ] **(CR-3)** `output/s196/state/PRE_PHASE_2_BACKUP.txt` exists with valid backup path; backup file accessible on EC2
- [ ] **(CR-4)** Every Phase 2 script operation is wrapped in `frappe.db.savepoint()` — grep `scripts/s196_data_migration.py` for `savepoint` returns at least one hit per logical step (rename, re-point+backfill, delete)
- [ ] **(CR-5)** 3 new Companies inserted with `first_provision_done=1`; no auto-provisioned template warehouses appeared under the 3 new Companies beyond what plan explicitly creates
- [ ] **(CR-6)** `_normalize_store_name_for_route` matrix test P4-T8 PASSES for: old `- BEI` suffix, new `<Store> - <NewCorp>` pattern, `Ortigas Estancia - BB ESTANCIA FOOD CORP.`, `Vista Mall Taguig - Tricern Food Corp.` (W-6 renames), defensive edge cases
- [ ] **(CR-7)** Helper uses ALLOWLIST `operational_status in (...)` — NULL operational_status is EXCLUDED from grid (P4-T1 h5 test PASS)
- [ ] **(W-1)** Phase 2 script refuses to run without `CONFIRM=yes`; `--dry-run` mode works
- [ ] **(W-2)** `scripts/s196_data_rollback.py` exists as committed Phase 2 deliverable with `--dry-run` support
- [ ] **(W-3)** P2-T5.5 pre-delete audit ran and Cost Center / Account / Customer / Bank Account / Employee / Contact / Address counts = 0 for each to-delete Company
- [ ] **(W-4)** Google Chat announcement posted to Finance + SCM channels (P6-T5)
- [ ] **(W-5)** `_NON_STORE_ENTITIES` drift assertion present in helper; P4-T9 test PASS
- [ ] **(W-6)** 3 legacy `- BEI` warehouses (Vista Mall Taguig, SM Taytay, SM Clark) renamed to store-first-corp-suffix pattern
- [ ] **(W-7)** Branch renamed from `s195-store-universe-company-ssot` to `s196-store-first-naming-and-migration` before push
- [ ] **(W-10)** Rollback Contract documents 10–30 min downtime window
- [ ] **(W-12)** SHFC DEFERRED row added to `SPRINT_REGISTRY.md` (P6-T6)

**HARD BLOCKERs (stop and ask if violated):**

1. **HARD BLOCKER — Preserve `_is_orderable_store` and `_NON_ORDERABLE_*` constants.** These are the correct second-stage filter. Do NOT modify. (Source: `hrms/api/store.py:1763-1790`, S195 audit v2.)
2. **HARD BLOCKER — Do NOT modify the frontend.** `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx` already correctly enumerates `Object.keys(store_meta)`. Fix is backend-only.
3. **HARD BLOCKER — Do NOT delete `_load_s037_rows`, `_STORE_TO_CHILD`, `_S037_RELPATH`, `store_entity_mapping_*.csv`.** These back `list_stores` (Company Master UI). Update `_STORE_TO_CHILD` entries only. (Source: user directive 2026-04-14.)
4. **HARD BLOCKER — Do NOT use the string literal "Archived" in any helper or filter.** Not a valid Select option per `hrms/fixtures/custom_field.json:961-991`. Use the ALLOWLIST form `operational_status in ("Active", "Pre-Opening", "Temporarily Closed", "Pipeline")` (Audit v3 CR-7 — NULL must be EXCLUDED, not passed through).
5. **HARD BLOCKER — Do NOT delete the 4 holding-company warehouses (Araneta Gateway, Robisons Galleria South, SM Caloocan, D'verde Laguna).** Each has 500+ SLE. Re-point only.
6. **HARD BLOCKER — Do NOT re-run the Round 1 data changes.** The 10 deletes + 2 creates + BEI relabel + Sweet Harmony Comment are already live. Phase 2 only adds NEW changes.
7. **HARD BLOCKER — Do NOT auto-merge or auto-deploy.** Per PR-Handoff doctrine (`MEMORY.md:pr-handoff-workflow.md`), Sam is the sole approver/merger. Builder creates PR and stops.
8. **HARD BLOCKER — Do NOT skip Phase 1 code prep before Phase 2 rename.** 26 hardcoded strings will break after rename cascade if not fixed first.
9. **[Audit v3 CR-1] HARD BLOCKER — Every `set_value("Warehouse","company",...)` MUST be immediately followed by SLE + GL Entry `company` back-fill UPDATE (inside the same savepoint).** Frappe does NOT cascade `Warehouse.company` to denormalized `SLE.company` / `GL Entry.company` columns. Skipping the back-fill silently corrupts analytics across 2000+ rows.
10. **[Audit v3 CR-4] HARD BLOCKER — Every Phase 2 multi-doc logical unit MUST be wrapped in `frappe.db.savepoint(name)` with `rollback_to_savepoint(name)` on exception.** Per DM-2 rule in `.claude/rules/frappe-development.md`. A flat try/except with `commit` per rename leaves partial state unrecoverable on mid-stream failure.
11. **[Audit v3 CR-5] HARD BLOCKER — When creating 3 new Companies in Phase 2 Step C, MUST insert with `first_provision_done=1` to suppress the `auto_provision_company` hook.** Otherwise the hook creates ~40 side-effect rows per Company (warehouse, cost center, 27-account COA, Customer, 2 banks, ADMS, GPS) that are not in plan scope. Plan requires manual population of: entity_category, operational_status, abbr, tax_id, branch_tin, bir_rdo_code, store_ownership_type. Confirm parent corp is `is_group=1` before insert.
12. **[Audit v3 CR-3] HARD BLOCKER — Pre-Phase-2 DB backup MUST succeed before any destructive operation.** `bench backup` must be executed via `docker exec` shell (the Python SSM dispatcher cannot invoke bench CLI). Backup path captured to `output/s196/state/PRE_PHASE_2_BACKUP.txt` and verified accessible. If backup fails, ABORT Phase 2.
13. **[Audit v3 W-1] HARD BLOCKER — Phase 2 script MUST refuse to run without `CONFIRM=yes` env var set.** Supports `--dry-run` mode that prints planned actions without executing. Destructive run requires explicit confirmation.

## Ground-Truth Lock

- **evidence_sources:**
  - `hrms/api/store.py:6850` — the stale filter
  - Production API `get_weekly_schedule?week_start=2026-04-13` returned 7 stores BEFORE round 1 (see `output/s195/state/baseline_get_weekly_schedule_BEFORE.json`)
  - Production API `frappe.client.get_list?doctype=Company` — 53 Companies (50 Store + 1 Commissary + 4 Holding + 2 Archived + 1 Franchisor)
  - Team workbook `F:\Downloads\bei_company_register (2).xlsx` — 49 stores, 41 corp entities
  - Superadmin API `https://superadmin.bebang.ph/api/stores` — 48 live stores, cross-validated no SM San Pablo
  - `hrms/fixtures/custom_field.json:961-991` — Select options for entity_category + operational_status (no "Archived")
  - `docs/plans/SPRINT_REGISTRY.md` — rows S181, S188, S190, S195 (superseded)

- **count_method:**
  - metric: orderable Companies returned by `get_orderable_companies()`
  - basis: Company rows where `entity_category in ("Store", "Commissary")` AND `operational_status not in ("Permanently Closed",)` (NULL passes)
  - method: `frappe.get_all("Company", filters={"entity_category": ["in", ["Store","Commissary"]], "operational_status": ["not in", ["Permanently Closed"]]}, pluck="name")`

- **count_method_warehouse:**
  - metric: `store_meta` entries returned by `get_weekly_schedule`
  - basis: one orderable Warehouse per orderable Company
  - method: query Warehouse filtered by `company in <orderable>`, `is_group=0`, `disabled=0`, apply `_is_orderable_store()`, dedup by Company

- **expected_final_counts:**
  - orderable Companies: ~47
  - orderable Warehouses on grid: ~47 (1-per-Company after Phase 2 dedup + re-point + rename)
  - multi-warehouse Companies: 0 (after cryptic duplicates deleted)
  - zero-warehouse Companies (silently omitted): ~3-5 (Sweet Harmony pre-BIR, BEBANG BFC, etc.)

- **authoritative_sections:** Sections "Phases", "L3 Workflow Scenarios", "Verification Script", "Closeout" are authoritative for execution. Predecessor-work table and amendment history are traceability only.
- **unresolved_value_policy:** operator-facing unknowns → `[UNVERIFIED — requires resolution]`
- **normalization_artifacts:**
  - `output/s196/phase_0_rename_matrix.csv` (the 12 renames + 3 creates + 3 deletes + 4 re-points + 2 wh renames + 3 wh deletes)
  - `output/s196/phase_1_code_impact_verified.md` (Phase 1 verification)
  - `output/s196/phase_2_ssm_run_log.txt` (SSM output)
  - `output/s196/post_deploy_validation.md` (before/after grid count)

## Phase Budget Contract (Audit v3 — revised totals)

- **phase_unit_budget:**
  - `Phase 1 — Code prep` → **13 units** (was 10; +3 for P1-T7 normalizer)
  - `Phase 2 — Data migration SSM` → **24 units** (was 15; +9 for P2-T0 backup, P2-T2.5 rollback script, P2-T2.7 legacy wh renames, P2-T5.5 pre-delete audit, P2-T8 SLE/GL backfill, P2-T9 abbr check)
  - `Phase 3 — Code helpers + rewire` → 10 units (unchanged)
  - `Phase 4 — Local verification` → **15 units** (was 10; +5 for P4-T6..T10 new tests + grep gate)
  - `Phase 5 — PR + post-deploy validation` → **11 units** (was 10; +1 for P5-T1 branch rename)
  - `Phase 6 — Closeout` → **6 units** (was 4; +2 for P6-T5 Chat announcement + P6-T6 SHFC DEFERRED reservation)
- **total_estimated_units:** **79** (was 59; Audit v3 +20 — still within 80-unit ceiling BUT tight)
- **hard_limit:** 15 per phase — **Phase 2 at 24 units exceeds this**; see split note below
- **preferred_split_threshold:** 12 per phase
- **Phase 2 split note:** Phase 2 is at 24 units (> 15 hard_limit) because ALL operations must run in one SSM session to maintain atomic cross-step savepoint boundaries. Splitting Phase 2 would break the DM-2 atomicity contract (CR-4). Accept this as a documented exception; mitigation is the strict savepoint wrapping per logical unit.
- **single_session:** yes — one agent, one session (Phase 5 L3 in a separate fresh session per S092 anti-corrupt-success)

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:**
  - artifact: `output/s196/SURFACE_OWNERSHIP_MATRIX.csv`
  - owned files: `hrms/api/company_master.py` (only lines named below + new helpers), `hrms/api/store.py` (get_weekly_schedule + get_day_summary + `_normalize_store_name_for_route` per CR-6), `hrms/fixtures/sales_dashboard_store_mapping.csv`, `hrms/fixtures/store_inventory_shadow_sync_registry.csv`, `hrms/tests/test_s196_*.py` (new — 5 test modules), `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts` (line 36 only), `scripts/s196_data_migration.py` (new), `scripts/s196_ssm_dispatch.py` (new), `scripts/s196_data_rollback.py` (new — Audit v3 W-2), `scripts/s196_grep_gate.py` (new — Audit v3 W-9e), `scripts/s196_verify_csv_fixtures.py` (new — used by P1-T4), `output/s196/**`
- **protected_surfaces:**
  - artifact: `output/s196/PROTECTED_SURFACE_REGISTRY.csv`
  - protected: `_is_orderable_store`, `_NON_ORDERABLE_*` constants, `_load_s037_rows`, `_STORE_TO_CHILD` (values only, keys stay), `_S037_RELPATH`, CSV seed files, frontend delivery-schedule page, Mosaic/Supabase pipelines, S190 billing chain, Sentry instrumentation
- **remote_truth_baseline:**
  - artifact: `output/s196/REMOTE_TRUTH_BASELINE.json`
  - fields: `repo=Bebang-Enterprise-Inc/hrms`, `release_branch=production`, `release_head_sha=<capture at Phase 1 start>`, `live_evidence_basis=get_weekly_schedule returned 7 stores at session start`
- **active_run_coordination:**
  - artifact: `output/s196/state/ACTIVE_RUN_COORDINATION.json` (claim on Phase 1 start, release on closeout)
- **pretouch_backup:**
  - artifact: `output/s196/state/PRETOUCH_BACKUP.json` (records `git rev-parse HEAD` at start of each phase)
- **supersession_map:**
  - artifact: `output/s196/state/SUPERSESSION_MAP.json` (S196 supersedes S195; predecessor SSM round 1 preserved)

## Agent Boot Sequence (Audit v3)

1. **Read this plan fully.** All 13 HARD BLOCKERs, all phases, all verification gates, **all Audit v3 amendments at the top**.
2. **Read the S195 audit v2 plan** at `docs/plans/2026-04-14-sprint-195-store-universe-company-ssot.md` for historical context (superseded, but audit findings still relevant).
3. **Read the audit v3 findings** in `output/plan-audit/s196-store-first-naming-and-data-migration/`:
   - `frappe-backend_findings.md` — CR-1 SLE cascade, CR-2 abbr, CR-3 backup, CR-4 savepoint, CR-5 auto_provision
   - `governance_findings.md` — W-3 pre-delete audit, W-11 registry consistency
   - Design-review / deployment-qa / system-arch findings are in this plan's synthesis at top (Audit v3 Amendments section) since those agents reported inline
4. **Read the Phase 0 exploration artifacts:**
   - `output/s195/plan_phase1_state_inventory.md` — full state of Companies + Warehouses post-round-1
   - `output/s195/plan_phase1_code_impact.md` — full list of hardcoded references to fix
5. **Verify branch state:** `git status` should show no unrelated changes. Branch is currently named `s195-store-universe-company-ssot` (per predecessor); zero commits on top of `origin/production` so far. Phase 5 T1 will rename to `s196-store-first-naming-and-migration` before push.
6. **Capture remote truth baseline:**
   ```bash
   git fetch origin
   git rev-parse origin/production > output/s196/state/PRETOUCH_BACKUP.json
   curl -s "https://hq.bebang.ph/api/method/hrms.api.store.get_weekly_schedule?week_start=2026-04-13" \
     -H "Authorization: token $FRAPPE_API_KEY:$FRAPPE_API_SECRET" \
     > output/s196/state/baseline_round2_BEFORE.json
   ```
   Confirm store_meta has 7 entries (same as round 1 baseline — Phase 2 will change it).
7. **Confirm dependencies:** S181 + S188 + S190 all say DEPLOYED in `docs/plans/SPRINT_REGISTRY.md`. If any say PLANNED or LOCKED, STOP and notify Sam.
8. **Read `hrms/overrides/company.py:592-708`** (auto_provision_company hook) to understand exactly what fires on Company insert — informs Phase 2 Step C (CR-5 suppression pattern).
9. **Begin Phase 1.**

## Execution Authority

Autonomous end-to-end execution. Do NOT stop for progress-only updates.

**Stop only for:**
- HARD BLOCKER violation
- Missing credentials (Doppler `FRAPPE_API_KEY`/`FRAPPE_API_SECRET`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`)
- Rebase produces conflict markers → capture diff to `output/s196/state/REBASE_CONFLICT.diff`, ask Sam
- Deploy run reports FAILED via `gh run watch` → capture log path, ask Sam
- Confidence on any phase gate < 0.80 → summarize to `output/s196/state/LOW_CONFIDENCE.md`, ask Sam
- Phase 2 SSM fails midway (partial rename state) → capture `output/s196/state/SSM_FAILURE.md`, STOP — do NOT retry without Sam reviewing
- Post-deploy validation (Phase 5) reports `len(store_meta) < 40` → invoke Rollback Contract (below)

## Phases

### Phase 1 — Code prep (13 units, was 10 — audit v3 +3 for P1-T7 CR-6)

Fix all hardcoded Company-name references BEFORE the Phase 2 rename cascade. 26 references across 5 files + normalizer update. Based on exploration artifact `output/s195/plan_phase1_code_impact.md`.

| # | Task | Verification | Units |
|---|---|---|---|
| P1-T1 | **[Audit v3 W-8 reworded]** Update `hrms/api/company_master.py:592-609` `_STORE_TO_CHILD` map: **UPDATE 15 values** (12 corp-first → store-first for renamed Companies; 3 BEBANG-prefixed values replaced with new store-first Company names). Keys (store_name strings from S037 CSV) stay the same. MUST_MODIFY `hrms/api/company_master.py`. MUST_CONTAIN: `"SM Manila - Bebang Enterprise Inc."` (new value). MUST_NOT_CONTAIN inside `_STORE_TO_CHILD`: `"Bebang Enterprise Inc. - SM Manila"`, `"BEBANG SM CALOOCAN"`, `"BEBANG ROBINSONS GALLERIA SOUTH"`, `"BEBANG SM SANGANDAAN"` (replaced). | git diff shows 15 changed values in this map | 3 |
| P1-T2 | Update `hrms/api/company_master.py:1143-1147` `populate_s181_fields` pre-seed map: DELETE 3 `BEBANG <STORE>` keys, ADD 3 new store-first keys. | git diff + grep confirm | 1 |
| P1-T3 | Update `hrms/api/company_master.py:1667-1676` accounting-rule-cache warehouse→store lookup: UPDATE 3 entries (keys change to uppercase store-first form per existing convention in that map). | git diff + grep confirm | 1 |
| P1-T4 | Update `hrms/fixtures/sales_dashboard_store_mapping.csv`: 12 rows company column corp-first → store-first (for renamed Companies); 4 rows company column → new per-store children (for re-pointed warehouses: Araneta Gateway, Robisons Galleria South, SM Caloocan, D'verde Laguna); warehouse_record_name column updates for the 2 renamed warehouses (Estancia/Paseo). | `python scripts/s196_verify_csv_fixtures.py` PASS | 3 |
| P1-T5 | Update `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv`: 4 rows whose `warehouse_docname` will change after Phase 2 warehouse renames (Estancia → `Ortigas Estancia - BB ESTANCIA FOOD CORP.`, Paseo Center, plus any affected by the 4 re-points where warehouse name stays but Company changes — for those, no CSV change if only company field moves). | Same verify script | 1 |
| P1-T6 | Update `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts:36`: `Bebang Enterprise Inc. - SM Megamall` → `SM Megamall - Bebang Enterprise Inc.`. | grep + git diff | 1 |
| **P1-T7** | **[Audit v3 CR-6 new]** Update `_normalize_store_name_for_route` in `hrms/api/store.py:1503-1512` to handle ALL post-Phase-2 warehouse naming patterns. Current normalizer strips only `" - BEBANG ENTERPRISE INC."`, `" - BEI"`, `" - BKI"`, `" - BEBANG KITCHEN INC."` suffixes. After Phase 2: (a) 2 renamed warehouses use store-first prefix + corp suffix (e.g., `Ortigas Estancia - BB ESTANCIA FOOD CORP.` → normalizer must strip the ` - BB ESTANCIA FOOD CORP.` suffix), (b) 3 legacy warehouses renamed per W-6 (Vista Mall Taguig, SM Taytay, SM Clark → `<Store> - <NewCorp>` — must strip new corp suffixes), (c) any auto-provisioned warehouses (should NOT exist if CR-5 `first_provision_done=1` works, but defensive). Approach: convert from hardcoded suffix list to regex `(?:\s-\s[A-Z .&']+( INC\.| CORP\.| OPC| HOLDINGS[^-]*)?)+$` that strips all trailing ` - <CorpLike>` segments. MUST_MODIFY `hrms/api/store.py`. MUST_CONTAIN: new regex pattern. Preserves uppercase normalization (maps all to `_CENTRAL_WAREHOUSE_ROUTE_MAP` key form). | Phase 4 P4-T8 normalizer matrix test PASS for all patterns | 3 |

**Phase 1 gate:**
```bash
# MUST return ZERO hits outside docs/plans/ + output/ + archived/
cd F:/Dropbox/Projects/BEI-ERP
grep -rn "Bebang Enterprise Inc\. - SM \|Bebang Mega Inc\. - \|Tungsten Capital - Gateway\|TAJ Food Corp\. - DVerde\|Bebang SM Marikina Inc\. - Sta Lucia\|BEBANG ROBINSONS GALLERIA\|BEBANG SM CALOOCAN\|BEBANG SM SANGANDAAN" \
  --include="*.py" --include="*.ts" --include="*.tsx" --include="*.csv" --include="*.json" \
  hrms/ \
  | grep -v "docs/plans/\|output/\|archived/"
# Expected: empty output
```

Commit Phase 1 changes with message `chore(S196 P1): fix 26 hardcoded Company-name references before rename cascade`.

### Phase 2 — Data migration SSM (24 units, was 15 — audit v3 +9 for CR-1/CR-3/CR-4/CR-5 + W-1/W-2/W-3/W-6)

Order matters — renames before deletes before creates. EVERY step wrapped in `frappe.db.savepoint()` per DM-2 (audit CR-4). Script requires `CONFIRM=yes` env var + supports `--dry-run` (audit W-1).

| # | Task | Verification | Units |
|---|---|---|---|
| **P2-T0** | **[Audit v3 CR-3 new — runs FIRST before any mutation]** Execute MariaDB backup via explicit SSM shell call (the existing Python dispatcher can't run `bench` CLI — must shell-exec in container): SSM command `docker exec $BACKEND /home/frappe/frappe-bench/env/bin/bench --site hq.bebang.ph backup --with-files`. Capture backup path to `output/s196/state/PRE_PHASE_2_BACKUP.txt`. If command exits non-zero or backup path is empty, ABORT Phase 2 — do NOT proceed. Backup path must be downloadable from EC2 for at least 30 days. | File exists with valid backup path; `aws s3 ls` or equivalent confirms backup is accessible | 2 |
| P2-T1 | **[Audit v3 CR-4/CR-5/W-1 reworded]** Write `scripts/s196_data_migration.py`. Structure: Frappe init boilerplate → **require `CONFIRM=yes` env var, support `--dry-run` flag** → BEFORE COUNTS → each step wrapped in `frappe.db.savepoint(name)` + `rollback_to_savepoint(name)` on exception → Step A (rename 12 Companies via `frappe.rename_doc`, one savepoint per rename) → Step B (rename 2 warehouses via `frappe.rename_doc` + new P2-T2.7 3 legacy warehouse renames) → Step C (create 3 new per-store Companies WITH `first_provision_done=1` on insert to suppress `auto_provision_company` hook — document each field to populate manually: entity_category, operational_status, abbr, tax_id, branch_tin, bir_rdo_code, store_ownership_type; confirm parent Corp is `is_group=1`) → Step D (re-point 4 warehouses via `frappe.db.set_value("Warehouse", name, "company", new)` + **P2-T8 SLE/GL back-fill per warehouse inside same savepoint**) → Step E (re-point SM Sangandaan warehouse with backfill) → **P2-T5.5 pre-delete audit** → Step F (delete 3 legacy `BEBANG <STORE>` Companies) → Step G (delete 3 cryptic duplicate warehouses) → Step H (delete JL TRADE OPC + its 5 template warehouses) → **P2-T9 abbr invariance check** → Step I (final verification: query + count orderable, report 47; confirm SLE.company == Warehouse.company per re-pointed wh). MUST_CONTAIN: `CONFIRM` env check, `--dry-run` branch, `savepoint`, `first_provision_done=1`. | File exists; `python scripts/s196_data_migration.py --dry-run` runs without destructive side effects and prints all planned actions | 5 |
| P2-T2 | Write `scripts/s196_ssm_dispatch.py` (copy from `scripts/s195_ssm_dispatch.py`, update script path). Dispatch passes `CONFIRM=yes` env on actual run only; local `--dry-run` invocation precedes SSM dispatch. | File exists | 1 |
| **P2-T2.5** | **[Audit v3 W-2 new]** Write `scripts/s196_data_rollback.py` — inverse migration script. For each Phase 2 operation, generate the reverse: renames back to old docnames (`frappe.rename_doc`), re-points back to old Company (captured before each re-point), re-create 3 deleted legacy Companies (from pre-backup metadata), re-create 3 deleted cryptic warehouses (from backup), re-create JL TRADE OPC. Document limitations: cannot recover auto-provisioned template warehouses deleted via Step F if `auto_provision_company` already fired (use backup restore). Script dry-run-first. | File exists; `python scripts/s196_data_rollback.py --dry-run` emits reverse plan | 2 |
| **P2-T2.7** | **[Audit v3 W-6 new]** Add to Phase 2 Step B: rename 3 additional legacy warehouses to store-first pattern: `Vista Mall Taguig - BEI` → `Vista Mall Taguig - Tricern Food Corp.`, `SM Taytay - BEI` → `SM Taytay - Day Ones Food and Drink Establishments Corp.`, `SM Clark - BEI` → `SM Clark - Red Taldawa Foods OPC`. Use `frappe.rename_doc("Warehouse", old, new)` wrapped in savepoint. P1-T7 normalizer update (CR-6) must handle the new corp-suffix patterns. Reserve a follow-up sprint for remaining 30+ `- BEI` warehouses (not all owned by non-BEI corps). | git diff shows 3 warehouse renames; normalizer test covers new suffixes | 2 |
| P2-T3 | Execute SSM dispatch: `doppler run --project bei-erp --config dev -- python scripts/s196_ssm_dispatch.py`. Requires `CONFIRM=yes`. Capture output to `output/s196/state/ssm_run_log.txt`. Final line must be `S196 PHASE 2 DONE`. Verification block must report exactly 47 orderable warehouses. | Log file exists; `grep "S196 PHASE 2 DONE" output/s196/state/ssm_run_log.txt` returns 1 hit | 3 |
| P2-T4 | Post-Phase-2 production API sanity: curl `get_weekly_schedule?week_start=2026-04-13` — at this point the OLD code is still running (no deploy yet), so store_meta may show 0 or garbage because the old filter now matches nothing. This is EXPECTED. Do NOT panic. Record to `output/s196/state/mid_migration_api_check.json` for traceability. | File exists with expected output | 1 |
| P2-T5 | Verify no orphaned references: run `curl .../frappe.client.get_count?doctype=GL Entry&filters=[["company","=","Bebang Enterprise Inc. - SM Manila"]]` — expect 0. Frappe should have cascaded. | Curl returns 0 for each old name | 2 |
| **P2-T5.5** | **[Audit v3 W-3 new — runs BEFORE Step F delete]** Pre-delete link audit for `BEBANG ROBINSONS GALLERIA SOUTH`, `BEBANG SM CALOOCAN`, `BEBANG SM SANGANDAAN`, `JL TRADE OPC`: query `SELECT parent, COUNT(*) FROM tabCost Center WHERE company=%s GROUP BY parent`, same for `tabAccount`, `tabCustomer`, `tabBank Account`, `tabEmployee`, `tabContact`, `tabAddress`, `tabFiscal Year Company`, `tabItem Default`. Abort Step F/H if any count > 0 and report to `output/s196/state/PRE_DELETE_AUDIT.md` — require Sam's manual resolution of linked docs before deletion can proceed. | Audit file exists; abort correctly if any Company has linked docs | 1 |
| P2-T6 | Data audit CSV: `output/s196/phase_2_rename_matrix_executed.csv` with columns: old_name, new_name, action, timestamp, status, savepoint_name. Populated from SSM script output. | File exists, 25+ rows | 2 |
| **P2-T8** | **[Audit v3 CR-1 new — runs INSIDE each re-point savepoint]** For each of the 4 re-pointed warehouses (Araneta Gateway, Robisons Galleria South, SM Caloocan, D'verde Laguna) AND the SM Sangandaan re-point: after `set_value("Warehouse", name, "company", new)`, run `frappe.db.sql("UPDATE \`tabStock Ledger Entry\` SET company=%s WHERE warehouse=%s", (new_company, wh_name))` and count rows updated. Also update GL Entry via voucher linkage: `UPDATE \`tabGL Entry\` ge JOIN \`tabStock Ledger Entry\` sle ON ge.voucher_no=sle.voucher_no SET ge.company=%s WHERE sle.warehouse=%s`. Log both row counts to run log. Both UPDATEs inside same savepoint as the `set_value` call so rollback is atomic. | Run log shows SLE.company and GL Entry.company back-fill counts; Phase 4 P4-T6 integration test PASS (SLE continuity) | 3 |
| **P2-T9** | **[Audit v3 CR-2 new — runs AFTER all rename steps]** Abbr invariance check: for each of the 12 renamed Companies, verify `Company.abbr` pre-rename matches post-rename (should be preserved by `rename_doc`). Also verify no two Companies share the same abbr post-rename. Also sample-check that existing Account docnames `<name> - <abbr>` still resolve (pick 5 random Accounts per renamed Company and confirm via `frappe.db.exists("Account", name)`). Report to `output/s196/state/ABBR_INVARIANCE_CHECK.md`. | File exists; 0 collisions; 0 missing Accounts | 1 |
| P2-T7 | Commit: `git add -f output/s196/ scripts/s196_*.py && git commit -m "feat(S196 P2): data migration — 12+3 Companies renamed store-first, 4+1 warehouses re-pointed with SLE/GL backfill, 2+3 warehouses renamed, 3 new per-store children created (hook suppressed), 3 legacy + 1 stale Companies deleted (pre-audit clean), 3 cryptic duplicate warehouses deleted; all ops wrapped in savepoints"`. | Commit on branch | 1 |

**Phase 2 gate:** SSM reports `S196 PHASE 2 DONE` + final verification shows 47 orderable warehouses + `grep "Bebang Enterprise Inc\. - SM \|Bebang Mega Inc\. - \|Tungsten Capital - Gateway\|TAJ Food Corp\. - DVerde" hrms/ bei-tasks/ --include="*.py" --include="*.ts" --include="*.csv" --include="*.json" | grep -v "docs/plans/\|output/\|archived/"` returns zero hits.

### Phase 3 — Code helpers + rewire (10 units)

| # | Task | Verification | Units |
|---|---|---|---|
| P3-T1 | **[Audit v3 CR-7 + W-5 reworded]** Add `get_orderable_companies(include_commissary: bool = True) -> list[str]` to `hrms/api/company_master.py`. Filter semantics: **ALLOWLIST** `operational_status in ("Active", "Pre-Opening", "Temporarily Closed", "Pipeline")` (NOT the `not in ("Permanently Closed",)` form — NULL must NOT pass, per CR-7). Plus `entity_category in ("Store", "Commissary")`. ALSO add a module-level assertion (runs on first call, cached) that every key in `_NON_STORE_ENTITIES` has `entity_category != Store/Commissary` — if violated, `frappe.log_error` + raise (per W-5 drift protection). MUST_CONTAIN: `def get_orderable_companies(`, allowlist values, `meta.has_field` defensive check, `_NON_STORE_ENTITIES` consistency check. MUST_NOT_CONTAIN: `"Archived"`, `"not in"` form of operational_status filter. | grep + unit test P4-T1 + P4-T9 | 2 |
| P3-T2 | Add `get_orderable_store_warehouses(include_commissary: bool = True) -> list[dict]` to same file. Algorithm: orderable = get_orderable_companies() → `if not orderable: return []` (G1 short-circuit) → query Warehouse filtered by company IN orderable, is_group=0, disabled=0 → apply `_is_orderable_store()` (lazy import from `hrms.api.store`) → group by Company → deterministic tie-break: `sorted(key=lambda w: (0 if _normalize_store_name_for_route(w["name"]) in _CENTRAL_WAREHOUSE_ROUTE_MAP else 1, w["name"]))` → pick [0]. Log `frappe.log_error` when len(group) > 1. MUST_CONTAIN: `if not orderable`, `key=lambda`, lazy import pattern. | grep + integration test | 3 |
| P3-T3 | Rewire `get_weekly_schedule` in `hrms/api/store.py`. Replace lines 6843-6873 (the `store_meta` build block) with call to `company_master.get_orderable_store_warehouses(include_commissary=True)`. Preserve `warehouse_filter`, `cluster_filter`, grouping logic (`_CENTRAL_WAREHOUSE_ROUTE_MAP` → warehouse_group), Sentry context (`set_backend_observability_context(module="scm", action="get_weekly_schedule", mutation_type="read")`), SCM permission gate. MUST_NOT_CONTAIN anywhere in `get_weekly_schedule`: `["Bebang Enterprise Inc.", "Bebang Kitchen Inc."]`. | grep + manual read | 3 |
| P3-T4 | Audit `get_day_summary` (line ~7116). If same stale filter: rewire. If not (operates on existing entries only): document in `output/s196/phase_3_get_day_summary_audit.md` with reasoning. | Audit doc OR git diff | 1 |
| P3-T5 | Audit `get_store_schedule` + `get_orders_for_dispatch` (registered in `bei-tasks/app/api/delivery-schedule/route.ts:11-15`). Rewire or document per-endpoint verdict in `output/s196/phase_3_other_endpoints_audit.md`. | Audit doc | 1 |

### Phase 4 — Local verification (15 units, was 10 — audit v3 +5 for P4-T6..T10 W-9)

| # | Task | Verification | Units |
|---|---|---|---|
| P4-T1 | Add unit tests `hrms/tests/test_s196_orderable_companies.py` — 11 cases: (a) ≥47 store companies returned, (b) excludes Permanently Closed, (c) excludes Head Office / Holding / Franchisor / Warehouse entity_category, (d) includes commissary when include_commissary=True, (e) excludes commissary when False, (f) get_orderable_store_warehouses returns ≥47 rows, (g) every wh passes `_is_orderable_store`, (h1) negative — BGC CAPITAL HOUSE / BRITTANY OFFICE NOT in result, (h2) G1 empty-list short-circuit via mock, (h3) G3 multi-warehouse determinism 3x same result, (h4) rogue "Archived" entity_category rows (created via raw SQL) excluded, **(h5 [Audit v3 CR-7])** NULL `operational_status` is EXCLUDED by allowlist filter (mock Company with op_status=None, assert not in result). | `bench --site hq.bebang.ph run-tests --module hrms.tests.test_s196_orderable_companies` all 12 PASS | 3 |
| P4-T2 | Add integration test `hrms/tests/test_s196_get_weekly_schedule.py` — calls `get_weekly_schedule(week_start="2026-04-13")`, asserts `len(store_meta) >= 47`, `"Shaw BLVD - BKI" in store_meta`, no Head Office warehouse, no cryptic duplicate warehouse name. | `bench ... run-tests --module hrms.tests.test_s196_get_weekly_schedule` PASS | 2 |
| P4-T3 | Write `output/s196/verify_s196.py` filesystem-verification script. Uses `git diff --name-only origin/production...HEAD` + grep. Checks: MUST_MODIFY files in diff, MUST_CONTAIN patterns, MUST_NOT_CONTAIN patterns in specific functions, HARD BLOCKER preservation (frontend untouched, `_is_orderable_store` untouched, CSV fixtures deleted=False), Sentry context present, all 26 Phase 1 references updated, P1-T7 normalizer regex present, `first_provision_done=1` in Phase 2 script, `savepoint` calls in Phase 2 script, allowlist filter in helper (no `not in` form). Exit 0 only when all checks PASS. | `python output/s196/verify_s196.py` exits 0 | 3 |
| P4-T4 | Run `bench --site hq.bebang.ph migrate` locally (no schema change expected — sanity). Check `~/frappe-bench/logs/web.log` last 100 lines for errors. | No errors | 1 |
| P4-T5 | Local smoke: curl local backend's `get_weekly_schedule` via API token; assert store_meta ≥ 47, `Shaw BLVD - BKI` present, no Head Office. Save to `output/s196/phase_4_local_response.json`. | File exists; assertions PASS | 1 |
| **P4-T6** | **[Audit v3 W-9a / CR-1 verification]** Add integration test `hrms/tests/test_s196_sle_continuity.py` — for the 5 re-pointed warehouses (Araneta Gateway, Robisons Galleria South, SM Caloocan, D'verde Laguna, SM Sangandaan), assert `frappe.db.count("Stock Ledger Entry", {"warehouse": wh_name, "company": ["!=", frappe.db.get_value("Warehouse", wh_name, "company")]}) == 0` (all SLE rows have company matching the warehouse). Same check for GL Entry via voucher linkage. | `bench ... run-tests --module hrms.tests.test_s196_sle_continuity` PASS | 1 |
| **P4-T7** | **[Audit v3 W-9b / CR-2 verification]** Add integration test `hrms/tests/test_s196_account_preservation.py` — for each of the 12 renamed Companies, sample 5 Accounts and confirm docname `<AccountName> - <abbr>` still exists after rename. Confirm no two Companies share an `abbr` value. Confirm `Company.abbr` was NOT changed (compare pre-rename snapshot). | PASS | 1 |
| **P4-T8** | **[Audit v3 W-9c / CR-6 verification]** Add unit test `hrms/tests/test_s196_normalizer.py` — matrix of 20+ warehouse names × expected `_CENTRAL_WAREHOUSE_ROUTE_MAP` key. Covers: old `Estancia - BEI` pattern, new `Ortigas Estancia - BB ESTANCIA FOOD CORP.` pattern, `Vista Mall Taguig - Tricern Food Corp.` pattern (W-6 renames), `Robisons Galleria South - Tungsten Capital Holdings OPC` pattern, plus defensive cases: double space `SM  Manila`, trailing whitespace, nested suffixes `- BEI-RPA`. | All 20+ rows PASS | 1 |
| **P4-T9** | **[Audit v3 W-9d / W-5 verification]** Add unit test `hrms/tests/test_s196_non_store_entities_sync.py` — for every key in `_NON_STORE_ENTITIES` map at `hrms/api/company_master.py:503`, assert Frappe DB has Company with that name AND entity_category != Store/Commissary. Prevents drift where someone adds a BEI/BKI sub-entity to `_NON_STORE_ENTITIES` without updating Company Custom Field. | PASS | 1 |
| **P4-T10** | **[Audit v3 W-9e]** CI-runnable grep gate: write `scripts/s196_grep_gate.py` (not a test, a CLI). Greps `hrms/ bei-tasks/` excluding `docs/plans/ output/ archived/` for the 26 Phase 1 forbidden strings + any remnant `["Bebang Enterprise Inc.", "Bebang Kitchen Inc."]` filter. Exits non-zero if any hit. Called in Phase 5 pre-push and in P4-T3 verify script. | `python scripts/s196_grep_gate.py` exits 0 | 1 |

### Phase 5 — PR + post-deploy validation (10 units)

| # | Task | Verification | Units |
|---|---|---|---|
| P5-T1 | **[Audit v3 W-7 reworded]** Rename branch for hygiene: `git branch -m s195-store-universe-company-ssot s196-store-first-naming-and-migration`. Then rebase against `origin/production`: `git fetch origin && git rebase origin/production`. Resolve any conflicts (unlikely — branch was freshly created). If conflicts produce markers, STOP per stop_only_for. Run `python scripts/s196_grep_gate.py` (P4-T10) as final gate before push. | git status clean; branch renamed; grep gate exit 0 | 2 |
| P5-T2 | Commit all Phase 3+4 changes: `git add -f hrms/api/company_master.py hrms/api/store.py hrms/tests/test_s196_*.py scripts/s196_*.py output/s196/ docs/plans/SPRINT_REGISTRY.md && git commit -m "feat(S196 P3+P4): store universe helper + delivery schedule rewire + tests"`. Push to `origin/s196-store-first-naming-and-migration` (with `-u` flag since this is first push of new branch name). | Push succeeds | 1 |
| P5-T3 | Open PR: `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s196-store-first-naming-and-migration --title "fix(S196): store universe SSOT + store-first Company naming — delivery schedule shows 47 stores" --body "$(cat <<'EOF' ... EOF)"`. PR body includes full Requirements Regression Checklist filled in + Audit v3 summary (7 CRITICAL + 12 WARNING applied) + before/after counts + Phase 1–4 evidence file paths. Update `SPRINT_REGISTRY.md` row with PR number. | PR URL returned; registry row updated | 2 |
| P5-T4 | Wait for Sam to review + merge + deploy. If Sam REJECTs or NEEDS_FIX, read PR comment, fix on SAME branch, push, re-request review. STOP autonomous loop only for HARD BLOCKERs. Per PR-Handoff doctrine: agent NEVER auto-merges or auto-deploys. | PR APPROVED + merged by Sam | (wait for Sam) |
| P5-T5 | Post-deploy production curl: `curl -s "https://hq.bebang.ph/api/method/hrms.api.store.get_weekly_schedule?week_start=2026-04-13" -H "Authorization: token $FRAPPE_API_KEY:$FRAPPE_API_SECRET"`. Assert len(store_meta) >= 47, "Shaw BLVD - BKI" in store_meta. Save to `output/s196/post_deploy_validation.md` with before=7, after=47 comparison. | File exists; assertions PASS | 2 |
| P5-T6 | Post-deploy NEGATIVE test: verify `BGC CAPITAL HOUSE`, `BRITTANY OFFICE`, parent `Bebang Enterprise Inc.` head-office warehouses are NOT in store_meta. | Assertion in post_deploy_validation.md PASS | 1 |
| P5-T7 | Sentry confirmation: in project `bei-hrms`, search for `transaction:hrms.api.store.get_weekly_schedule` after deploy. Confirm `module=scm action=get_weekly_schedule` tags present. Screenshot or query result saved to `output/s196/sentry_confirmation.md`. | File exists | 1 |
| P5-T8 | Generate L3 handoff prompt for a FRESH agent session (per CLAUDE.md + S092 anti-corrupt-success rule). Output to Sam with scenarios list + evidence dirs. L3 execution is NOT done in this session. | Handoff prompt in output message | 2 |

### Phase 6 — Closeout (6 units, was 4 — audit v3 +2 for P6-T5 W-4 / P6-T6 W-12)

| # | Task | Verification | Units |
|---|---|---|---|
| P6-T1 | Update plan YAML: `status: COMPLETED`, `completed_date: 2026-04-XX`, `execution_summary: <paragraph>`. | git diff shows YAML change | 1 |
| P6-T2 | Update `SPRINT_REGISTRY.md` S196 row: status `PLANNED_AUDITED_v3` → `COMPLETED YYYY-MM-DD — <summary>` with PR number. | git diff shows row update | 1 |
| P6-T3 | Commit closeout: `git add -f docs/plans/ && git commit -m "chore(S196): closeout — store-first naming + data migration shipped, grid 7→47 stores"`. Push to branch (or open separate closeout PR if policy requires). | Commit exists | 1 |
| **P6-T5** | **[Audit v3 W-4 new]** Post Google Chat announcement to Finance + SCM channels (bot identity: Blip). Template body: "S196 deployed 2026-04-XX. Company docnames renamed to STORE-FIRST convention (e.g., `SM Manila - Bebang Enterprise Inc.` instead of `Bebang Enterprise Inc. - SM Manila`). **Action required:** finance/ops users must refresh any saved Desk bookmarks, saved report filters, chart filters, favorites that reference renamed Companies. Full rename list: `output/s196/phase_2_rename_matrix_executed.csv`. Invoice print format still displays corp-first (unchanged) — separate follow-up sprint will add print-format reversal for internal Desk views if needed. Questions to Sam." Use `/chat` skill or `hrms/api/google_chat.py`. | Message posted; response URL captured to `output/s196/chat_announcement.md` | 1 |
| **P6-T6** | **[Audit v3 W-12 new]** Reserve shadow follow-up sprint in `SPRINT_REGISTRY.md` for SHFC (Sweet Harmony Food Corp) restructure. Add row with `status: DEFERRED`, `trigger: SM San Pablo BIR registration complete`, reference to Frappe Comment `n6gqgqltuq`, reference to S188 playbook (restructure to `is_group=1`, create per-store children with store-first naming, re-point warehouses, follow CR-5 hook suppression). This ensures the work stays searchable in the registry — not lost when the timeline Comment scrolls off. | New registry row exists; row text searchable via `grep "DEFERRED.*SHFC" docs/plans/SPRINT_REGISTRY.md` | 1 |
| P6-T4 | Post PR comment to Sam: "S196 COMPLETED. Grid: 7→47 stores. Company renaming: 12 store-first + 3 new + 3 deleted + 1 stale deleted. Warehouses: 4 re-pointed + 2 renamed + 3 duplicates deleted. Evidence: `output/s196/post_deploy_validation.md`. L3 handoff prompt in prior message." | Comment posted | 1 |

## L3 Workflow Scenarios

Run in a SEPARATE fresh agent session (per CLAUDE.md + S092 anti-corrupt-success rule). Current session generates the handoff prompt only.

**Library audit (pre-run):**
- Existing Page Object: `bei-tasks/tests/e2e/pages/scm/DeliverySchedulePage.ts` (from S192)
- Existing fixture: `loggedInAsSCM` (from S192)
- Library contributions if any: document in `output/l3/s196/LIBRARY_CONTRIBUTIONS.md`

**Scenarios (real-browser Playwright):**

| User | Action | Expected outcome | Failure means |
|---|---|---|---|
| `loggedInAsSCM` | Navigate to `/dashboard/scm/delivery-schedule`, week Apr 13–19 | Weekly Grid shows ≥ 47 stores grouped (3MD North / Pinnacle South / Jentec / Other) | Helper returning wrong count |
| `loggedInAsSCM` | Scroll group "Other" | `Shaw BLVD - BKI` row visible | Commissary excluded (wrong include_commissary flag) |
| `loggedInAsSCM` | Search "BGC CAPITAL", "BRITTANY" | Zero results | Head Office leaked through filter |
| `loggedInAsSCM` | Search store name that was renamed — "SM Manila", "Ayala Evo City", "Robinsons Antipolo" | Row appears with cleaned short name | Store-first Company docname broke warehouse lookup |
| `loggedInAsSCM` | Click store/day cell, toggle COLD | Toggle persists, entry_count +1 | `toggle_delivery` regression |
| `loggedInAsSCM` | Switch to "Daily Route" tab | Loads, honors same universe | `get_day_summary` regression (P3-T4) |
| `loggedInAsSCM` | Switch to "Store Card" tab, search "SM Manila" | Single result, no 500 | `get_store_schedule` regression (P3-T5) |

**Evidence files required before closeout:**
- `output/l3/s196/form_submissions.json`
- `output/l3/s196/api_mutations.json`
- `output/l3/s196/state_verification.json`
- `output/l3/s196/screenshots/*.png`

**Failure Response (per qa-test-library-discipline doc):**
- Mode A (app bug) → file `[BUG-S196-NN]` in `output/l3/s196/DEFECTS.csv`, re-run after fix
- Mode B (test bug) → fix test, promote to Page Object if reusable
- Mode C (brittleness) → fix library, not spec. No `waitForTimeout`, no `retry(3)` masking
- If ≥3 library fixes → emit `output/l3/s196/LIBRARY_IMPROVEMENTS.md`

## Verification Script

At `output/s196/verify_s196.py`. Filesystem-based, not agent-self-report. Follows the S154 machine-verifiable gate rule.

Key assertions:
```python
# MUST_MODIFY
- hrms/api/company_master.py in git diff
- hrms/api/store.py in git diff
- hrms/fixtures/sales_dashboard_store_mapping.csv in git diff
- hrms/tests/test_s196_orderable_companies.py new file
- hrms/tests/test_s196_get_weekly_schedule.py new file

# MUST_CONTAIN
- def get_orderable_companies(
- def get_orderable_store_warehouses(
- "Permanently Closed"
- "entity_category"
- if not orderable  (G1 short-circuit)
- key=lambda  (G3 deterministic sort)
- _CENTRAL_WAREHOUSE_ROUTE_MAP
- meta.has_field
- set_backend_observability_context\(\s*module="scm"

# MUST_NOT_CONTAIN
- Inside get_weekly_schedule body: ["Bebang Enterprise Inc.", "Bebang Kitchen Inc."]
- Inside helper body: "Archived"
- In any *.py or *.ts or *.csv outside output/ archived/ docs/plans/:
  "Bebang Enterprise Inc. - SM Manila"
  "Bebang Enterprise Inc. - SM Megamall"
  "Bebang Enterprise Inc. - SM Southmall"
  "Bebang Enterprise Inc. - Robinsons Antipolo"
  "Bebang Mega Inc. - Ayala Evo City"
  "Bebang Mega Inc. - Ayala Vermosa"
  "Bebang Mega Inc. - Robinsons Gen Trias"
  "Bebang Mega Inc. - Robinsons Imus"
  "Bebang Mega Inc. - SM Tanza"
  "Bebang SM Marikina Inc. - Sta Lucia"
  "TAJ Food Corp. - DVerde Calamba"
  "Tungsten Capital - Gateway Mall"
  "BEBANG ROBINSONS GALLERIA SOUTH"
  "BEBANG SM CALOOCAN"
  "BEBANG SM SANGANDAAN"
  "BB ESTANCIA FOOD CORP. - Ortigas Estancia - BBEFC"
  "BEBANG PASEO INC. - Paseo Center - BPI"

# HARD BLOCKER preservation
- _is_orderable_store NOT modified (no + / - lines at that def)
- bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx NOT in git diff
- hrms/data_seed/store_entity_mapping_2026-04-13.csv NOT deleted
- _load_s037_rows NOT deleted
- _STORE_TO_CHILD still defined (values updated, structure preserved)

# Phase artifacts present
- output/s196/phase_0_rename_matrix.csv
- output/s196/state/ssm_run_log.txt
- output/s196/post_deploy_validation.md
```

Exit 0 only when every check PASSes.

## Zero-Skip Enforcement

Every task in every phase MUST be implemented. No exceptions.

**Phase Completion Checklist** — after each phase, append to `output/s196/PHASE_COMPLETION_CHECKLIST.md`:

```markdown
| Phase | Task | Status | Evidence | Skipped? | If skipped, why? |
|---|---|---|---|---|---|
| 1 | P1-T1 _STORE_TO_CHILD map | DONE | git sha abc123 | NO | — |
| 1 | P1-T2 populate_s181_fields map | DONE | ... | NO | — |
```

If any task is skipped or partial → STOP, notify Sam BEFORE proceeding.

**PR description gate:** full task table in PR body. Sam REJECTs PRs with unexplained gaps.

**L3 handoff gate:** every task listed so the fresh L3 agent can verify builder claims.

**Forbidden agent behaviors:**
- Silent task skipping
- Marking partial work as DONE
- Replacing a task with a simpler version without Sam's approval
- "Deferred to next sprint" as a way to drop work
- Combining tasks and dropping features in the merge commit
- Happy-path-only implementation (especially P5-T6 negative test)

## Status Reconciliation Contract

Whenever counts, blockers, stage, or status changes → update in the same work unit:

1. `output/s196/RUN_STATUS.json`
2. `output/s196/PHASE_COMPLETION_CHECKLIST.md`
3. `output/s196/RUN_SUMMARY.md`
4. `output/l3/s196/DEFECTS.csv` (if defects emerge during P5 L3)
5. plan status line + authoritative sections of this file
6. `docs/plans/SPRINT_REGISTRY.md` row at PR_CREATED, DEPLOYED, COMPLETED

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam (CEO)
- **signoff_artifact:** PR comment from Sam approving + merging; closeout commit updates plan YAML to COMPLETED
- **note:** no synthetic department signoff required

## Autonomous Execution Contract

- **completion_condition:** (Audit v3 revised)
  - Phase 1 — 26 hardcoded references updated; P1-T7 normalizer handles all post-migration patterns; grep gate `scripts/s196_grep_gate.py` clean
  - Phase 2 — P2-T0 backup captured + verified; SSM reports `S196 PHASE 2 DONE` with `CONFIRM=yes`; P2-T5.5 pre-delete audit clean; P2-T8 SLE/GL back-fill counts logged; P2-T9 abbr invariance PASS; P2-T2.5 rollback script exists as deliverable; final verification shows 47 orderable
  - Phase 3 — helpers added with allowlist filter (no NULL pass-through, no `"Archived"`); `_NON_STORE_ENTITIES` drift assertion present; `get_weekly_schedule` rewired; `get_day_summary` audited
  - Phase 4 — all 12 unit tests PASS (T1 now 12 cases incl. h5 NULL exclusion); P4-T2/T6/T7/T8/T9 integration + matrix tests PASS; `verify_s196.py` exit 0; `scripts/s196_grep_gate.py` exit 0
  - Phase 5 — branch renamed to `s196-store-first-naming-and-migration`; PR opened; merged by Sam; deployed; post-deploy validation PASS (≥ 47 stores, commissary IN, head office OUT)
  - Phase 6 — plan YAML + registry updated to COMPLETED; Google Chat announcement posted (P6-T5); SHFC DEFERRED row added to registry (P6-T6); L3 handoff prompt generated
- **stop_only_for:** (listed under Execution Authority above)
- **continue_without_pause_through:** Phase 1 → Phase 2 → Phase 3 → Phase 4 → PR creation → wait_for_Sam → Phase 5 → Phase 6
- **blocker_policy:**
  - programmatic → fix and continue
  - 3 failed test attempts → grounded research, then continue
  - business-data/policy → pause
  - rebase/deploy/low-confidence → per stop_only_for
- **canonical_closeout_artifacts:** (Audit v3 additions marked *)
  - `output/s196/RUN_STATUS.json`
  - `output/s196/RUN_SUMMARY.md`
  - `output/s196/PHASE_COMPLETION_CHECKLIST.md`
  - `output/s196/phase_2_rename_matrix_executed.csv`
  - `output/s196/post_deploy_validation.md`
  - `output/s196/state/ssm_run_log.txt`
  - `output/s196/sentry_confirmation.md`
  - `output/s196/state/PRE_PHASE_2_BACKUP.txt` *(Audit v3 CR-3)*
  - `output/s196/state/PRE_DELETE_AUDIT.md` *(Audit v3 W-3)*
  - `output/s196/state/ABBR_INVARIANCE_CHECK.md` *(Audit v3 CR-2)*
  - `output/s196/chat_announcement.md` *(Audit v3 W-4)*
  - `scripts/s196_data_rollback.py` *(Audit v3 W-2 deliverable)*
  - `scripts/s196_grep_gate.py` *(Audit v3 W-9e deliverable)*
  - `docs/plans/2026-04-15-sprint-196-store-first-naming-and-data-migration.md` (this file, status COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S196 row COMPLETED + SHFC DEFERRED row per W-12)

## Rollback Contract

Live ops surface — no feature flag. Rollback path MUST be defined before deploy.

**Rollback required if ANY within 30 minutes of deploy:**
1. Post-deploy curl returns `len(store_meta) < 40` (universe regression)
2. Head Office warehouses appear in store_meta (containment broken)
3. Sentry error rate on `transaction:hrms.api.store.get_weekly_schedule` > 5x 30-day baseline within 5 minutes
4. L3 P5-T8 (separate session) fails > 2 of 7 scenarios (non-flake)
5. Sam observes broken UI + explicitly asks for rollback

**Data rollback (Phase 2 reversal):**
- **[Audit v3 W-2]** Rollback script `scripts/s196_data_rollback.py` is a Phase 2 deliverable (written in P2-T2.5 BEFORE any destructive operation runs). Contents: inverse migration — rename_doc back (using captured old_name from `phase_2_rename_matrix_executed.csv`), set_value back (re-point to old Company), recreate 3 deleted legacy Companies (from pre-audit snapshot), recreate 3 deleted cryptic warehouses, recreate JL TRADE OPC + its template warehouses. Supports `--dry-run`.
- **[Audit v3 CR-3]** Pre-Phase-2 DB backup EXECUTED via explicit SSM shell-exec to `bench` (not via Python dispatcher — the dispatcher cannot invoke bench CLI). P2-T0 runs this as the FIRST task of Phase 2 and aborts if backup fails. Backup path captured to `output/s196/state/PRE_PHASE_2_BACKUP.txt`.
- **[Audit v3 W-10]** Rollback downtime window: **10–30 minutes** (MariaDB dump restore time for ~20GB BEI DB on EC2 Docker container; PITR not available since BEI uses local Docker MariaDB, not RDS). Scheduled maintenance announcement required BEFORE running rollback. Post Google Chat notice 5 min before restore begins.
- Rollback decision path: if code revert is sufficient (post-deploy curl fix), prefer that over data rollback. Only restore DB backup if Phase 2 data changes themselves caused the incident AND the P2-T2.5 inverse script can't cleanly reverse.

**Code rollback (Phase 3 reversal):**
```bash
# Preferred: PR revert
GH_TOKEN="" gh pr create --base production --head s196-rollback \
  --title "revert(S196): store universe SSOT — rollback per criterion #N"
# Then in PR: git revert <merge-commit> && git push

# Fast path: direct revert
cd F:/Dropbox/Projects/BEI-ERP
git fetch origin && git checkout production && git pull origin production
git revert -m 1 <S196-merge-SHA>
git push origin production
# Then trigger redeploy
```

**Post-rollback:**
1. RCA to `output/s196/ROLLBACK_RCA.md` within 24 hours
2. Plan YAML status → `ROLLED_BACK`, registry row → `ROLLED_BACK YYYY-MM-DD — <reason>`
3. Open S197 follow-up if required
4. Do NOT re-deploy same SHA without addressing root cause

**NOT rollback triggers:**
- Single Sentry error → investigate
- 1 flaky L3 scenario → re-run
- Latency +200ms → log + monitor
- Unexpected Company appears → verify entity_category first, may be data hygiene not code bug

## Out of Scope (explicit non-goals)

- Retiring `store_entity_mapping_2026-04-13.csv` + `_load_s037_rows` (separate sprint once Company DocType proven sufficient for `list_stores`)
- Print-format reversal for invoices (`<Corp> - <Store>` display) — separate sprint
- Restructuring single-store corps (TRICERN, DAY ONES, RED TALDAWA, etc.) into parent+child — future sprint if Sam wants
- Restructuring `SWEET HARMONY FOOD CORP.` when SM San Pablo BIR-registers — separate sprint following S188 playbook
- Renaming the "- BEI" suffix on now-correctly-owned warehouses (SM Taytay, SM Clark, Vista Mall Taguig, etc.) — cosmetic, not blocking
- JL TRADE OPC recovery if Sam identifies it later
- Data hygiene relabel of 2 "Archived" entity_category rows (named "JV" and "Managed Franchise", created via raw SQL) — out-of-band data fix

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| `frappe.rename_doc` fails midway → partial state | Each rename wrapped in try/except + commit per step; SSM log shows which failed; DB backup pre-Phase-2 |
| Re-pointing warehouse with 500+ SLE triggers revaluation | Re-point is field change, Frappe cascades; verify SLE count before/after on 1 warehouse as smoke |
| Phase 1 grep misses a hardcoded reference not yet discovered | Post-Phase-2 grep gate re-runs same pattern; any hits fail verify_s196.py |
| Test env doesn't have renamed Companies | Tests filter by entity_category, not hardcoded names; integration test asserts Shaw BLVD (untouched) + count ≥ 47 |
| Sentry transaction names change after rewire | Same function name = same Sentry transaction |
| 4 re-pointed warehouses show bad valuation | `repost_item_valuation` queue; verify via `get_stock_balance` curl |
| Rebase against production produces conflicts from parallel S194/S193 merges | stop_only_for trigger; Sam reviews conflict diff |
| Round-1 data changes not preserved (agent re-runs) | HARD BLOCKER #6; Phase 0 reading predecessor-work table is mandatory |

## Closeout Checklist (Audit v3)

**Phase 1**
- [ ] 26 hardcoded references updated
- [ ] Grep gate `scripts/s196_grep_gate.py` exit 0 (outside docs/plans/, output/, archived/)
- [ ] P1-T7 normalizer handles all post-migration warehouse name patterns

**Phase 2**
- [ ] P2-T0 DB backup captured — `output/s196/state/PRE_PHASE_2_BACKUP.txt` exists with valid path
- [ ] P2-T2.5 rollback script `scripts/s196_data_rollback.py` written + dry-run tested
- [ ] P2-T5.5 pre-delete link audit clean (Cost Centers / Accounts / Customers / Bank Accounts / Employees = 0 per to-delete Company)
- [ ] SSM dispatch: `CONFIRM=yes`, `S196 PHASE 2 DONE`, 47 orderable warehouses reported
- [ ] P2-T8 SLE + GL Entry back-fill counts logged for all 5 re-pointed warehouses
- [ ] P2-T9 abbr invariance PASS — 0 abbr collisions, 0 missing Accounts
- [ ] Every operation wrapped in `frappe.db.savepoint()` (grep `scripts/s196_data_migration.py` confirms)
- [ ] 3 new Companies inserted with `first_provision_done=1` (CR-5)

**Phase 3**
- [ ] Helpers added with ALLOWLIST `operational_status` filter (CR-7)
- [ ] `_NON_STORE_ENTITIES` drift assertion present (W-5)
- [ ] `get_weekly_schedule` no longer references `[Bebang Enterprise Inc., Bebang Kitchen Inc.]`

**Phase 4**
- [ ] 12 unit tests PASS in `test_s196_orderable_companies.py` (includes h5 NULL exclusion)
- [ ] P4-T6 SLE continuity test PASS
- [ ] P4-T7 Account naming preservation test PASS
- [ ] P4-T8 normalizer matrix test PASS
- [ ] P4-T9 `_NON_STORE_ENTITIES` drift test PASS
- [ ] `verify_s196.py` exit 0

**Phase 5**
- [ ] Branch renamed to `s196-store-first-naming-and-migration` before push
- [ ] PR merged by Sam + deploy SUCCESS
- [ ] Post-deploy curl: `len(store_meta) >= 47`, Shaw BLVD IN, Head Office OUT

**Phase 6**
- [ ] Plan YAML status COMPLETED + `completed_date` + `execution_summary`
- [ ] `SPRINT_REGISTRY.md` S196 row COMPLETED + PR number
- [ ] P6-T5 Google Chat announcement posted to Finance + SCM channels
- [ ] P6-T6 SHFC DEFERRED row added to SPRINT_REGISTRY.md
- [ ] All canonical_closeout_artifacts present and committed via `git add -f`
- [ ] L3 handoff prompt generated + posted to Sam
- [ ] PR comment posted to Sam announcing completion

**Safety**
- [ ] No HARD BLOCKER violations (all 13 preserved)
- [ ] Round-1 data preserved (none of the 10 deletes / 2 creates / BEI relabel / Sweet Harmony comment n6gqgqltuq regressed)
- [ ] Rollback Contract tested: `scripts/s196_data_rollback.py --dry-run` emits valid inverse plan

## Execution Workflow

- Test Python locally: `/local-frappe`
- Deploy (Sam-mediated): `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing (separate session): `/e2e-test` → `/l3-v2-bei-erp`
