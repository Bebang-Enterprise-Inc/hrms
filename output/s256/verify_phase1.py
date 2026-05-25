"""Phase 1 verification — investigation gate assertions."""
import json, os, sys

OUT = 'output/s256'

def main():
    errors = []
    f = os.path.join(OUT, 'phase1_source_investigation.json')
    if not os.path.exists(f):
        errors.append("phase1_source_investigation.json missing")
        print("PHASE 1 VERIFY FAILED:", errors)
        return 1

    data = json.load(open(f, encoding='utf-8'))

    if 'proceed_with_source_redesign' not in data:
        errors.append("proceed_with_source_redesign field missing")
    else:
        proceed = data['proceed_with_source_redesign']
        if proceed:
            if not data.get('procurement_app_chosen'):
                errors.append("proceed=True but procurement_app_chosen is null")
            if not data.get('ho_opening_balance_chosen'):
                errors.append("proceed=True but ho_opening_balance_chosen is null")
        # If proceed=False, that's valid (just means deferral)

    if errors:
        print("PHASE 1 VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PHASE 1 VERIFY: ALL PASS (proceed_with_source_redesign={data.get('proceed_with_source_redesign')})")
    return 0

if __name__ == '__main__':
    sys.exit(main())
