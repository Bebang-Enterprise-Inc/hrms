"""Cross-check BDO-cleared checks against AP status.

Question: Which BDO-cleared checks are still showing as LIABILITY in AP sheets?
If a check cleared in bank but AP still shows Check Released / In Pipeline, we can
reclassify to Paid → reduces liability by that amount.
"""
import pandas as pd

# BDO matched to FPM (202 rows)
matched = pd.read_csv('CEO/CashFlow/bdo_statements/matched_bdo_to_fpm.csv')
matched['debit'] = pd.to_numeric(matched['debit'], errors='coerce').fillna(0)
matched['Amount Due'] = pd.to_numeric(matched['Amount Due'], errors='coerce').fillna(0)

print(f'BDO-cleared checks matched to FPM: {len(matched)}')
print(f'Total debit (BDO): ₱{matched["debit"].sum():,.2f}')
print(f'Total amount (FPM): ₱{matched["Amount Due"].sum():,.2f}')

# FPM status breakdown of BDO-cleared checks
print(f'\\n=== BDO-CLEARED CHECKS BY FPM STATUS ===')
status_summary = matched.groupby('Status').agg(
    count=('Amount Due', 'count'),
    total_amt=('Amount Due', 'sum'),
).sort_values('total_amt', ascending=False)
print(status_summary.to_string())

# The ones still flagged as liability in FPM (not yet Paid/Cleared)
still_liability = matched[matched['Status'] != 'Paid/ Cleared']
print(f'\\n=== CHECKS CLEARED IN BDO BUT NOT YET "PAID" IN FPM ===')
print(f'Count: {len(still_liability)}')
print(f'Total amount: ₱{still_liability["Amount Due"].sum():,.2f}')

if len(still_liability) > 0:
    print(f'\\nBreakdown by current FPM status:')
    for st, grp in still_liability.groupby('Status'):
        print(f'  {st}: {len(grp)} checks, ₱{grp["Amount Due"].sum():,.2f}')

    print(f'\\nTop 15 by amount:')
    for _, r in still_liability.sort_values('Amount Due', ascending=False).head(15).iterrows():
        print(f'  {r["date"]}  chk {r["check_clean"]:<10}  ₱{r["Amount Due"]:>11,.2f}  [{r["Status"]}]  {str(r["Payee"])[:35]}')

# Now cross-check against consolidated_ap.csv which builds the "outstanding" liability
ap = pd.read_csv('CEO/CashFlow/intercompany_gl/consolidated_ap.csv')
ap['outstanding'] = pd.to_numeric(ap['outstanding'], errors='coerce').fillna(0)

print(f'\\n\\n=== CONSOLIDATED_AP.CSV STATUS DISTRIBUTION ===')
status_ap = ap.groupby('status').agg(
    count=('outstanding', 'count'),
    total_out=('outstanding', 'sum'),
).sort_values('total_out', ascending=False)
print(status_ap.to_string())

# Cross-join: BDO cleared checks, look for matching RFP in consolidated_ap
# consolidated_ap has 'rfp_no' column. Match matched['RFP NO.'] to ap['rfp_no']
matched['rfp_clean'] = matched['RFP NO.'].astype(str).str.strip()
ap['rfp_clean'] = ap['rfp_no'].astype(str).str.strip()

# Look for RFPs in AP that still show outstanding > 0 but BDO says cleared
bdo_rfps = set(matched[matched['Status'] != 'Paid/ Cleared']['rfp_clean'])
ap_matches = ap[ap['rfp_clean'].isin(bdo_rfps) & (ap['outstanding'] > 0)]
print(f'\\n=== AP INVOICES STILL SHOWING OUTSTANDING BUT CHECK CLEARED IN BDO ===')
print(f'Count: {len(ap_matches)}')
print(f'Total outstanding in AP: ₱{ap_matches["outstanding"].sum():,.2f}')

if len(ap_matches) > 0:
    print(f'\\nBy AP status:')
    for st, grp in ap_matches.groupby('status'):
        print(f'  {st}: {len(grp)} invoices, ₱{grp["outstanding"].sum():,.2f}')

# FINAL ANSWER — total liability that can be cleaned up
print(f'\\n' + '=' * 70)
print('ANSWER: LIABILITY REDUCTION OPPORTUNITY')
print('=' * 70)
# 1. FPM updates: checks cleared in BDO but FPM still not "Paid"
fpm_reduction = still_liability['Amount Due'].sum()
print(f'\\nFROM FPM RFP Summary:')
print(f'  BDO-cleared checks w/ FPM status != "Paid/Cleared": {len(still_liability)}')
print(f'  Total amount: ₱{fpm_reduction:,.2f}')
# 2. AP (consolidated) updates: invoices with outstanding > 0 but check cleared
ap_reduction = ap_matches['outstanding'].sum()
print(f'\\nFROM consolidated_ap.csv (liability ledger):')
print(f'  Invoices with outstanding > 0 but check cleared: {len(ap_matches)}')
print(f'  Potential liability reduction: ₱{ap_reduction:,.2f}')
print(f'\\nNOTE: Some overlap possible. Actual reduction ≈ ₱{max(fpm_reduction, ap_reduction):,.2f}')
print(f'      → Current AP ₱90.8M - ₱{max(fpm_reduction, ap_reduction)/1e6:.2f}M = ~₱{(90_821_404 - max(fpm_reduction, ap_reduction))/1e6:.2f}M true AP')

# Save for update
still_liability.to_csv('CEO/CashFlow/bdo_statements/checks_to_mark_cleared.csv', index=False)
ap_matches.to_csv('CEO/CashFlow/bdo_statements/ap_invoices_to_clear.csv', index=False)
print(f'\\nSaved: CEO/CashFlow/bdo_statements/checks_to_mark_cleared.csv')
print(f'Saved: CEO/CashFlow/bdo_statements/ap_invoices_to_clear.csv')
