# L3 Test Plan: S134 + S135 Procurement (Combined, Hardened)

**Sprint IDs:** S134, S135
**Type:** L3 Acceptance Testing (post-deploy, NO CORNER CUTTING)
**Test Script:** `scripts/testing/l3_s134_s135_procurement.mjs`

---

## ANTI-CORNER-CUTTING ENFORCEMENT (STRUCTURAL — NOT ADVISORY)

These are enforced by code in the test script, not by trust:

1. **All mutations UNDER TEST via browser button clicks** — Mae approval, CEO approval, Quick Receive, batch approve, invoice form submit, Create PR. Setup mutations (create supplier, create PO, submit for approval) use `page.evaluate(fetch POST)` in browser context with session cookies — explicitly allowed by L3 skill `api_used_for_setup: true`. Only `apiGET()` exists for read-only verification.
2. **Self-audit gate after EVERY scenario** — checks that form_submissions, state_verification, and screenshots were actually produced. If any check fails, result is auto-downgraded to `DEFECT-CORNER-CUT`.
3. **Values read, not existence checked** — `textContent()` reads actual text; `API GET` reads actual field values. Never `isVisible()` alone as proof of correctness.
4. **Defect reporting mandatory** — any bug found (in-scope or collateral) is written to `DEFECTS.md` with severity and sprint attribution.
5. **Fresh data per run** — every test creates new suppliers and POs with timestamps. Never reuses stale data.
6. **Login via /login only** — with cookie clearing before every login switch.
7. **Screenshots before AND after every mutation** — not just at success.
8. **No `PASS` without evidence** — self-audit checks that form_submissions array has entries for the scenario.

## Prerequisites

1. All 4 PRs merged and deployed:
   - hrms#374, hrms#375 (backend)
   - BEI-Tasks#269, BEI-Tasks#270 (frontend)
2. Playwright installed: `npm install playwright`
3. Test accounts available (below)
4. Production site accessible: https://my.bebang.ph

## Test Accounts

| Email | Password | Role | Used For |
|-------|----------|------|----------|
| test.hr@bebang.ph | BeiTest2026! | Procurement User | Create POs, suppliers, PRs, GRs |
| mae@bebang.ph | BeiTest2026! | Mae Approver | Approve POs via BROWSER button |
| sam@bebang.ph | 2289454 | CEO | CEO approval via BROWSER button |

## Execution

```bash
cd F:\Dropbox\Projects\BEI-ERP
node scripts/testing/l3_s134_s135_procurement.mjs
```

---

## L3 Scenarios (9 total)

### S134: Quick Receive + Auto-Invoice + PO Data Fixes (7 scenarios)

| # | Type | Scenario | Browser Actions | Expected | Self-Audit Checks |
|---|------|----------|-----------------|----------|-------------------|
| S134-L3-1 | happy | Quick Receive + Auto-Invoice dialog | Setup PO → Mae approve VIA BROWSER BUTTON → GR/new → select PO → upload doc → click "Received All as Ordered" → verify dialog → click "Create Invoice" → verify navigation | GR created. Dialog appears with "Create Invoice" button. Clicking navigates to /invoices/new?po=X&gr=Y | form_submissions has QR entry, Mae approval via browser confirmed, screenshots before+after |
| S134-L3-2 | adversarial | Partial Receive — QR hidden | Setup approved PO → GR/new → select PO → upload doc → modify received_qty to 7 (ordered 10) | "Received All as Ordered" button HIDDEN (variance detected). Regular Create GR still works. | qty modified in browser, button visibility checked, state verification recorded |
| S134-L3-3 | happy | PO warehouse default | Create PO WITHOUT ship_to in payload → verify via API GET + browser | ship_to defaults to "Stores - BEI". PO detail page shows it. | ship_to verified via API AND browser textContent, screenshot taken |
| S134-L3-4 | happy | CEO Approval full chain | Create new vendor PO → submit → Mae approve VIA BROWSER → verify Pending CEO → Sam login → approve VIA BROWSER BUTTON + confirmation dialog → verify Approved | Draft → Pending Mae → Pending CEO (badge visible) → Approved. Both Mae and CEO via browser buttons. | Mae browser click confirmed, CEO browser click confirmed, badge verified in browser, final status via API+browser |
| S134-L3-5 | happy | Auto-Invoice form fill + submit | Navigate to /invoices/new?po=X → fill invoice# → click Create → verify invoice created with correct amounts | Invoice created, amounts match PO. Invoice detail has correct grand_total. | Invoice form filled in browser, submit via browser button, amounts verified via API GET |
| S134-L3-6 | adversarial | Stale PO status check | GET PO-2026-00069 and PO-2026-00073 → read current status | Both Cancelled or have price_variance_override=1. If not, defect filed. | Both POs checked, status values read (not existence), defects filed if unclean |
| S134-L3-7 | happy | Batch approve + Frappe PO sync | Create 2 POs without ship_to → submit → Mae batch approve VIA BROWSER → verify Frappe PO sync with warehouse | Batch approve succeeds. Both POs have ship_to="Stores - BEI". No warehouse error. | Batch approve via browser button, ship_to verified on both POs |

### S135: Inventory Bridge + Supplier Intelligence (6 scenarios)

| # | Type | Scenario | Browser Actions | Expected | Self-Audit Checks |
|---|------|----------|-----------------|----------|-------------------|
| S135-L3-1 | happy | Stock Alerts + Create PR | Navigate /dashboard/procurement → verify widget → click "Create PR" link on an item | "Stock Alerts" widget visible. API returns items with days_remaining, daily_consumption, suggested_qty. Create PR navigates to /purchase-requisitions/new. | Widget via textContent, API verified, Create PR checked |
| S135-L3-2 | happy | Deliveries This Week | Same dashboard → verify widget | Widget visible. API returns deliveries with po_no, supplier_name, delivery_date, is_overdue fields. | Widget via textContent, response fields validated |
| S135-L3-3 | happy | Supplier Documents + detail | Dashboard → verify widget → navigate to supplier detail page | Widget visible. Supplier detail page shows expiry-related info (BIR/SEC/Permit). | Dashboard widget verified, supplier detail page checked |
| S135-L3-4 | adversarial | Auto-convert blocks invalid PR | POST auto-convert with non-existent PR name | Returns success=false or HTTP 400+. Does NOT crash with 500. | Tested with genuinely non-existent PR, response checked for error |
| S135-L3-5 | happy | Low Stock API threshold | GET low-stock with threshold 3, 7, 30 | count(3d) <= count(7d) <= count(30d). All items have days_remaining <= threshold. Response has all required fields. | Three thresholds tested, monotonicity verified, values checked not just existence |
| S135-L3-6 | adversarial | Empty state — no stock data | GET low-stock with non-existent warehouse | Returns empty items array, status 200. Dashboard shows graceful empty state. | Tested with non-existent warehouse, empty array verified, dashboard empty state checked |

---

## Evidence Files (MANDATORY before closeout)

```
output/l3/S134/
  form_submissions.json    ← MUST have: Quick Receive, Mae approval, CEO approval, invoice form fill, batch approve
  api_mutations.json       ← MUST have: Mae approve, CEO approve (marked "via browser button"), batch approve
  state_verification.json  ← MUST have: ship_to default, CEO pending badge, Approved status, stale PO check, invoice amounts, Frappe sync
  results.json             ← 7 scenarios with PASS/FAIL
  self_audit.json          ← 7 self-audits, all passed=true
  DEFECTS.md               ← Any bugs found (empty if none)
  artifacts/               ← Screenshots at every step

output/l3/S135/
  form_submissions.json    ← Create PR navigation (if items exist)
  api_mutations.json       ← Dashboard API GETs, auto-convert POST, empty state GET
  state_verification.json  ← Widget visibility, API responses, threshold filtering, supplier detail, empty state
  results.json             ← 6 scenarios with PASS/FAIL
  self_audit.json          ← 6 self-audits, all passed=true
  DEFECTS.md               ← Any bugs found
  artifacts/               ← Dashboard screenshots
```

## Defect Reporting

ALL bugs found during testing are reported in `DEFECTS.md`:

| Field | Values |
|-------|--------|
| Severity | BLOCKER, CRITICAL, MAJOR, MINOR |
| Type | IN-SCOPE (sprint bug) or COLLATERAL (discovered but outside sprint scope) |
| Sprint | Which sprint owns the fix |

Defects do NOT block PASS for the scenario that found them — they are reported separately for triage.

## After All Pass

```bash
git add -f output/l3/S134/ output/l3/S135/
git commit -m "test(S134+S135): L3 evidence — 13 scenarios"
git push
```

Then update both plan files to COMPLETED and SPRINT_REGISTRY.md.
