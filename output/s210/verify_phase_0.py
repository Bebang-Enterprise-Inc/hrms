"""S210 Phase 0 verification. Filesystem-based assertions. Returns 0 on PASS, 1 on FAIL."""
import json, pathlib, sys, csv

FAILED = []
# Resolve ROOT from this file's location so the verifier works in either
# the main repo or the s210 worktree.
ROOT = pathlib.Path(__file__).resolve().parents[2]

def must_exist(rel, reason):
    p = ROOT / rel
    if not p.exists():
        FAILED.append(f'MISSING: {rel} -- {reason}')
        return None
    return p

def must_contain_substring(rel, substr, reason):
    p = must_exist(rel, reason)
    if p is None:
        return
    text = p.read_text(encoding='utf-8', errors='ignore')
    if substr not in text:
        FAILED.append(f'PATTERN MISSING: {substr!r} in {rel} -- {reason}')

def must_have_min_rows(rel, min_rows, reason):
    p = must_exist(rel, reason)
    if p is None:
        return
    with open(p, 'r', encoding='utf-8') as f:
        n = sum(1 for _ in csv.reader(f)) - 1  # minus header
    if n < min_rows:
        FAILED.append(f'TOO FEW ROWS: {rel} has {n}, need >= {min_rows} -- {reason}')

# Task 0.1 - canonical preflight log
must_exist('output/s210/verify_canonical_preflight.log',
           'Preflight captured (scope: none per CEO, skip rule N/A)')

# Task 0.2 - Procurement AppSheet baseline
must_exist('output/s210/PROCUREMENT_APPSHEET_BASELINE.json',
           'Procurement AppSheet tab structure captured')
must_contain_substring('output/s210/PROCUREMENT_APPSHEET_BASELINE.json',
                       '1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q',
                       'Contains verified Procurement AppSheet sheet ID')
must_contain_substring('output/s210/PROCUREMENT_APPSHEET_BASELINE.json',
                       'Suppliers', 'Suppliers tab enumerated')
must_contain_substring('output/s210/PROCUREMENT_APPSHEET_BASELINE.json',
                       'PO Items', 'PO Items tab enumerated')
must_contain_substring('output/s210/PROCUREMENT_APPSHEET_BASELINE.json',
                       'Delivery Receipts', 'Delivery Receipts tab enumerated')

# Task 0.3 - Library audit
must_exist('output/s210/LIBRARY_AUDIT.md',
           'Library audit documented')
must_contain_substring('output/s210/LIBRARY_AUDIT.md',
                       'postChatNotification', 'Names the key helper')

# Task 0.4 - Ownership matrix (>= 15 rows)
must_have_min_rows('output/s210/S210_SURFACE_OWNERSHIP.csv', 15,
                   'Ownership matrix covers all S210 surfaces')

# Task 0.5 - Protected surfaces
must_exist('output/s210/S210_PROTECTED_SURFACES.csv',
           'Protected surfaces listed')

# Baseline + coordination
must_exist('output/s210/state/S210_REMOTE_TRUTH_BASELINE.json', 'Remote-truth baseline')
must_exist('output/s210/state/S210_ACTIVE_RUN_COORDINATION.json', 'Run coordination claim')

if FAILED:
    print(f'[FAIL] Phase 0 verification -- {len(FAILED)} issues:')
    for f in FAILED:
        print(' ', f)
    sys.exit(1)
print('[PASS] Phase 0 verification -- all assertions green')
sys.exit(0)
