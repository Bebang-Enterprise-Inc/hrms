"""Phase 3 verification — affiliate migration."""
import json, os, sys

OUT = 'output/s256'

def main():
    errors = []
    f = os.path.join(OUT, 'intercompany_affiliate_migration_log.json')
    if not os.path.exists(f):
        errors.append("intercompany_affiliate_migration_log.json missing")
    else:
        data = json.load(open(f))
        if 'migrated_rows' not in data:
            errors.append("migrated_rows field missing")
        elif data['migrated_rows'] < 0:
            errors.append(f"migrated_rows negative: {data['migrated_rows']}")

    cf = os.path.join(OUT, 'phase3_affiliate_candidates.json')
    if not os.path.exists(cf):
        errors.append("phase3_affiliate_candidates.json missing")
    else:
        cdata = json.load(open(cf))
        if 'candidates_count' not in cdata:
            errors.append("candidates_count field missing")

    if errors:
        print("PHASE 3 VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    migrated = json.load(open(f))['migrated_rows']
    print(f"PHASE 3 VERIFY: ALL PASS (migrated_rows={migrated})")
    return 0

if __name__ == '__main__':
    sys.exit(main())
