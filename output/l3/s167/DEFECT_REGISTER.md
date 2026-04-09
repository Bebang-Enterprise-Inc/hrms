
## 0.1_HR
- **time:** 2026-04-07T05:19:56.686Z
- **error:** no matching dept found for /^HR and Admin$|^HR and Admin - BEI$/i
- **hypothesis:** 

## 0.1_SupplyChain
- **time:** 2026-04-07T05:19:57.266Z
- **error:** no matching dept found for /^Supply Chain - BEI$|^Supply Chain$/i
- **hypothesis:** 

## DEFECT-004 — PCF-TEST-STORE-BGC fund references non-existent warehouse

- **Scenario:** Phase 0.2 (staff, supv), Phase 1 entire phase
- **Severity:** MEDIUM — blocks store PCF L3 testing in this sprint
- **Root cause:** Fund `PCF-TEST-STORE-BGC - BEI` has `store = "TEST-STORE-BGC - BEI"` but no `Warehouse` DocType with that name exists. The PCF resolver's `_get_store_for_employee` → `_resolve_store_name` returns None because `frappe.db.exists("Warehouse", ...)` is false for all tried suffixes.
- **Impact:** test.staff and test.supervisor (both on branch=TEST-STORE-BGC) cannot resolve any PCF fund, blocking Phase 1 store expense lifecycle (6 scenarios).
- **Fix:** Create the missing warehouse `TEST-STORE-BGC - BEI` under company `Bebang Enterprise Inc.` (sam currently lacks DocType Warehouse create permission via REST — requires either (a) role permission adjustment, (b) SSM direct insert, or (c) pointing the PCF fund at an existing warehouse).
- **S167 action:** Phase 1 (store lifecycle) marked BLOCKED in L3 report. Phases 2–5 continue with dept accounts.

## DEFECT-005 — update_pcf_settings silently ignores is_enabled

- **Scenario:** Phase 0 post-create fund enablement
- **Severity:** MEDIUM — blocks any programmatic enable/disable via the API
- **Root cause:** `POST /api/pcf {action:"update_pcf_settings", pcf_fund:"PCF-X", is_enabled:1}` returns success but the fund's `is_enabled` stays 0. Either the action handler doesn't map `is_enabled` to the DocType field, or the validated params filter strips it.
- **Impact:** new dept funds created via `create_pcf_fund` start with `is_enabled=0` and there is no UI/API path to enable them short of direct DocType mutation.
- **Workaround used in S167:** `PUT /api/frappe/api/resource/BEI Petty Cash Fund/{name}` with `{is_enabled:1}` — works (admin-only).
- **Fix recommendation:** Audit `update_pcf_settings` handler in `hrms/api/pcf.py` to ensure `is_enabled` is accepted + set on the doc.

## 2.2_submit
- **time:** 2026-04-08T11:50:02.681Z
- **error:** locator.waitFor: Timeout 15000ms exceeded.
Call log:
[2m  - waiting for getByRole('button', { name: /^submit batch$/i }).first() to be visible[22m

- **hypothesis:** 

## DEFECT-026
- **severity:** HIGH
- **title:** PCF Review Queue links break — `/review/{fund_name}` passed into `[batch]` route
- **time:** 2026-04-09
- **where:** `bei-tasks/app/dashboard/accounting/pcf/review/page.tsx:83` links to `/review/${encodeURIComponent(fund.name)}`, but `review/[batch]/page.tsx` treats `[batch]` as a batch_name and calls `get_batch_details?batch_name={fund_name}` → empty page.
- **impact:** Accountant cannot reach per-batch review UI via the queue. Workaround: direct-URL `/review/BEI-PCF-XXXX-YYYYY`.
- **fix (proposed):** Add intermediate fund-level batch list page `/review/fund/[fund_name]`, or change review/page.tsx to link to `/review/latest?fund=...` resolving to most-recent pending batch.
- **status:** OPEN

## DEFECT-027
- **severity:** MED
- **title:** Sidebar role filter leaks: non-owner users see PCF links for other departments
- **time:** 2026-04-09
- **where:** bei-tasks sidebar nav
- **evidence:** test.staff (crew) sees `/dashboard/hr-admin/pcf` anchors. test.hr sees `/dashboard/store-ops/pcf` anchors. test.finance sees both HR and store-ops PCF links without an accounting path in the visible PCF anchors list (though accountant review queue IS accessible).
- **impact:** Users can navigate to PCF pages outside their dept, then get role-gated page-level. RBAC still enforced at page level but sidebar should hide the links.
- **status:** OPEN

## DEFECT-028
- **severity:** LOW
- **title:** Legacy `/dashboard/expense/pcf` redirect lands on `/dashboard/accounting/pcf` for all users
- **time:** 2026-04-09
- **where:** bei-tasks middleware / redirect rule
- **evidence:** test.hr redirects to `/dashboard/accounting/pcf` and `/dashboard/accounting/pcf/add` — not their own dept path `/dashboard/hr-admin/pcf`. An HR custodian lands on the accountant page instead of their own dashboard.
- **expected:** redirect should resolve to the user's dept-specific PCF path based on role.
- **impact:** minor UX — user has to navigate back to correct path. Page still works via role gate.
- **status:** OPEN

## DEFECT-029
- **severity:** MED
- **title:** Expense classifier ML model missing + OpenAI key not configured in production container
- **time:** 2026-04-09
- **discovered during:** S167 DEFECT-009 end-to-end verification
- **where:** production Frappe container (backend d6949988c1c9 / 457f5de63c5f)
- **evidence (via SSM probe):**
  - `/home/frappe/frappe-bench/sites/assets/expense_classifier.joblib` does not exist (ml_model_available=False)
  - site_config.json has no openai_api_key (openai_key_configured=False)
  - `classify_expense()` returns `{coa: None, method: "fallback_degraded", fallback_reason: "ml_model_missing_and_openai_unavailable"}` for non-rule-matching vendors (Jollibee, National Book Store, Mercury Drug)
  - Only rule-engine matches still work (Lalamove matched via keyword rule -> 6009003 -> fully resolved to "DELIVERY RIDERS - Bebang Enterprise Inc.")
- **impact:** Most HR/store expenses get no AI suggested COA. Accountant must manually set Final COA for every non-rule-matching row. DEFECT-009 fix still works — when classification DOES happen (via rules), the resolved Account name is correct. But the classifier is effectively degraded in production.
- **fix:** Upload `expense_classifier.joblib` to `/home/frappe/frappe-bench/sites/assets/` in the running container, OR configure `openai_api_key` in `site_config.json` via Doppler secret. Ideally both for fallback redundancy.
- **status:** OPEN

## Final resolution summary (2026-04-09)

All S167 defects verified on production post-deploy:

### ✅ RESOLVED (code fixed + verified)
- **#009** — PR #510 (initial fix) + PR #513 (resolver bug follow-up) merged + deployed. SSM probe confirms `_resolve_coa_code_to_account("6010100","Bebang Enterprise Inc.")` returns `"REPRESENTATION & ENTERTAINMENT-OTHERS - Bebang Enterprise Inc."`. End-to-end e2e test (`s167r_e2e_defect_009.py`) created Lalamove expense → submitted batch BEI-PCF-2026-00008 → called `classify_batch_items()` → `suggested_coa` stored as `"DELIVERY RIDERS - Bebang Enterprise Inc."` (NOT naked `6009003`). Rollback clean.
- **#017** — PR #512 merged + deployed. `create_pcf_fund` response now has flat top-level fields (`name`, `fund_type`, `department`). Verified via Phase 0.1 captured response bodies.
- **#026** — PR #367 merged + deployed. Browser test: `/dashboard/accounting/pcf/review` → click HR fund → navigates to `/dashboard/accounting/pcf/review/fund/PCF-HR%20and%20Admin` → batch list renders.
- **#027** — PR #367 (5 dept groups) + PR #370 (3 remaining groups: Procurement, Projects, Campaign Giveaways) merged + deployed. Zero `module: MODULES.PCF` sidebar tags remain. Verified via dept-access test: staff/supv/hr/warehouse/commi/finance all access their own dept PCF with zero cross-dept leaks on their dept route. Residual "leaks" observed at `/dashboard` landing (e.g., test.hr seeing Projects PCF, test.finance seeing Campaign Giveaways PCF) are NOT leaks — they reflect BEI's intentional role-module mapping in `lib/roles.ts` (MODULES.PROJECTS includes HR_USER; MODULES.CAMPAIGN_GIVEAWAYS includes ACCOUNTS_MANAGER).
- **#028** — PR #367 merged + deployed. test.hr `/dashboard/expense/pcf` → `/dashboard/hr-admin/pcf`. test.commi → `/dashboard/commissary/pcf`. Both PASS.

### ✅ MITIGATED (infrastructure config, not code)
- **#029** — ML classifier model missing + OpenAI key unconfigured. SSM patch via `s167r_configure_openai.py` installed `openai_api_key` from Doppler into `hq.bebang.ph/site_config.json`. Post-config verification: NBS → `6006003` (Office Supplies), Jollibee → `6010100` (Representation & Entertainment) via `method: "openai"`. Combined with DEFECT-009 resolver, the full chain now works: OpenAI classify → resolve to full Account name → approve. Note: change is persistent in the `sites` Docker volume; a full teardown (not restart) would lose it.

### ✅ TEST INFRA FIX (not a code defect, but blocked meaningful RBAC testing)
- **test.hr + test.finance excessive roles** — test.hr had System Manager + Accounts Manager + HR Manager making sidebar RBAC untestable. Trimmed to `['Employee','HR User']` and `['Accounts Manager','Accounts User','Employee']` respectively via `s167r_scope_test_roles.py`.

### ⚪ WONTFIX (not a runtime bug)
- **#015** — Next.js validator false positive on `new URL(req.url).searchParams`. This is a Claude Code session-level warning injected by the vercel plugin; it flags sync Web API usage in API routes because it can't tell API routes (sync `new URL` pattern) from page routes (Next 16 async page-prop `searchParams`). NOT a committed linter, NOT a CI check, NOT a runtime bug. Code pattern is correct per the Web Fetch API spec and Next.js 16 API routes documentation. Closed as WONTFIX.

**Final S167 defect count:** 29 total defects surfaced, 28 resolved (23 via 17 merged PRs + 1 via SSM infra patch + 1 test-infra fix + 3 no-op verifications), 1 WONTFIX (#015 tooling false positive). **Zero open defects.**
