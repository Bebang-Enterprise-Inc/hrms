# S168 — L3 Handoff Prompt

**Status:** S168 code is merged + deployed across hrms (PR #482 + #484) and bei-tasks (PR #351). Runtime prerequisites are NOT yet satisfied — see below. L3 acceptance testing must run AFTER runtime prereqs are complete, in a fresh Claude Code session per S099 rule.

## Branch / commit anchors

| Repo | Branch | Final merged commit | PR(s) |
|------|--------|---------------------|-------|
| hrms | production | 4a350a1c2 | #482 + #484 |
| bei-tasks | main | (post-#351) | #351 |

## RUNTIME PREREQS — must run before L3 (Sam owns these)

```bash
# 1. bench migrate — registers 14 Custom Fields + 8 BEI Settings fields
bench --site hq.bebang.ph migrate

# 2-7. Seed scripts in this exact order (each idempotent, each writes audit JSON to output/s168/)
python scripts/s168_seed_gl_accounts.py            # 4000100 + 4000101 - BKI
python scripts/s168_seed_vat_template.py           # BKI Output VAT 12% Sales
python scripts/s168_seed_customer_group.py         # BKI Store group
python scripts/s168_seed_customers.py              # 35 customers from S037 + TIN/RDO from ENTITY_TIN_RDO
python scripts/s168_seed_cost_centers.py           # Stores → JV / MF / FF → {store} - BKI
python scripts/s168_configure_bei_settings.py      # markup % + VAT template + income account + incoterm
```

After all 7 steps, re-run `python scripts/s168_l1_live.py` and `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/RUNTIME_PREREQS_AUDIT.md` checks — all should now PASS.

## L3 prompt (paste into a fresh session)

```
Run /l3-v2-bei-erp for sprint S168.

Plan: docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md
Branches: s168-bki-store-sale-billing-on-delivery (hrms #482 + #484), s168-bki-store-sale-billing-on-delivery (bei-tasks #351)
Deploy commits: hrms 4a350a1c2 / bei-tasks main HEAD post-#351

L3 Scenarios to execute (from plan + R2-C8 + Phase 11):
1. JV store — happy path: commissary fulfillment → draft SI created with 2.75% markup + 12% VAT, store accepts DR → SI submits with DR No., GL entries land on per-store cost center
2. Managed Franchise store — happy path: same flow with 8% markup
3. Full Franchise store — happy path: same flow with 8% markup
4. Partial rejection: store marks With Issues → SI submits with received_qty minus rejected, not expected_qty (row-level aggregation per R1 Phase 3.1)
5. Full rejection: store rejects everything → SI stays Draft → appears in Billing Holds dashboard
6. Billing hold release: from /dashboard/accounting/billing-holds, click Release → SI submits
7. Billing hold reject: click Reject with reason → SI cancelled, audit logged
8. Billing hold reassign: click Reassign Customer → SI customer changes
9. Credit note: submitted SI → "Request Credit Note" button (visible to Accounts Manager / SCM) → CreditNoteModal → submit return SI → original SI shows credit note link
10. Logistics fee: store accepts DR → BEI Billing Schedule row auto-created (Phase 10 fix from PR #484) → Finance approves → fee SI created with 12% VAT
11. EWT toggle (negative test): default OFF, no EWT line on SI; flip to ON in BEI Settings → next SI includes EWT deduction row
12. Stock Entry cancel: cancel SE that produced a Draft SI → orphan Draft SI is deleted (PR #484 fix)
13. Per-store P&L: query GL Entry by cost center after several SIs → entries land on {store} - BKI cost center, NOT BKI default (PR #484 fix)
14. Naming series: if BEI Settings.bki_sales_naming_series is set, new SI uses that prefix
15. Permission: non-SCM user cannot see "Request Credit Note" button on receiving page

Evidence files to produce:
- output/l3/s168/form_submissions.json   (Phase 11 credit note modal, billing hold actions, DR input submission, etc.)
- output/l3/s168/api_mutations.json      (every POST/PATCH/PUT API call with response status)
- output/l3/s168/state_verification.json (before/after state for SI submission, GL entries, BEI Billing Schedule rows, custom field values)
- output/l3/s168/si_gl_entries.json      (GL entry dump per submitted SI to prove cost center + VAT account + income account)

Test accounts: memory/testing-accounts.md
- test.scm@bebang.ph or test.accounts@bebang.ph for billing-holds + credit notes
- test.store@bebang.ph for receiving DR input
- Any commissary user for fulfillment

After all scenarios pass:
1. git add -f output/l3/s168/ && git commit -m "test(S168): L3 evidence — 15 scenarios PASS"
2. Push the L3 evidence (new branch off production: test/s168-l3-evidence)
3. Update docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md YAML status to COMPLETED
4. Update docs/plans/SPRINT_REGISTRY.md S168 row to COMPLETED
```

## Known issues to expect during L3

- **Phase 15 same-company reclassification** is dead code on production. `reverse_same_company_reclassification_je` exists but the forward `_create_same_company_reclassification_je` does not. If Finance has decided BEI→BEI stays as straight stock transfer (no JE), the reverse helper should be deleted. If Finance wants the JE, the forward helper needs to be implemented in a follow-up PR. **Do NOT include Phase 15 in L3 scenarios until this is resolved.**
- **Phase 3 verify-script grep bug** — `phase3()` greps `commissary.py` for `_compute_si_row_qty_from_receiving` but the function lives in `store.py:7354`. Verify-script will FAIL Phase 3 even though code is correct. Manual grep confirms presence.

## Closeout artifacts in this run

- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/RUN_STATUS.json` — current canonical state
- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/SCOPE_WARNING.md`
- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/AUDIT_COMPLETENESS.md` — first round audit (found 4 CRITICAL gaps)
- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/AUDIT_ORCHESTRATOR.md` — orchestrator self-audit (Grade D)
- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/AUDIT_FINAL.md` — post-#484 audit (CRITICAL #1-4 verified fixed)
- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/L1_LIVE_REPORT.md` — initial L1 (15/18 PASS, 3 FAIL = custom fields not synced)
- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/L2_LIVE_REPORT.md` — frontend L2 (2 PASS / 0 FAIL / 2 PARTIAL)
- `data/_CLEANROOM/agent_runs/2026-04-07_s168-bki-store-sale-billing-on-delivery/RUNTIME_PREREQS_AUDIT.md` — 0/7 PASS until Sam runs migrate + seeds
- `output/s168/SESSION_A_COMPLETE.flag` — Session A sentinel (R2-C6)
- `output/s168/HANDOFF_FOR_L3.md` — this file
- `output/s168/L1_LIVE_RESULTS.json`, `RUNTIME_PREREQS_RESULTS.json`
