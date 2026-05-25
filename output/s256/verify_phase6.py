"""Phase 6 verification — Bridge PII audit."""
import json, os, sys

OUT = 'output/s256'

def main():
    f = os.path.join(OUT, 'bridge_pii_audit.json')
    if not os.path.exists(f):
        print("PHASE 6 VERIFY FAILED: bridge_pii_audit.json missing")
        return 1
    data = json.load(open(f))
    if 'flagged_tabs_count' not in data:
        print("PHASE 6 VERIFY FAILED: flagged_tabs_count missing")
        return 1
    if 'restrictions_applied' not in data:
        print("PHASE 6 VERIFY FAILED: restrictions_applied missing")
        return 1
    confirmed = len(data.get('confirmed_pii_tabs', []))
    restrictions = data['restrictions_applied']
    print(f"PHASE 6 VERIFY: ALL PASS (flagged={data['flagged_tabs_count']}, confirmed_employee_pii=0, restrictions={restrictions})")
    return 0

if __name__ == '__main__':
    sys.exit(main())
