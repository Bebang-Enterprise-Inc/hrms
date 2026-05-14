"""Phase 1 verification — machine-checkable assertions against the patched script."""
import sys, re, os

SRC = 'scripts/google_apps/s248_ap_view_hourly_sync_v37.gs'
if not os.path.exists(SRC):
    print(f'FAIL: source file {SRC} does not exist')
    sys.exit(1)

code = open(SRC, 'r', encoding='utf-8').read()

checks = {
    'seedFromDenisePaymentPlan_ defined':       'function seedFromDenisePaymentPlan_' in code,
    'mapDeniseToApStatus_ defined':             'function mapDeniseToApStatus_' in code,
    'DENISE_PP_ID constant':                    "const DENISE_PP_ID = '13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU'" in code,
    'Denise sheet ID present':                  '13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU' in code,
    'Reads tab "Suppliers w/o FD & Middleby"':  "'Suppliers w/o FD & Middleby'" in code,
    'Reads tab "Middleby"':                     "name: 'Middleby'" in code,
    'Reads tab "Forward Dynamics"':             "'Forward Dynamics'" in code,
    'Reads tab "Masterlist"':                   "'Masterlist'" in code,
    'SOURCE tag "Denise PP"':                   "'Denise PP'" in code,
    'SOURCE tag Disputed (Middleby)':           "'Denise PP - Disputed (Middleby)'" in code,
    'SOURCE tag Disputed (FD)':                 "'Denise PP - Disputed (FD)'" in code,
    'SOURCE tag Masterlist safety net':         "'Denise PP - Masterlist'" in code,
    'CATEGORY "Disputed - Eventually Payable"': "'Disputed - Eventually Payable'" in code,
    'CATEGORY "Supplier Payments"':             "'Supplier Payments'" in code,
    'WITH FINANCE fallback in status mapper':   "return 'WITH FINANCE'" in code,
    'PAID status mapping':                      "if (s === 'PAID') return 'PAID'" in code,
    'NO RFP YET mapping for On Hold':           "if (s === 'ON HOLD') return 'NO RFP YET'" in code,
    'CHECK READY mapping':                      "return 'CHECK READY'" in code,
    'FOR ONLINE PAYMENT mapping':               "return 'FOR ONLINE PAYMENT'" in code,
    'outstanding <= 0 filter':                  re.search(r'outstanding\s*<=\s*0', code) is not None,
    'Wired into seedNewInvoicesFromSources_':   'seedFromDenisePaymentPlan_(ss, fpmLookup, taxLookup, existingIndex, dryRun)' in code,
    'stats.denise_seed assignment':             'stats.denise_seed = deniseStats' in code,
    'logEvent for Denise seed':                 "'invoice_seeded_from_denise_pp'" in code,
    'Intra-Denise-run dedup logic':             'seenThisRun' in code,
    'BEI-FIN dedup logic':                      'beiFinNorm' in code,
    'Header at row 3 (index 2)':                'data[2]' in code,
    'NCOLS append width':                       'NCOLS' in code and '.setValues(values)' in code,
    'Suppliers SOA target tab':                 "newRowsByTab['Suppliers SOA']" in code,
}

passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f'Phase 1 verification: {passed}/{total} checks')
fails = []
for k, v in checks.items():
    status = 'OK  ' if v else 'FAIL'
    print(f'  [{status}] {k}')
    if not v: fails.append(k)

if fails:
    print(f'\nFAIL: {len(fails)} check(s) failed:')
    for f in fails:
        print(f'  - {f}')
    sys.exit(1)
print(f'\nPASS: all {total} checks passed')
sys.exit(0)
