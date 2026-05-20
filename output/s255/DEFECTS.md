# S255 — Defect Register

**Sprint:** S255
**Status:** ✅ NO DEFECTS BLOCKING DEPLOY
**Last reviewed:** 2026-05-20 PHT

## Resolved during execution (no longer blocking)

| ID | Phase | Description | Resolution |
|---|---|---|---|
| R1 | 3 | Row 7 banner column count off-by-one (range A7:N7 had 15 data elements) | Fixed to A7:O7 in both v3.9 + Python; v3.9 line ~1059 patched |
| R2 | 3 | CAPEX header at row 19 (not 17 like other entry tabs) | HEADER_ROWS map added to both v3.9 + Python — handles per-tab variance |
| R3 | 8 | UnicodeEncodeError on print('writer → commenter') on Windows console | Drive API call succeeded BEFORE the print; verified via re-fetch (Roberose=commenter live). Log corrected. |

## Flagged but non-blocking (deferred to S256 or Sam decision)

| ID | Phase | Description | Recommendation |
|---|---|---|---|
| D1 | 2.3 | 2-3 ambiguous Intercompany rows use phrasing the strict regex misses (e.g. "Fund Transfer From UB - Snack House to BEI", "Trasnfer of Fund" typo, "Transfer to BPI for check clearing") | Sam reviews `intercompany_ambiguous.json` (25 rows total: 18 correctly-excluded govt-remittance + 7 phrasing-mismatch). Can opt to migrate manually or amend regex in S256 |
| D2 | 4 | 7 non-Denise dupe-groups remain on Suppliers SOA (FPM × legacy SOA dupes) | Out of S255 scope (plan was "delete Denise PP-sourced dupes; keep legacy/FPM"). Sam can opt for stricter dedup in S256 |
| D3 | 5 | Plan v1.1 estimated 12 stranded "Invoice No. X" rows but current data has 0 | Plan estimate was stale; v3.9 detection is forward-looking. 6 Denise PP - Masterlist 3M Dragon rows exist with valid invoice numbers — Sam can opt to retag those to Denise PP - Manual in S256 if procurement-bypass tracking is needed |
| D4 | 8 | joevic@bebang.ph identity unknown (writer on Denise PP) | Joevic inquiry draft prepared (`joevic_inquiry_draft.md`); send to Denise/James when ready, then update ACL based on response |
| D5 | 8 | bea.garcia.intern@bebang.ph writer access (intern role) | Verify if intern needs writer vs commenter; downgrade if just read/comment |
| D6 | 8 | 6 NEW BEI writers added to Denise PP since plan v1.0 (drew@, liezel@, maika@, marco@, julius@ reader, bea.garcia.intern@) | Best-judgment kept as-is; presumably Sam/Denise authorized. Sam can selectively review |
| D7 | 9a | Bridge has 5 users on FPM (more than expected; not on Sam's radar in plan) | Investigate / confirm — could be DD-related setup pre-S255 or unauthorized. Sam to verify |
| D8 | 9a | Bridge has NO access to AP Master / Compliance / Bank Balances / Cashflow / PCM | For DD readiness, Sam should grant READER on FPM (already), Compliance, Bank Balances. PCM + Cashflow optional |
| D9 | 7 | `payment_plan_mirror_disabled` is a hardcoded const (not PropertiesService) | Per plan v1.1, intentional — using PropertiesService would have required deploying v3.9 first which has chicken-and-egg with the mirror itself. Acceptable; toggle later via S256 redeploy or PropertiesService migration |

## Did not occur (per plan)

- No L3 form submissions / API mutations (this is a script deploy, not a UI feature)
- No `tabEmployee` / Frappe data changes (canonical_scope: none)
- No Test Employee / test Bio ID work (no test data created)

## Sprint signoff status

✅ ZERO DEFECTS BLOCKING PRODUCTION OR MERGE.

All 9 deferred items (D1-D9) are either out-of-scope amendments for future sprints OR pending Sam-only decisions that don't block S255 closure.
