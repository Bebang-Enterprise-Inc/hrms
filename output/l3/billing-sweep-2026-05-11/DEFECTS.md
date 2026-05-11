# Billing Sweep Defects — BKI→Store PI Generator

**Sweep date:** 2026-05-11
**Scope:** 49 candidate buyer Companies (45 canonical stores + 4 BEI-parent skeleton stores from S243)
**Evidence:** `tmp/billing-sweep/sweep_result.json`, `tmp/billing-sweep/one_failure_result.json`, `tmp/billing-sweep/perp_result.json`

## Verdict counts

| Verdict | Count | Meaning |
|---|---|---|
| PASS (with caveats) | 13 | PI created — BUT see DEFECT C below |
| FAIL (PI never created) | 30 | DEFECT B |
| FAIL (PI created, wrong expense acct) | 2 | DEFECT B + C |
| DEFECT_CONFIRMED (4 BEI-parent stores) | 4 | DEFECT A |

**No leftover test SIs or PIs.** Cleanup verified: `aftermath_result.json` → leftover_si=0, leftover_pi=0, orphan_pi=0.

---

## DEFECT A — 4 stores miss `Company.cost_center` (CRITICAL)

**Stores:** ROBINSONS ANTIPOLO, SM MANILA, SM MEGAMALL, SM SOUTHMALL (all under BEBANG ENTERPRISE INC. parent)

**Symptom:** PI generation fails silently via savepoint rollback.

**Cause:** S243 seeded canonical CoA accounts on these 4 stores but did NOT set `Company.cost_center`. The generator's `_resolve_per_store_cost_center` falls back to `Company.cost_center` → NULL → `frappe.throw` → savepoint rollback → no PI created.

**Fix:** Set `Company.cost_center = 'Main - <ABBR>'` per store. Verify `Main - <ABBR>` Cost Center exists first.

**Severity:** CRITICAL — silent revenue posting miss on 4 active stores.

---

## DEFECT B — 32 stores miss `Company.stock_received_but_not_billed` (CRITICAL, NEW)

**Stores:** All 32 of the FAIL stores have `Company.enable_perpetual_inventory=1` AND `stock_received_but_not_billed=NULL`. 

The 13 PASS stores have `enable_perpetual_inventory=0` — they passed only because ERPNext's auto-stock-accounting logic was bypassed entirely.

**Symptom:** PI generation fails silently via savepoint rollback.

**Cause:** ERPNext's `purchase_invoice.set_expense_account()` calls `get_company_default("stock_received_but_not_billed")` when `update_stock=1` AND `is_perpetual_inventory_enabled(company)` is True. If the company default isn't set → `frappe.throw("Please set default Stock Received But Not Billed in Company ...")` → savepoint rollback → no PI created.

**Proof (full traceback captured in `one_failure_result.json` for AYALA FAIRVIEW TERRACES):**
```
frappe.exceptions.ValidationError: Please set default Stock Received But Not Billed 
in Company AYALA FAIRVIEW TERRACES - BEBANG FT INC.
  at erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py:455
  → self.get_company_default("stock_received_but_not_billed")
```

**Per-Company evidence:**

| `enable_perpetual_inventory` | `stock_received_but_not_billed` | Verdict | Count |
|---|---|---|---|
| 0 (disabled) | NULL | PASS | 13 |
| 1 (enabled) | NULL | FAIL (no PI) | 30 |
| 1 (enabled) | SET | FAIL (wrong expense_account) | 2 (GHO, SMK) |
| 0 (disabled) | NULL | DEFECT A | 4 |

**Fix options** (architectural decision needed):

1. **Set `Company.stock_received_but_not_billed` on the 32 stores** — point to a per-store SRBNB account. ERPNext's standard template uses `Stock Received But Not Billed - <ABBR>` (a Liability account). Most stores already have such an account but it's not set as the Company default.

2. **Disable `enable_perpetual_inventory=0` on the 32 stores** — match the 13 PASS stores. Side effect: no auto-stock-accounting JEs on PI submit. Inventory still moves via SLE but no GL impact from PI directly.

3. **Stop using `update_stock=1` in the generator** — change ICT-003 design. Separate stock receipt (via Stock Entry) from billing (PI with `update_stock=0`). Two-document flow.

**Severity:** CRITICAL — most stores (32/45 active) can't generate a store-side PI today. The "silent" nature means BKI's SI submits cleanly while the store's books gain nothing — no payable, no inventory cost, no expense.

---

## DEFECT C — `update_stock=1` causes expense_account to be overridden (CRITICAL)

**Stores affected:** All stores where `enable_perpetual_inventory=1`. Visible on 2 stores (GHO, SMK) where SRBNB happens to be set so PI insertion succeeds.

**Symptom:** Generator computes `expense_account = "1104210 - Inventory-from-Commissary"` correctly, then ERPNext's `set_expense_account(for_validate=True)` OVERWRITES it with the warehouse's account (e.g., `"Stock In Hand - GHO"`).

**Cause:** ERPNext's `purchase_invoice.py:set_expense_account` runs during `validate` with `for_validate=True`. The branch `if not item.expense_account or for_validate` means it always replaces during validate.

**Result:** Even when the PI inserts successfully, the journal entries on submit will hit:
- Dr: `Stock In Hand - <ABBR>` (whatever Warehouse.account is)
- Cr: `2103210 - AP-Trade-BKI - <ABBR>`

NOT what the canonical CoA design intended (which was `Dr: 1104210 - Inventory-from-Commissary`).

**Severity:** CRITICAL when PI submits go live — wrong GL accounts on every store-side PI.

**Fix options:**

1. **Map `Warehouse.account = "1104210 - Inventory-from-Commissary"`** per store. Then ERPNext's override picks the desired account.

2. **Stop using `update_stock=1`.** Same as DEFECT B option 3.

3. **Accept the override** — change ICT-003 design to use `Stock In Hand - <ABBR>` as the canonical inventory landing account, and reposition `1104210 - Inventory-from-Commissary` as a reporting roll-up.

---

## DEFECT D (informational) — 13 "PASS" stores have `enable_perpetual_inventory=0`

These 13 stores passed only by accident — their perpetual inventory is disabled, so the PI inserts without stock accounting. On submit, no stock GL entries are created at all. The PI behaves as a non-stock invoice.

**Implication:** Even the "passing" stores are not posting inventory to the store's books on PI submit. The whole "BKI→Store inventory transfer via update_stock=1 PI" mechanism is broken or skipped on 100% of active stores.

This is a SOFT PASS — the test infrastructure accepted these as PASS because the asserted fields match, but the GL outcome isn't what the canonical design called for.

---

## Architectural summary

The ICT-003 design as implemented:
- Generator sets `pi.update_stock=1` so inventory lands on the store's books
- Generator sets `pi.items[].expense_account = "1104210 - Inventory-from-Commissary"`

Reality:
- `update_stock=1` + perpetual inventory triggers ERPNext's SRBNB validation → blocks PI for 32 stores
- `update_stock=1` + perpetual inventory triggers expense_account override → wrong account for 2 visible + all 32 if unblocked

**The current generator is incompatible with `enable_perpetual_inventory=1` across all 45 active stores.**

For the 13 stores where it "works," the design's GL intent is silently dropped because perpetual is off.

---

## Cleanup state

- Leftover SIs: 0
- Leftover PIs: 0
- Orphan PIs: 0
- Production state restored to pre-sweep.

---

## Suggested next steps (need CEO decision)

The original Phase C plan (4-store cost_center fix) only addresses DEFECT A. The newly-discovered DEFECTS B/C/D require a real architectural decision before any fix sprint is sensible:

**Question for Sam:** how do we want BKI→Store PI inventory mechanics to actually work in production?

- **Option 1** (least invasive): Disable `enable_perpetual_inventory=0` on the 32 stores to match the 13. Generator works, but no automatic stock GL on store-side PIs (the inventory transfer is implicit via SLE only).
- **Option 2** (correct ERPNext path): Enable perpetual everywhere AND set SRBNB + warehouse.account = 1104210 per store + accept ERPNext's expense_account model. Many small data fixes per store.
- **Option 3** (redesign): Stop using `update_stock=1` on PI. Generator becomes billing-only. Inventory moves via separate Stock Entry doc. Requires generator rewrite.
