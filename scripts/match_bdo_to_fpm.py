"""Match BDO bank transactions to FPM RFPs by check number to determine clearance."""
import re
import pandas as pd

bdo = pd.read_csv('CEO/CashFlow/bdo_statements/all_bdo_transactions.csv')
fpm = pd.read_csv('CEO/CashFlow/payroll/_fpm_rfp_summary.csv')
fpm.columns = [c.strip() for c in fpm.columns]

# ----- Clean BDO -----
bdo['debit'] = pd.to_numeric(bdo['debit'], errors='coerce').fillna(0)
bdo['credit'] = pd.to_numeric(bdo['credit'], errors='coerce').fillna(0)
bdo['check_clean'] = bdo['check_number'].astype(str).str.strip().str.lstrip('0')
# Exclude placeholder zero checks
bdo = bdo[bdo['check_clean'] != '']

# Classify debits by description type
def txn_type(desc):
    d = str(desc).upper()
    if 'OUS TO' in d or 'OUS DR' in d or 'CM' in d and 'OUS' in d:
        return 'INTERCO TRANSFER'
    if 'LOCAL REGULAR INWARD' in d or 'REGIONAL REGULAR' in d:
        return 'INWARD (deposit)'
    if 'CREDIT MEMO' in d:
        return 'CREDIT MEMO'
    if 'CHEQUE ENCASHMENT' in d:
        return 'CHEQUE CASHED'
    if 'DEBIT MEMO' in d:
        return 'DEBIT MEMO (check)'
    if 'INTEREST' in d:
        return 'INTEREST'
    if 'TRANSFER' in d:
        return 'TRANSFER (intercomp.)'
    return 'OTHER'

bdo['txn_type'] = bdo['description'].apply(txn_type)

print('BDO DEBIT txn types (outflows):')
out = bdo[bdo['debit'] > 0]
for t, grp in out.groupby('txn_type'):
    print(f'  {t:30s}  {len(grp):4d} txns  ₱{grp["debit"].sum():>14,.2f}')

# ALL debits with non-zero check numbers (includes intercompany but we'll filter later with FPM join)
supplier_checks = out[(out['debit'] > 0) & (out['check_clean'] != '') & (out['check_clean'] != '0')].copy()
print(f'\\n=== ALL DEBIT CHECKS (any type): {len(supplier_checks)} (₱{supplier_checks["debit"].sum():,.2f}) ===')

# ----- Clean FPM -----
fpm['Amount Due'] = pd.to_numeric(fpm['Amount Due'], errors='coerce').fillna(0)
fpm['check_clean'] = fpm['Check No./Ref No.'].astype(str).str.strip().str.lstrip('0')
fpm_with_check = fpm[(fpm['check_clean'] != '') & (fpm['check_clean'] != 'nan')]
print(f'\\nFPM RFPs with check numbers: {len(fpm_with_check)}')
print('FPM status breakdown for checks:')
for st, c in fpm_with_check['Status'].value_counts().items():
    print(f'  {st}: {c}')

# ----- Match by check number -----
merged = supplier_checks.merge(
    fpm_with_check[['check_clean', 'RFP NO.', 'Payee', 'Particulars', 'Amount Due', 'Status', 'Category', 'Processed Date']],
    on='check_clean', how='left', suffixes=('_bdo', '_fpm'),
)

matched = merged[merged['RFP NO.'].notna()]
unmatched = merged[merged['RFP NO.'].isna()]

print(f'\\n=== MATCH RESULTS ===')
print(f'  BDO supplier checks:          {len(supplier_checks)}')
print(f'  Matched to FPM RFP:           {len(matched)} ({len(matched)/len(supplier_checks)*100:.1f}%)')
print(f'  Unmatched (not in FPM):       {len(unmatched)}')

if len(matched) > 0:
    print('\\nSample matched (top 10 by debit):')
    for _, r in matched.sort_values('debit', ascending=False).head(10).iterrows():
        amt_match = '✓' if abs(r['debit'] - r['Amount Due']) < 1 else 'X'
        print(f'  {r["date"]}  chk {r["check_clean"]:<10}  ₱{r["debit"]:>11,.2f}  FPM ₱{r["Amount Due"]:>11,.2f} {amt_match}  {str(r["Payee"])[:35]}')

    # Amount agreement
    amt_match_count = (abs(matched['debit'] - matched['Amount Due']) < 1).sum()
    print(f'\\nAmount agreement: {amt_match_count}/{len(matched)} ({amt_match_count/len(matched)*100:.1f}%)')

    # Save matched/unmatched/full
    matched.to_csv('CEO/CashFlow/bdo_statements/matched_bdo_to_fpm.csv', index=False)
    unmatched.to_csv('CEO/CashFlow/bdo_statements/unmatched_bdo_checks.csv', index=False)
    print('\\nSaved: CEO/CashFlow/bdo_statements/matched_bdo_to_fpm.csv')
    print('Saved: CEO/CashFlow/bdo_statements/unmatched_bdo_checks.csv')

# ----- Flip: FPM checks NOT in BDO (outstanding/uncleared) -----
fpm_check_set = set(fpm_with_check['check_clean'])
bdo_check_set = set(supplier_checks['check_clean'])
fpm_uncleared = fpm_with_check[~fpm_with_check['check_clean'].isin(bdo_check_set)]
fpm_cleared = fpm_with_check[fpm_with_check['check_clean'].isin(bdo_check_set)]
print(f'\\n=== CHECK CLEARANCE STATUS (from FPM perspective) ===')
print(f'  FPM checks CLEARED in BDO:    {len(fpm_cleared)} (₱{fpm_cleared["Amount Due"].sum():,.2f})')
print(f'  FPM checks NOT in BDO:        {len(fpm_uncleared)} (₱{fpm_uncleared["Amount Due"].sum():,.2f})')

fpm_uncleared[['RFP NO.', 'check_clean', 'Payee', 'Particulars', 'Amount Due', 'Status', 'Processed Date']].to_csv(
    'CEO/CashFlow/bdo_statements/fpm_uncleared_checks.csv', index=False
)
print('Saved: CEO/CashFlow/bdo_statements/fpm_uncleared_checks.csv')
