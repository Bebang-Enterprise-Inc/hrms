"""S210 Phase 6 verifier. Exit 0 = PASS.

Per plan task 6.5:
- Runs all prior phase verifiers (0-5) in sequence
- Asserts E2E evidence files exist and all scenarios pass:
  * output/l3/s210/e2e_test_3md.json
  * output/l3/s210/e2e_test_pinnacle.json
  * output/l3/s210/e2e_test_supplier_si.json
  * output/l3/s210/SUMMARY.md
- Asserts onboarding doc exists with >=10 numbered steps and both sheet URLs
- Asserts plan YAML has status: COMPLETED (post-6.6)
- Asserts SPRINT_REGISTRY row is updated (post-6.7)
"""
import json, re, sys, subprocess, pathlib
sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(r'F:\Dropbox\Projects\BEI-ERP-s210')
L3_DIR = ROOT / 'output/l3/s210'
PLAN_PATH = ROOT / 'docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md'
REGISTRY_PATH = ROOT / 'docs/plans/SPRINT_REGISTRY.md'
ONBOARDING_PATH = ROOT / 'output/s210/ONBOARDING_MARTIN_PINNACLE.md'
SHEET_IDS_PATH = ROOT / 'output/s210/SHEET_IDS.json'


def run_verifier(name):
    path = ROOT / f'output/s210/{name}'
    if not path.exists():
        return False, f'{name} missing'
    result = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True, text=True,
        cwd=str(ROOT),
    )
    return (result.returncode == 0), result.stdout + result.stderr


def main():
    failures = []

    # Run all prior verifiers
    for verifier in ('verify_phase_0.py', 'verify_phase_2.py', 'verify_phase_3.py',
                     'verify_phase_4.py', 'verify_phase_5.py'):
        ok, out = run_verifier(verifier)
        if not ok:
            failures.append(f'{verifier} FAILED:\n{out}')
        else:
            print(f'[PASS] {verifier}')

    # E2E evidence files
    for name in ('e2e_test_3md.json', 'e2e_test_pinnacle.json',
                 'e2e_test_supplier_si.json', 'SUMMARY.md', 'SUMMARY.json'):
        p = L3_DIR / name
        if not p.exists():
            failures.append(f'Missing evidence: {p}')

    # Check evidence PASS=true
    for name in ('e2e_test_3md.json', 'e2e_test_pinnacle.json', 'e2e_test_supplier_si.json'):
        p = L3_DIR / name
        if p.exists():
            data = json.loads(p.read_text())
            if not data.get('pass'):
                failures.append(f'{name} pass=false: {data.get("error", data)}')

    # Overall E2E pass
    sum_path = L3_DIR / 'SUMMARY.json'
    if sum_path.exists():
        summary = json.loads(sum_path.read_text())
        if not summary.get('overall_pass'):
            failures.append('SUMMARY.json overall_pass=false')

    # Onboarding doc checks
    if not ONBOARDING_PATH.exists():
        failures.append(f'{ONBOARDING_PATH} missing')
    else:
        text = ONBOARDING_PATH.read_text(encoding='utf-8')
        numbered_steps = len(re.findall(r'^\d+\. ', text, flags=re.MULTILINE))
        if numbered_steps < 10:
            failures.append(f'Onboarding has {numbered_steps} numbered steps (need >=10)')
        ids = json.loads(SHEET_IDS_PATH.read_text())
        if ids['sheet_a_id'] not in text:
            failures.append(f'Onboarding missing sheet_a_id')
        if ids['sheet_b_id'] not in text:
            failures.append(f'Onboarding missing sheet_b_id')

    # Plan YAML status: COMPLETED (checked after task 6.6)
    plan_text = PLAN_PATH.read_text(encoding='utf-8')
    m = re.search(r'^status:\s*(\S+)', plan_text, flags=re.MULTILINE)
    if not m:
        failures.append('Plan missing status: line')
    elif m.group(1).strip() != 'COMPLETED':
        failures.append(f'Plan status is {m.group(1)} (expected COMPLETED)')

    # Registry update — S210 row shows COMPLETED
    reg_text = REGISTRY_PATH.read_text(encoding='utf-8')
    s210_line = None
    for line in reg_text.splitlines():
        if 'S210' in line and '|' in line:
            s210_line = line
            break
    if not s210_line:
        failures.append('SPRINT_REGISTRY.md missing S210 row')
    elif 'COMPLETED' not in s210_line:
        failures.append(f'SPRINT_REGISTRY.md S210 row not COMPLETED: {s210_line[:120]}')

    print('\n=== S210 Phase 6 Verifier ===\n')
    if failures:
        for f in failures:
            print(f'[FAIL] {f}')
        print(f'\n{len(failures)} failures')
        sys.exit(1)

    print('[PASS] All prior phase verifiers passed')
    print('[PASS] E2E evidence files present + all scenarios pass')
    print('[PASS] SUMMARY.json overall_pass=true')
    print('[PASS] Onboarding doc has >=10 numbered steps + both sheet URLs')
    print('[PASS] Plan YAML status = COMPLETED')
    print('[PASS] SPRINT_REGISTRY S210 row = COMPLETED')
    print('\nAll checks passed.')
    sys.exit(0)


if __name__ == '__main__':
    main()
