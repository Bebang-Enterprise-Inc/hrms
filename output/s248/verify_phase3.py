"""Phase 3 verification — live deploy + first sync."""
import json, sys

dep = json.load(open('output/s248/v37_deployment.json'))
assert dep.get('versionNumber', 0) >= 14, f"version too low: {dep.get('versionNumber')}"
dc = dep.get('deploymentConfig', {})
assert dc.get('versionNumber', 0) >= 14, f'deployment not pointing at v14+'

live = json.load(open('output/s248/first_live_sync.json'))
ds = live.get('denise_seed', {})
appended = ds.get('appended', 0)
assert appended >= 200, f"live appended too low: {appended}"
assert ds.get('matches_dry_run') is True, 'live appended did NOT match dry-run prediction'

# Sheet state verification
state = json.load(open('output/s248/sheet_state_after_phase3.json'))
baseline = json.load(open('output/s248/baseline_sheet_state.json'))
soa_delta = state['Suppliers SOA'] - baseline['Suppliers SOA']
assert soa_delta == appended, f'Suppliers SOA delta {soa_delta} != denise_seed.appended {appended}'

# Protected surfaces unchanged
assert state['Head Office'] == baseline['Head Office'], 'Head Office regressed'
assert state['CAPEX'] == baseline['CAPEX'], 'CAPEX regressed'

# Spot-check SOURCE distribution
spot = json.load(open('output/s248/post_live_spotcheck.json'))
src_dist = spot.get('source_distribution', {})
assert 'Denise PP' in src_dist, 'no Denise PP rows in seeded set'
assert src_dist.get('Denise PP', 0) >= 200, f'fewer urgent Denise PP rows than expected: {src_dist.get("Denise PP")}'
assert src_dist.get('Denise PP - Disputed (Middleby)', 0) >= 5, 'Middleby disputed rows not tagged correctly'

print(f"PASS: v3.7 deployed (version={dep['versionNumber']}), {appended} Denise rows appended live")
print(f'  AP Master Suppliers SOA: {baseline["Suppliers SOA"]} -> {state["Suppliers SOA"]} (+{soa_delta})')
print(f'  HO unchanged: {state["Head Office"]} (protected)')
print(f'  CAPEX unchanged: {state["CAPEX"]} (protected)')
print(f'  Sources tagged: {src_dist}')
sys.exit(0)
