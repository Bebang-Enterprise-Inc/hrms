"""Phase 2 verification — v3.10 intercompany broadening + dedup race fix."""
import os, sys, re

V310 = 'scripts/google_apps/s256_ap_view_hourly_sync_v310.gs'

def main():
    errors = []

    if not os.path.exists(V310):
        errors.append("v3.10 source file missing")
        print("PHASE 2 VERIFY FAILED:", errors)
        return 1

    src = open(V310, encoding='utf-8').read()
    sz = os.path.getsize(V310)
    if sz < 90000 or sz > 110000:
        errors.append(f"v3.10 size {sz} out of expected range")

    if 'INTERCO_AFFILIATE_PATTERNS' not in src:
        errors.append("INTERCO_AFFILIATE_PATTERNS const missing")

    if 'isIntercompany' not in src:
        errors.append("isIntercompany variable missing")

    if 'skipped_existing_fpm_soa' not in src:
        errors.append("skipped_existing_fpm_soa counter missing")

    # Check at least 5 of the 14 affiliate entity names
    affiliates = ['CUBED', 'ESTANCIA', 'BEIFRANCHISE', 'DMD', 'ALABANG',
                  'TERMINAL', 'SOLENAD', 'TALDAWA', 'RESTO', 'SWEET',
                  'TAJ', 'TUNGSTEN', 'PERPETUAL', 'DAY']
    found = sum(1 for a in affiliates if a in src.upper())
    if found < 5:
        errors.append(f"Only {found}/14 affiliate names found (need >= 5)")

    # Check Bebang pattern still preserved as first entry
    if '/^Bebang' not in src:
        errors.append("Original Bebang pattern not preserved")

    # Check FPM-SOA dedup key in existingIndex builder
    if "FPMSOA|" not in src:
        errors.append("FPMSOA| dedup key not in existingIndex builder")

    if errors:
        print("PHASE 2 VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PHASE 2 VERIFY: ALL PASS (v3.10 size={sz}, affiliates={found}/14)")
    return 0

if __name__ == '__main__':
    sys.exit(main())
