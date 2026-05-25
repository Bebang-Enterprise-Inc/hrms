"""Phase 5 verification — bypass 3PL auto-tag."""
import os, sys, json

V310 = 'scripts/google_apps/s256_ap_view_hourly_sync_v310.gs'
OUT = 'output/s256'

def main():
    errors = []
    src = open(V310, encoding='utf-8').read()

    if 'BYPASS_3PL_PATTERNS' not in src:
        errors.append("BYPASS_3PL_PATTERNS const missing")

    patterns_needed = ['Dragon', 'Pinnacle', 'Royal', 'Coolitz', 'Suzuyo']
    found = sum(1 for p in patterns_needed if p in src)
    if found < 5:
        errors.append(f"Only {found}/5 bypass patterns found")

    if 'BYPASS_3PL_PATTERNS.some' not in src:
        errors.append("Auto-tag override logic missing in seedFromDenisePaymentPlan_")

    log_file = os.path.join(OUT, 'auto_tag_bypass_log.json')
    if not os.path.exists(log_file):
        errors.append("auto_tag_bypass_log.json missing")
    else:
        data = json.load(open(log_file))
        if 'historical_retagged_count' not in data:
            errors.append("historical_retagged_count field missing")

    if errors:
        print("PHASE 5 VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    retagged = json.load(open(log_file)).get('historical_retagged_count', 0)
    print(f"PHASE 5 VERIFY: ALL PASS (backfill retagged={retagged})")
    return 0

if __name__ == '__main__':
    sys.exit(main())
