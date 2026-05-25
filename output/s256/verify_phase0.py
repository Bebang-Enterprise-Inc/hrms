"""Phase 0 verification — machine-checkable assertions."""
import json, os, sys

OUT = 'output/s256'

def main():
    errors = []

    # baseline SHA exists
    sha_file = os.path.join(OUT, 'baseline_sha.txt')
    if not os.path.exists(sha_file):
        errors.append("baseline_sha.txt missing")
    else:
        sha = open(sha_file).read().strip()
        if len(sha) < 40:
            errors.append(f"baseline_sha too short: {sha}")

    # v3.9 backup in range [90000, 105000]
    backup = os.path.join(OUT, 'script_source_backup_v39.gs')
    if not os.path.exists(backup):
        errors.append("script_source_backup_v39.gs missing")
    else:
        sz = os.path.getsize(backup)
        if sz < 90000 or sz > 105000:
            errors.append(f"v3.9 backup size {sz} out of range [90000, 105000]")

    # baseline_state.json has >= 17 tabs
    bs_file = os.path.join(OUT, 'baseline_state.json')
    if not os.path.exists(bs_file):
        errors.append("baseline_state.json missing")
    else:
        bs = json.load(open(bs_file))
        if bs.get('tab_count', 0) < 17:
            errors.append(f"AP Master tab_count {bs.get('tab_count')} < 17")

    # scheduler paused
    cs_file = os.path.join(OUT, 'cloud_scheduler_pause_log.json')
    if not os.path.exists(cs_file):
        errors.append("cloud_scheduler_pause_log.json missing")
    else:
        cs = json.load(open(cs_file))
        if cs.get('current_state') != 'PAUSED':
            errors.append(f"Scheduler not PAUSED: {cs.get('current_state')}")

    # ownership matrix >= 10 rows
    om_file = os.path.join(OUT, 'S256_SURFACE_OWNERSHIP_MATRIX.csv')
    if not os.path.exists(om_file):
        errors.append("S256_SURFACE_OWNERSHIP_MATRIX.csv missing")
    else:
        lines = open(om_file).readlines()
        if len(lines) < 11:  # header + 10 data
            errors.append(f"Ownership matrix only {len(lines)-1} rows (need >= 10)")

    # Denise PP baseline has bridge users
    pp_file = os.path.join(OUT, 'denise_pp_baseline.json')
    if not os.path.exists(pp_file):
        errors.append("denise_pp_baseline.json missing")
    else:
        pp = json.load(open(pp_file))
        if pp.get('bridge_user_count', 0) < 1:
            errors.append("No Bridge users on Denise PP")

    # Upstream ACLs have bridge
    ua_file = os.path.join(OUT, 'upstream_acl_baseline.json')
    if not os.path.exists(ua_file):
        errors.append("upstream_acl_baseline.json missing")
    else:
        ua = json.load(open(ua_file))
        for name, data in ua.get('sheets', {}).items():
            if data.get('bridge_count', 0) < 1:
                errors.append(f"No Bridge users on upstream sheet: {name}")

    if errors:
        print("PHASE 0 VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PHASE 0 VERIFY: ALL PASS")
    return 0

if __name__ == '__main__':
    sys.exit(main())
