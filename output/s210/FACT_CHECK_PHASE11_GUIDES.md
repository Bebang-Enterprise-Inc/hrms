# Fact-check report — S210 Phase 11 guide pack

Date: 2026-04-21
Scope: `output/s210/guides/*.md` (6 files) + live `_Instructions` tabs in Sheets A + B.
Method: Layer 1 programmatic verification of all factual claims against
source-of-truth files.

---

## Summary

| Severity | Count | Details |
|---|---|---|
| Green (verified correct) | 16 claim categories | IDs, URLs, approval chain, schema |
| Yellow (defer but flag) | 1 | BIR 3-year retention (plan-stated, but may conflict with NIRC §235 10yr) |
| **Red (must fix)** | **2** | Finance handover date off-by-one-day; false Timestamp auto-fill claim |

---

## RED findings

### R1. Finance handover date wrong

**Location:** `guides/FINANCE_RECONCILIATION_GUIDE.md` — 3 occurrences.

- `**Audience:** Denise (takes over Finance 2026-04-27 after Juanna leaves)` — **WRONG**
- `_Version 2026-04-21 (S210 Phase 11 guide pack). Scheduled handover from Juanna 2026-04-27._` — **WRONG**
- Also in `SUPPLIER_ROLLOUT_GUIDE.md`? Let me re-grep: `escalation matrix` mentions nothing date-related. Safe.
- `IAN_DAILY_OPS_PLAYBOOK.md` does not reference Denise dates. Safe.

**Source of truth (`memory/finance-team-2026-04-15.md`):**

> **Juanna Alcober** (Bio 9001787, juanna@bebang.ph) — Finance Manager — resigned, last day **2026-04-27**. [...] **Denise Almario** (Bio 9000816, denise@bebang.ph) — Finance Supervisor — promoted to **finance lead effective 2026-04-28**.

Denise is effective **2026-04-28**, not 2026-04-27. Juanna's LAST DAY is 2026-04-27; Denise takes over the DAY AFTER.

**Fix:** change "takes over 2026-04-27" → "takes over 2026-04-28 (Juanna's last day is 2026-04-27)".

### R2. Timestamp auto-fill claim is false

**Location:**
- `guides/3PL_DOCK_QUICK_CARD.md` → "A. Timestamp | Now (auto-fills if you leave blank)"
- `guides/SHEET_INSTRUCTIONS_3PL.md` → "A. Timestamp (leave blank if you want auto; else type date+time)"
- Live `_Instructions` tabs in Sheets A + B (already pushed the wrong text)

**Actual behavior from `s210_master_handler.gs` line ~170-172:**

```javascript
const rowMs = new Date(tsRaw).getTime();
if (isNaN(rowMs) || rowMs <= lastSeen) continue;
```

If Timestamp is blank, `new Date('').getTime()` returns `NaN`, and the row
is SKIPPED entirely. No auto-fill happens — there's no auto-fill formula
in the sheet and no script hook. A blank Timestamp means the row is never
processed.

**Fix:** change to "Timestamp — Type the date+time of arrival (required; row is skipped if blank)".

Long-term fix option: add a Sheet-level script or simple formula (`=IF(B2<>"", IF(A2="", NOW(), A2), "")`) to auto-populate Timestamp when other columns are filled. Out of scope for this fact-check fix; noting for a follow-up.

---

## YELLOW findings

### Y1. BIR 3-year retention claim

**Location:** `guides/SUPPLIER_FAQ.md` → "Yes — paper SI is still required for BIR's 3-year retention rule."

**Plan source** (`docs/plans/2026-04-20-sprint-210-*.md` line ~89): "original paper SI must still arrive for BIR 3-year retention (not a payment gate)".

**Possible conflict:** NIRC Section 235 specifies 10-year retention of books of accounts and supporting records (5 years hard copy, 5 years electronic). The 3-year number may have come from a specific BIR issuance that applies to certain document types — but without a direct primary-source citation, this is unverified.

**Decision:** Defer to plan as authoritative working assumption. Flag for Ashish or Denise to verify against the actual BIR RR / RMC citation when they onboard. Keep guide wording as-is until authoritative source is produced.

---

## GREEN findings (verified correct — no changes needed)

| Claim | Source | Verdict |
|---|---|---|
| Sheet A ID `1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU` | `SHEET_IDS.json` | ✓ |
| Sheet B ID `10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw` | `SHEET_IDS.json` | ✓ |
| Sheet C ID `1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0` | `SHEET_IDS.json` | ✓ |
| Sheet D ID `1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As` | `SHEET_IDS.json` | ✓ |
| Form edit ID `1gyijOzmjXJHlyil7wraQ8xjmPMu0q1eoqUcjwHXogPg` | `SI_UPLOAD_FORM_ID.json` | ✓ |
| Form responder URI | `SI_UPLOAD_FORM_ID.json` | ✓ |
| Apps Script project ID `1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S` | `SHEET_IDS.json` | ✓ |
| GCP project `quiet-walker-475722-s2` | `CLOUD_SCHEDULER.json` | ✓ |
| 4 Scheduler jobs (s210-poll-all, s210-age-variance-hourly, s210-refresh-masters-06, s210-ceo-email-07) | `CLOUD_SCHEDULER.json` | ✓ |
| Scheduler location `asia-southeast1` | `CLOUD_SCHEDULER.json` | ✓ |
| SCM Chat space `spaces/AAQArCi8zjE` | `s210_master_handler.gs` line 32 | ✓ |
| Procurement Notif Chat space `spaces/AAQAYAYwPPk` | `s210_master_handler.gs` line 33 | ✓ |
| 16-col schema (no photos post-Phase-7) | `s210_master_handler.gs` COL_* constants | ✓ |
| BEI team emails (`ian@`, `jay@`, `cayla@`, `sam@`, `luwi@`, `mae@`, `denise@` @bebang.ph) | `SHEET_IDS.json` editors list | ✓ |
| Frappe URL `hq.bebang.ph` | `docs/BEI_CREDENTIALS.md` | ✓ |
| Approval chain (Luwi→Mae ≤₱1M, Luwi→Mae→Sam >₱1M) | Plan doc line 190 | ✓ |
| CFO seat vacant, Sam sole finance approver | `memory/finance-team-2026-04-15.md` | ✓ |
| EoPT Act RA 11976 + RR 7-2024 | Plan doc line 109 | ✓ |
| 7 inherited header fields (RR#, PO#, Supplier, SI#, Trucker, Plate, Received By) | `s210_master_handler.gs` HEADER_COLS | ✓ |
| 7 per-line fields never inherited (Material Code/Desc, Qty, UoM, ProdDate, ExpDate, Notes) | `s210_master_handler.gs` (exclusion by omission) | ✓ |

---

## Actions taken

After this report:

1. Patch `FINANCE_RECONCILIATION_GUIDE.md` (3 date corrections)
2. Patch `3PL_DOCK_QUICK_CARD.md` (Timestamp row text)
3. Patch `SHEET_INSTRUCTIONS_3PL.md` (Timestamp row text)
4. Re-run `push_instructions_tab.py` so live Sheet A + Sheet B `_Instructions` tabs reflect the fix
5. Commit + push to PR #665

Open follow-up (not blocking):

- Verify BIR paper-SI retention period (3yr vs 10yr per NIRC §235) with an authoritative RR citation. Probable owner: Denise after 2026-04-28 onboarding, or Ashish earlier if he has a clearer citation.
- Add a timestamp auto-populate Sheet formula to Sheets A + B so blank Timestamp doesn't silently skip the row. Out-of-scope for this guide-pack fix.
