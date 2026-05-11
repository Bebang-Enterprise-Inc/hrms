# S246 Phase 2 — CEO Decision Gate Outcome

**Decision date:** 2026-05-11
**Decision authority:** Sam Karazi (CEO, single-owner signoff)
**Format:** In-session decision based on `output/l3/s246/audit/audit_report.md` findings
**No external review:** per CEO directive 2026-05-11, no Denise / finance review pre-decision (Butch/Alyssa/Juanna resigned; Denise has not yet been positioned for ICT-003 architectural reviews)

---

## Chosen Option: 3-corrected (SE + PI split with SRBNB GR/IR clearing)

### What gets built (S247)

1. **PI generator refactored** to billing-only: `pi.update_stock=0`, `pi.items[].expense_account = SRBNB`, `pi.credit_to = 2103210 - AP-Trade-BKI - <ABBR>`.
2. **NEW Stock Entry generator** at `hrms/api/bki_store_stock_entry_generator.py` producing `Material Receipt` SE: `se.items[].t_warehouse = buyer_company`, `se.items[].expense_account = SRBNB`, `bki_si_reference = si.name`.
3. **`hrms/hooks.py`** STRING→LIST conversion for both `Sales Invoice.on_submit` (PI + SE generators) and `Sales Invoice.on_cancel` (SE-first cascade, then PI cascade). New `Stock Entry.validate` hook for the SE posting-date lock.
4. **BEI Settings kill-switch toggles** for both generators (PI toggle already exists at value=1; SE toggle is NEW).
5. **`Stock Entry.bki_si_reference` Custom Field** installed via idempotent script.
6. **Master-data UPDATEs:**
   - Phase 4a (pre-deploy, safe): `Company.cost_center = 'Main - <ABBR>'` on the 4 BEI-parent stores (ROA, SMM, SMMM, SMS)
   - Phase 4b (post-deploy): `Company.stock_received_but_not_billed`, `Warehouse.account = 1104210 - ...`, `Supplier.accounts[BKI TRADE]` entries per Company
7. **Historical 839 BKI SI cleanup** via `scripts/s247/cleanup_historical_test_bki_si.py` with generator toggles disabled during cleanup.
8. **L3 sweep re-run** with single-store smoke first, then full 49 stores, plus the new GR/IR JE chain assertion (Dr 1104210 once, Cr 2103210 once, SRBNB nets to zero).

### Resulting GL chain per BKI→Store shipment (post-deploy)

```
SE (Material Receipt, update_stock=1)
    Dr  1104210 - Inventory-from-Commissary - <ABBR>     (via Warehouse.account)
    Cr  Stock Received But Not Billed - <ABBR>           (via item.expense_account)

PI (update_stock=0)
    Dr  Stock Received But Not Billed - <ABBR>           (via item.expense_account)
    Dr  1106210 - Input VAT - BKI Inter-Co - <ABBR>      (via tax row)
    Cr  2103210 - AP-Trade-BKI - <ABBR>                  (via pi.credit_to)

Net per shipment:
    Dr  1104210 Inventory-from-Commissary
    Dr  1106210 Input VAT
    Cr  2103210 AP-Trade-BKI
    SRBNB clearing nets to zero.
```

This is the textbook ERPNext / SAP / Oracle / NetSuite GR/IR (Goods Receipt / Invoice Received) pattern for receiving from external suppliers.

### Atomicity stance (per v1.1 Decision 3 amendment)

**Independent savepoint isolation** with daily reconciliation cron sweep for half-paired SIs. SI submit never fails on paired-doc generation issue. If PI generation fails, SE still runs; if SE fails, PI still runs; if both fail, SI is still successfully submitted. Half-paired state is tolerable for hours, not days — reconciliation cron (S248 follow-up) retries or alerts.

### Cancel cascade order (per v1.1 Blocker 10)

**SE first, then PI** (reverse-creation order, textbook reversal pattern). Hook list in `hrms/hooks.py` declares them in this order.

### perpetual_inventory_consistency

**Decision: defer to S247 Phase 4b.** Currently 36 stores have `enable_perpetual_inventory=1` and 13 have `=0`. Option 3-corrected works on both states (it doesn't rely on perpetual being on, because the explicit `expense_account = SRBNB` setting bypasses the auto-stock-accounting path that the perpetual flag controls). But for CONSISTENCY across the fleet and proper inventory GL on every store, the recommendation is to set perpetual=1 on all 49 in S247 Phase 4b. CEO approves this default in S247 (no further decision needed unless audit during S247 surfaces a reason to deviate).

---

## Scope of S246 (this sprint, closing here)

**COMPLETED (Phases 0, 1A, 1B, 2):**
- Phase 0: Boot + worktree + baseline state
- Phase 1A: Canonical store master-data spec + extended verifier v2 + 49-store gap report (0/49 fully canonical)
- Phase 1B: 7-item audit + 30-day Error Log sweep + consolidated audit_report.md
- Phase 2: This decision

**DEFERRED to S247:**
- Phase 3A: PI generator refactor (update_stock=0 + SRBNB routing)
- Phase 3B: Stock Entry generator + hook wiring + SE posting-date lock + Internal Customer guard
- Phase 3C: BEI Settings SE toggle + SE Custom Field install
- Phase 4a: Pre-deploy cost_center on 4 stores
- Phase 4b: Post-deploy SRBNB + Warehouse.account + Supplier.accounts
- Phase 5: L3 sweep validation (single-store smoke + 49-store + GR/IR JE assertion)
- Phase 6: Historical 839 BKI SI cleanup with toggle-disable
- Phase 7: Closeout

S246 keeps Phases 0-2 (~30 work units actually executed). S247 will be ~70 units of pure implementation with the architectural decision frozen.

---

## Rationale: why Option 3-corrected won

| Criterion | Option 1 (disable perpetual) | Option 2 (perpetual + WH.account=1104210) | Option 3-corrected (SE+PI split, SRBNB GR/IR) |
|---|---|---|---|
| Stock GL on store books | ❌ NONE | ✅ YES | ✅ YES |
| Preserves "Inventory-from-Commissary" semantic | ❌ N/A | ❌ collapses to single 1104210 use | ✅ explicit account |
| Reporting granularity | ❌ poor | 🟡 medium | ✅ high (SE + PI split with bki_si_reference) |
| ERPNext canonical pattern | ❌ band-aid | 🟡 acceptable | ✅ matches SAP/Oracle/NetSuite GR/IR |
| Audit trail | 🟡 minimal | 🟡 single doc | ✅ two paired docs, clean separation |
| Implementation cost | 🟢 lowest | 🟡 medium | 🟥 highest (generator rewrite + new doctype hook) |
| Risk on cancellation/return | 🟢 N/A | 🟡 single doc cascade | 🟡 dual-doc cascade (SE first, PI second) |

Option 3-corrected wins on every quality dimension except implementation cost. CEO accepts the higher implementation cost in exchange for the proper long-term answer.

The audit data specifically dispositioned the "Option 1 is acceptable as band-aid" case: the 13 stores currently operating under Option 1 conditions (perpetual=0) produce ZERO stock GL entries from the BKI flow. The design intent is silently dropped on 100% of these stores. Locking that in fleet-wide would mean ZERO BKI-related inventory GL across all 49 stores forever. That's not a band-aid; it's removing a feature that was never actually working.

---

## Signoff

- **Approver:** Sam Karazi (CEO)
- **Date:** 2026-05-11
- **Mode:** single-owner (per BEI policy 2026-04-15: Butch/Alyssa/Juanna resigned; CEO is sole signoff authority for architectural decisions)
- **Decision:** **Option 3-corrected**
- **Next step:** close S246 as PR_OPEN (audit + decision only). Write S247 plan when ready, with this decision frozen as the architectural premise.

---

## Items the S247 plan must include from this decision

1. **All Phase 3A/3B/3C/4a/4b/5/6/7 task details from S246 v1.1 plan body** — most can be lifted verbatim.
2. **`perpetual_inventory_consistency: yes`** in Phase 4b master-data UPDATEs (all 49 stores → perpetual=1).
3. **Reconciliation cron task** for half-paired SIs (as a follow-up sprint, not necessarily in S247 itself).
4. **The architectural premise** baked into Design Rationale: Option 3-corrected was CEO-chosen on 2026-05-11 based on `output/l3/s246/audit/audit_report.md` evidence.
5. **Reference to S246's evidence** (`output/l3/s246/audit/CANONICAL_STORE_SPEC.md`, `output/l3/s246/verification/verify_canonical_v2_before.json`) as input to S247's planning.
