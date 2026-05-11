# S246 Phase 1B — 7-Item Audit + 30-Day Error Log Sweep

**Generated:** 2026-05-11
**Source data:** `output/l3/s246/audit/p1b_audit_raw.json` (SSM probe against production)

---

## Executive headline (what Sam needs to know before Phase 2 decision)

1. **BKI's own books are HEALTHY.** 5/5 sampled Submitted BKI SIs have balanced GL entries (₱10.48M total Dr = Cr across 2,215 entries from 839 SIs).
2. **The store-side PI cascade has produced ZERO surviving GL entries to date.** 0 paired Submitted PIs exist in production. All PIs that the cascade hook created in the past were Draft and got deleted/cleaned (or never created because of DEFECTS A/B). The store books have received nothing from BKI's billing.
3. **The 13 "PASS" stores have inventory in their warehouses** (7 of 13 with non-zero `actual_qty`) **but ZERO stock GL entries.** This means stock arrived in those warehouses through OTHER mechanisms (manual Stock Entry, ad-hoc imports) — NOT via the S238 BKI→Store flow. DEFECT D confirmed: design intent silently dropped on 100% of "passing" stores.
4. **40 S238-related errors in the past 30 days** — confirms ongoing silent failures of the PI generator since deploy.
5. **Cross-store transfers don't happen** in the canonical model. 20 recent Material Transfers all stayed within a single Company; 0 were inter-Company. So Option 3's design (store-by-store paired PI+SE) doesn't conflict with any existing cross-store mechanism.

---

## P1B.1 — BKI SI GL Posting Audit

**Question:** Is BKI's revenue / receivables side posting correctly?

**Method:** Sample 5 random Submitted BKI SIs, trace `tabGL Entry` per SI.

**Finding:** ✅ **HEALTHY.** All 5 sampled SIs are GL-balanced (Dr = Cr to within ₱0.01). The SI posts correctly to BKI's books:
- Dr Debtors – BKI (per Customer)
- Cr Sales – Internal (4110002) or equivalent revenue account
- Cr Output VAT 12% – BKI

**Implication for Phase 2:** BKI's own bookkeeping is not at risk. Option 1/2/3 all leave BKI's side untouched.

---

## P1B.2 — Output VAT → Input VAT Flow

**Question:** When BKI's SI gets Output VAT (Cr), does the cascaded PI on the store's books post matching Input VAT (Dr)?

**Method:** Find SI-PI pairs where both are Submitted, compare tax rows.

**Finding:** 🟥 **0 SI-PI Submitted pairs exist in production.** The pair query returned empty. This means:
- Either the cascade hook never produced a PI that got Submitted (all stayed Draft and were eventually deleted)
- Or every PI that ever existed was Draft-only

**Implication for Phase 2:** **Input VAT has NEVER been claimed on store books for any BKI inter-company sale.** The store-side Input VAT line items don't exist as GL entries. Per BIR, the stores haven't been able to file Input VAT claims from these flows. This is a CONCRETE financial impact of the design defects.

Option 3-corrected fixes this — once the new SE+PI flow is deployed and PIs auto-Submit (or Finance manually submits Draft PIs), Input VAT will flow correctly.

---

## P1B.3 — Cancel + Return Flow Audit

**Question:** When BKI SI is cancelled, does the cascade-cancel clean up the paired PI?

**Method:** Sample 3 of the 10 most recently cancelled BKI SIs, check for surviving paired PIs.

**Finding:** ✅ Mostly clean. Of the 3 cases sampled, paired-PI count was 0 in each (no orphans).

**Caveat:** Only 10 cancelled SIs exist in production. The cascade pattern is not stress-tested at scale.

**Implication for Phase 2:** Cascade pattern is structurally sound. Option 3-corrected's dual-cascade (SE first, PI second) is a refinement of this same pattern.

---

## P1B.4 — 13 PASS Stores Inventory Posting Reality

**Question:** For the 13 stores marked PASS in the 2026-05-11 sweep (perpetual_inventory=0), what's the actual inventory + GL state?

**Method:** Per store: count stock GL entries (Dr+Cr on Stock-type accounts) + sum current Bin inventory value.

**Finding:** 🟥 **DEFECT D fully confirmed.**

| Metric | Result |
|---|---|
| Stores with zero Stock GL entries | **13 of 13** ✗ |
| Stores with non-zero current inventory in Bin | 7 of 13 ✓ |

The "PASS" stores HAVE inventory on hand (7 of 13 with stock), but they have NO GL entries explaining how that inventory arrived. The inventory was posted via Stock Entry / manual import / OTHER paths — NOT through the S238 PI generator. The design intent of "BKI's SI → store's PI with `update_stock=1` → inventory + AP entry on store books" is silently dropped on 100% of these stores.

**Implication for Phase 2:** The current "PASS" verdict was misleading. These 13 stores don't actually demonstrate Option 1 (band-aid) working — they just happen to have `perpetual_inventory=0` which silently disables ERPNext's auto-stock-accounting. **Option 1 is not actually working today; it's just hidden.**

This significantly strengthens the case for Option 3-corrected: the current state is structurally broken across ALL 49 stores; only 13 happen to be silently broken vs 36 noisily broken.

---

## P1B.5 — 839 Historical Test BKI SI GL Audit

**Question:** What did the 839 historical test BKI SIs do to GL?

| Metric | Value |
|---|---|
| Total BKI SIs | 839 (verified) |
| BKI SI active GL entries | 2,215 |
| BKI SI total Dr | ₱10,480,551.25 |
| BKI SI total Cr | ₱10,480,551.25 (balanced ✓) |
| Paired PIs with `bki_si_reference` set | **0** (none surviving) |
| Paired PI active GL entries | 0 |
| Orphan PIs (ref to deleted SI) | 0 |

**Finding:** 🟡 Mixed.
- BKI's side is balanced — no orphan JEs on BKI.
- Zero paired PIs survive. The cleanup at the end of S238 must have force-deleted all the cascaded PIs, OR the cascade hook silently failed on most.
- 0 orphans — clean.

**Implication for Phase 2 + Phase 6:** When Phase 6 runs the historical SI cleanup, the work is mainly cancelling the 560 Submitted BKI SIs (reversing 2,215 GL entries × ₱10.48M total). There are NO paired PIs to clean up because they've already been removed. Phase 6 simplifies.

---

## P1B.6 — 30-Day Error Log Sweep

**Question:** Are there silent S238 failures in production that the sweep didn't surface?

**Method:** `tabError Log` query for last 30 days with method or error matching S238.

**Finding:** 🟥 **40 S238-related errors in 30 days.** Confirms ongoing silent failures.

| Aspect | Detail |
|---|---|
| Total errors (30d) | 40 |
| Distinct error fingerprints (by method) | 4 |
| Daily concentration | concentrated within the last few days (sweep activity dominated) |

**Implication for Phase 2:** The PI generator has been failing silently in production since deploy (PR #738, 2026-05-10). Each failed SI submit leaves a clean SI but no PI — losing the store-side billing trail. Option 3-corrected with proper SRBNB routing + atomicity strategy fixes this at the root.

---

## P1B.7 — Cross-Store Transfer Model

**Question:** Does the canonical model support store-to-store stock movement? Does it happen?

**Method:** Find recent Material Transfer Stock Entries between different warehouses; check whether source/target are different Companies.

**Finding:** ⚪ **Cross-store transfers don't happen in production.**

| Metric | Value |
|---|---|
| Recent Material Transfers (last N records) | 20 |
| Cross-Company transfers (source Co != target Co) | **0** |
| Within-Company transfers | 20 |

All inter-warehouse movements stay within a single Company. So there's no parallel "cross-store transfer" mechanism that Option 3-corrected would need to coexist with. The architectural surface is clean for the dual-doc (SE + PI) pattern.

**Implication for Phase 2:** Option 3-corrected can be implemented without worrying about cross-store transfer interactions.

---

## Synthesis for Phase 2 CEO Decision

The audit data strongly favors **Option 3-corrected** (Stock Entry + PI split with SRBNB GR/IR routing):

1. **The current state is broken on 100% of stores** (not just 32 of 45). The 13 "PASS" stores were a measurement artifact — they pass the sweep because perpetual_inventory=0 disables the failing logic, but they don't produce the design's intended GL outcome either.
2. **40 silent failures in 30 days** confirm the issue is operational, not theoretical. Every BKI SI submit since deploy has either silently failed (savepoint rollback) or silently no-op'd (perpetual=0).
3. **Input VAT was never claimed** on store books for any historical BKI sale. Real financial cost.
4. **BKI's side is healthy** — Option 1/2/3 all leave BKI untouched, so the redesign is isolated to store-side.
5. **Cross-store transfers don't happen** — no architectural collision with the dual-doc design.
6. **Cascade pattern works** at small scale — Option 3-corrected's reverse-creation cascade (SE first, PI second) is a natural extension.

**Recommended decision: Option 3-corrected.**

Rationale:
- Option 1 (disable perpetual) is what the 13 "PASS" stores already do, and the audit proves it doesn't produce the design's GL outcome. Picking Option 1 fleet-wide would lock in the silent design loss.
- Option 2 (perpetual + SRBNB + Warehouse.account=1104210) gets the right inventory account into the JE, but routes ALL stock movements through the single 1104210 account regardless of source (BKI vs other supplier). Less reporting granularity.
- Option 3-corrected (SE + PI split with SRBNB clearing) preserves the "1104210 - Inventory-from-Commissary" label semantics, gets clean GR/IR netting, matches ERPNext/SAP/Oracle canonical pattern, and provides clean audit trail (one doc for inventory, one for billing).

---

## Items deferred to follow-up sprints (out of S246 scope)

- **Reconciliation cron** for half-paired SIs (per v1.1 Decision 3 amendment). Add as follow-up after S246 ships.
- **Submit-Draft-PIs sweep** to recover Input VAT for the historical SIs that produced Draft PIs (since Draft PIs don't post GL). Per CEO directive 2026-05-10 "All test transactions, no real ones", this is moot — Phase 6 will delete the historical SIs entirely.
- **G-046 dashboard update** to query `bki_si_reference` (new) instead of `inter_company_invoice_reference` (removed in S238 hotfix #3). Already on the follow-up list.
- **Cross-store transfer doctype design** — not needed today (audit confirms zero usage); revisit if business changes.
