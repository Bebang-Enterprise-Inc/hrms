# Design: Procurement Module Bug Fixes

**Date:** 2026-02-07
**Spec:** procurement-bugfix

---

## 1. Solution Architecture

All fixes are **surgical patches** to existing code. No new files, no schema changes, no migrations.

### Backend Fixes (5 bugs in `hrms/api/procurement.py`)

| Bug | Function | Fix Type | Lines |
|-----|----------|----------|-------|
| BUG-1 | `get_invoices()` | Add field to SELECT | ~764 |
| BUG-2 | `get_payment_requests()` | Add field to SELECT/JOIN | ~915 |
| BUG-3 | `get_received_value_for_po()` | Fix table/field names | ~1650-1683 |
| BUG-4 | `get_suppliers()` | Add alias `total_amount` | ~68 |
| BUG-7 | `get_purchase_order()` | Add items subquery | varies |

### Frontend Fixes (2 bugs in `bei-tasks/app/dashboard/procurement/`)

| Bug | File | Fix Type |
|-----|------|----------|
| BUG-5 | `layout.tsx` or sidebar component | Add "Pending" label to badges |
| BUG-6 | `reports/page.tsx` | Add `comingSoon: true` flag |

---

## 2. Detailed Fix Designs

### BUG-1: Add `purchase_order` to Invoice List API

**Current SQL (approximate):**
```sql
SELECT name, invoice_no, supplier, grand_total, status, ...
FROM `tabBEI Invoice`
```

**Fixed SQL:**
```sql
SELECT name, invoice_no, supplier, purchase_order, grand_total, status, ...
FROM `tabBEI Invoice`
```

**Risk:** None - additive field, no breaking change.

### BUG-2: Add `supplier` to Payment Request List API

**Option A (preferred):** If `tabBEI Payment Request` has a `supplier` field:
```sql
SELECT name, rfp_id, supplier, payment_amount, status, ...
FROM `tabBEI Payment Request`
```

**Option B:** If supplier must be resolved via chain:
```sql
SELECT pr.name, pr.rfp_id, pr.payment_amount, pr.status,
       COALESCE(inv.supplier, po.supplier) as supplier
FROM `tabBEI Payment Request` pr
LEFT JOIN `tabBEI Invoice` inv ON pr.invoice_reference = inv.name
LEFT JOIN `tabBEI Purchase Order` po ON pr.po_reference = po.name
```

**Risk:** Option B adds a JOIN which could slow large result sets. Use Option A if field exists.

### BUG-3: Fix `get_received_value_for_po` Table References

**Approach:**
1. Identify actual table name for GR items (likely `tabBEI GR Item`)
2. Identify correct field names (likely `qty`, `rate` or `unit_cost`)
3. Fix the SQL to match actual schema

**Risk:** Low - read-only query, no data modification.

### BUG-4: Align Supplier Field Name

**Preferred fix (backend):** Add alias in SELECT:
```sql
SELECT ..., total_po_value as total_amount, ...
```

This avoids touching frontend code and maintains backward compatibility.

**Risk:** None - alias is additive.

### BUG-5: Clarify Sidebar Badge Labels

**Current:** Badge shows `{count}` (just a number)
**Fixed:** Badge shows `{count} pending` or tooltip "Pending Approvals"

**Alternative:** If badges show total counts instead:
- Change API call from `get_pending_po_approvals` to `get_purchase_orders` with count
- This changes the semantics - discuss with team

**Recommended:** Keep pending approval count but add "pending" label.

### BUG-6: Add Coming Soon to Goods Receipt Log

**Current:**
```tsx
{ name: "Goods Receipt Log", ... }
```

**Fixed:**
```tsx
{ name: "Goods Receipt Log", comingSoon: true, ... }
```

**Risk:** None.

### BUG-7: Include PO Items in Detail Response

**Approach:** In `get_purchase_order()`, after fetching the PO header, query child table:
```sql
SELECT item_name, qty, rate, amount
FROM `tabBEI PO Item`
WHERE parent = %(po_name)s
ORDER BY idx
```

Include the items array in the response JSON.

**Risk:** Low - standard Frappe child table pattern.

---

## 3. Development Workflow (MANDATORY - /build Rules)

### Phase 0: Setup

1. **Feature branch:** `fix/procurement-bugs` (already on `feat/commissary-completion-testing`, will branch from there or use directly)
2. **Tasks:** Created via TaskCreate for each bug fix

### During Implementation

**For Python/API changes (BUG-1,2,3,4,7):**
1. Edit `hrms/api/procurement.py`
2. Test each fix via curl against production API (read-only fixes are safe to test live)
3. Use `/local-frappe` if available, otherwise test via API calls
4. Commit all backend fixes together

**For Frontend changes (BUG-5,6):**
1. Edit files in `bei-tasks` repo
2. Test locally with `npm run dev`
3. Verify via Chrome DevTools MCP
4. Commit frontend fixes separately

**For Commits:**
- Use `/pr-deploy` for deployment
- Follow commit message conventions: `fix(procurement): description`
- Include Co-Authored-By tag

### Phase Completion

1. **Code review** by Opus code-reviewer agent
2. **Backend deployment** via PR to production (GitHub Actions Docker build)
3. **Frontend deployment** via PR to main (Vercel auto-deploy)
4. **E2E verification** via `/test-full-cycle` or targeted Chrome DevTools testing

---

## 4. Cost Savings Analysis

Since this is a bugfix (not new feature), the audit prevented scope creep:

| Metric | Without Audit | With Audit | Savings |
|--------|---------------|------------|---------|
| Bugs identified | Unknown | 7 specific | **Targeted fixes** |
| Files to modify | Unknown | 2 files | **No wasted effort** |
| New DocTypes needed | 0 | 0 | **Confirmed none needed** |
| Schema migrations | 0 | 0 | **No deployment risk** |
| Estimated effort | Days (guessing) | 2-4 hours | **90% time saved** |

---

## 5. Deployment Strategy

### Step 1: Backend (BEI-ERP repo)
```
Feature branch → PR to production → GitHub Actions build → Docker deploy → bench migrate
```

### Step 2: Frontend (bei-tasks repo)
```
Feature branch → PR to main → Vercel auto-deploy → Verify on my.bebang.ph
```

### Step 3: Verification
```
curl API tests → Chrome DevTools page snapshots → All 7 bugs confirmed fixed
```

### Rollback Plan
- Backend: `docker service rollback frappe_backend`
- Frontend: Vercel instant rollback to previous deployment
