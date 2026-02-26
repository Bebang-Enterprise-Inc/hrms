#!/usr/bin/env python
import sys
sys.path.insert(0, '/workspace/frappe-bench/apps/frappe')
sys.path.insert(0, '/workspace/frappe-bench/apps/hrms')

try:
    import hrms.api.onboarding as onboarding
    print("Import OK")
    print(f"get_session: {onboarding.get_session}")
    print(f"Has whitelist attr: {hasattr(onboarding.get_session, 'is_whitelisted')}")
except Exception as e:
    print(f"Import FAILED: {e}")
