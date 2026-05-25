"""Phase 4a/4b/4c verification — source-of-truth redesign."""
import os, sys

V310 = 'scripts/google_apps/s256_ap_view_hourly_sync_v310.gs'
OUT = 'output/s256'

def main():
    errors = []
    src = open(V310, encoding='utf-8').read()

    # 4a assertions
    if 'PROCUREMENT_APP_ID' not in src:
        errors.append("PROCUREMENT_APP_ID const missing")
    if 'function seedFromProcurementApp_' not in src:
        errors.append("seedFromProcurementApp_ function missing")
    if "'Procurement App'" not in src:
        errors.append("'Procurement App' SOURCE assignment missing")
    if 'seedFromProcurementApp_(ss' not in src and 'procStats = seedFromProcurementApp_' not in src:
        errors.append("seedFromProcurementApp_ not wired into doRefreshAllTabs_v3_")

    # 4b assertions
    if 'denise_pp_seed_disabled' not in src:
        errors.append("denise_pp_seed_disabled const missing")
    if 'seed_disabled: true' not in src:
        errors.append("early-exit with seed_disabled missing")
    if not os.path.exists(os.path.join(OUT, 'payment_plan_mirror_cutover_v2_runbook.md')):
        errors.append("Cutover runbook missing")

    # 4c assertions
    if 'HO_OPENING_BALANCE_ID' not in src:
        errors.append("HO_OPENING_BALANCE_ID const missing")
    if 'function seedHoOpeningBalanceOnce_' not in src:
        errors.append("seedHoOpeningBalanceOnce_ function missing")
    if "'_ho_opening_loaded'" not in src:
        errors.append("Idempotency flag tab logic missing")

    if errors:
        print("PHASE 4 VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PHASE 4 (a+b+c) VERIFY: ALL PASS")
    return 0

if __name__ == '__main__':
    sys.exit(main())
