# Tasks: Procurement Module Bug Fixes

**Date:** 2026-02-07
**Spec:** procurement-bugfix

---

## Task Execution Order

```
TASK-1 (Backend bugs) → TASK-2 (Code review) → TASK-3 (Backend deploy) →
TASK-4 (Frontend bugs) → TASK-5 (Frontend code review) → TASK-6 (Frontend deploy) →
TASK-7 (E2E verification)
```

---

## TASK-1: Fix 5 Backend Bugs in procurement.py

**Type:** CODE
**Owner:** backend-dev (or lead)
**Priority:** CRITICAL
**Estimated:** 1-2 hours

### Steps:

1. Read `hrms/api/procurement.py` to find exact line numbers for each function
2. **BUG-1:** In `get_invoices()`, add `purchase_order` to the SQL SELECT fields
3. **BUG-2:** In `get_payment_requests()`, add `supplier` field (direct field or JOIN)
4. **BUG-3:** In `get_received_value_for_po()`, fix table name and field references to match actual `tabBEI GR Item` schema
5. **BUG-4:** In `get_suppliers()`, add alias `total_po_value as total_amount` OR add `total_amount` field
6. **BUG-7:** In `get_purchase_order()`, add child table query for `tabBEI PO Item` items
7. Verify each fix with curl:
   ```bash
   FRAPPE_KEY=$(doppler secrets get FRAPPE_API_KEY --project bei-erp --config dev --plain)
   FRAPPE_SECRET=$(doppler secrets get FRAPPE_API_SECRET --project bei-erp --config dev --plain)

   # BUG-1: Check invoice has purchase_order field
   curl -s "https://hq.bebang.ph/api/method/hrms.api.procurement.get_invoices" \
     -H "Authorization: token ${FRAPPE_KEY}:${FRAPPE_SECRET}" | python -m json.tool

   # BUG-3: Check received value works
   curl -s "https://hq.bebang.ph/api/method/hrms.api.procurement.get_received_value_for_po?po_name=PO-2026-00040" \
     -H "Authorization: token ${FRAPPE_KEY}:${FRAPPE_SECRET}" | python -m json.tool
   ```

### Acceptance Criteria:
- [ ] `get_invoices` response includes `purchase_order` field for each invoice
- [ ] `get_payment_requests` response includes `supplier` field for each payment
- [ ] `get_received_value_for_po` returns 200 (not 500) with ordered/received values
- [ ] `get_suppliers` response includes `total_amount` field (formatted currency-ready)
- [ ] `get_purchase_order` response includes `items` array with line item details

---

## TASK-2: Code Review Backend Changes

**Type:** REVIEW
**Owner:** code-reviewer (Opus)
**Priority:** HIGH
**Blocked by:** TASK-1

### Review Checklist:
- [ ] No SQL injection vulnerabilities in modified queries
- [ ] No N+1 query patterns introduced
- [ ] Field names match actual DocType definitions
- [ ] JOINs use proper index columns (name, parent)
- [ ] Response format is backward-compatible (no removed fields)
- [ ] Error handling for edge cases (null supplier, no items)

---

## TASK-3: Deploy Backend Fixes

**Type:** DEPLOY
**Owner:** deployer
**Priority:** CRITICAL
**Blocked by:** TASK-2

### Steps:
1. Commit backend changes:
   ```
   git add hrms/api/procurement.py
   git commit -m "fix(procurement): Fix 5 API bugs found in audit (BUG-1,2,3,4,7)"
   ```
2. Create PR via `/pr-deploy`:
   - PR title: "fix(procurement): Fix 5 API bugs from Feb 7 audit"
   - Base: production
3. Monitor GitHub Actions build (Docker image)
4. After merge, verify endpoints respond correctly
5. Poll deployment using `scripts/wait_for_deployment.py`:
   ```python
   wait_for_frappe_migration(
       doctype="BEI Invoice",
       field="purchase_order",  # Verify field accessible
       max_wait_seconds=600,
       poll_interval=30
   )
   ```

### Acceptance Criteria:
- [ ] PR created and CI passes
- [ ] Docker build completes successfully
- [ ] All 5 fixed endpoints return correct data on production

---

## TASK-4: Fix 2 Frontend Bugs in bei-tasks

**Type:** CODE
**Owner:** frontend-dev (or lead)
**Priority:** MEDIUM
**Blocked by:** TASK-3 (backend must deploy first for API field changes)

### Steps:
1. **BUG-5:** In sidebar/layout component:
   - Find badge rendering code
   - Add "pending" label text or tooltip
   - Example: `{count > 0 ? `${count} pending` : null}`
2. **BUG-6:** In `reports/page.tsx`:
   - Find the reports array/config
   - Add `comingSoon: true` to "Goods Receipt Log" entry
3. Also verify BUG-4 is fixed from backend (field name alignment):
   - Check `suppliers/page.tsx` reads the correct field name
   - If backend provides `total_amount` alias, no frontend change needed
   - If not, update frontend to read `total_po_value`
4. Test locally:
   ```bash
   cd ../bei-tasks && npm run dev
   ```
5. Verify via browser at localhost:3000

### Acceptance Criteria:
- [ ] Sidebar badges show "X pending" (not just "X")
- [ ] Goods Receipt Log has "Coming Soon" badge
- [ ] Supplier list shows formatted PHP values (not NaN)

---

## TASK-5: Code Review Frontend Changes

**Type:** REVIEW
**Owner:** code-reviewer (Opus)
**Priority:** MEDIUM
**Blocked by:** TASK-4

### Review Checklist:
- [ ] No XSS vulnerabilities in dynamic content
- [ ] Proper null/undefined handling for display values
- [ ] Consistent styling with existing "Coming Soon" badges
- [ ] No hardcoded strings (use i18n if applicable)

---

## TASK-6: Deploy Frontend Fixes

**Type:** DEPLOY
**Owner:** deployer
**Priority:** MEDIUM
**Blocked by:** TASK-5

### Steps:
1. Commit frontend changes:
   ```
   cd ../bei-tasks
   git add app/dashboard/procurement/
   git commit -m "fix(procurement): Fix sidebar badges and reports page (BUG-5,6)"
   ```
2. Push to main → Vercel auto-deploys
3. Verify at https://my.bebang.ph/dashboard/procurement

### Acceptance Criteria:
- [ ] my.bebang.ph procurement pages load correctly
- [ ] No NaN values on supplier list
- [ ] Reports page shows consistent badges

---

## TASK-7: E2E Verification (All 7 Bugs)

**Type:** TEST
**Owner:** qa-tester
**Priority:** HIGH
**Blocked by:** TASK-3, TASK-6

### Steps:
1. **API verification** (backend bugs):
   ```bash
   # BUG-1: Invoice has purchase_order
   curl get_invoices → check purchase_order field present

   # BUG-2: Payment has supplier
   curl get_payment_requests → check supplier field present

   # BUG-3: Received value works
   curl get_received_value_for_po?po_name=PO-2026-00040 → expect 200

   # BUG-4: Supplier has total_amount
   curl get_suppliers → check total_amount field present

   # BUG-7: PO detail has items
   curl get_purchase_order?po_name=PO-2026-00040 → check items array
   ```

2. **Browser verification** (frontend bugs):
   - Navigate to /procurement/invoices → Click PO link → Should go to valid PO page
   - Navigate to /procurement/payments → Click supplier → Should go to valid supplier page
   - Navigate to /procurement/suppliers → Verify no "NaN" values
   - Check sidebar badges → Should show "X pending" label
   - Navigate to /procurement/reports → Goods Receipt Log has "Coming Soon"
   - Navigate to /procurement/purchase-orders/PO-2026-00040 → Should show line items

3. **Regression check:** Verify existing features still work:
   - Dashboard KPIs load
   - Supplier CRUD works
   - PO approval chain visible
   - Payment 4-level flow visible

### Acceptance Criteria:
- [ ] All 7 bugs confirmed fixed
- [ ] No regressions in existing functionality
- [ ] Screenshots captured as evidence

---

## TASK-8: Update Procurement Module Plan

**Type:** DOC
**Owner:** plan-tracker (or lead)
**Priority:** LOW
**Blocked by:** TASK-7

### Steps:
1. Update `docs/plans/PROCUREMENT_MODULE_PLAN.md`:
   - Add audit findings to Section 9 (E2E Test Results)
   - Add new bug fixes to Section 10 (Deployment)
   - Update API endpoint count (63, not "20+")
   - Add Section 14: Feb 7 Audit & Bug Fixes
2. Archive audit report reference

### Acceptance Criteria:
- [ ] Plan reflects current state accurately
- [ ] Audit findings documented
- [ ] Bug fixes documented with resolution dates
