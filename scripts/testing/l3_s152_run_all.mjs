/**
 * S152 Master Runner — Runs all chains in sequence
 *
 * Usage:
 *   node scripts/testing/l3_s152_run_all.mjs           # Run all
 *   node scripts/testing/l3_s152_run_all.mjs chain-a    # Chain A only
 *   node scripts/testing/l3_s152_run_all.mjs chain-bc   # Chain B+C only
 *   node scripts/testing/l3_s152_run_all.mjs edge       # Edge cases only
 *   node scripts/testing/l3_s152_run_all.mjs dashboards # Dashboards only
 */
import { execSync } from 'child_process';
import fs from 'fs';

const OUT = 'output/l3/S152';
const args = process.argv.slice(2);
const runAll = args.length === 0 || args.includes('all');

const scripts = [
  { name: 'Chain A (≤P500K, Mae-only, 3-level RFP)', file: 'l3_s152_chain_a.mjs', key: 'chain-a' },
  { name: 'Chain B+C (>P500K dual + >P1M CEO)', file: 'l3_s152_chain_bc.mjs', key: 'chain-bc' },
  { name: 'Edge Cases (rejections, partial GR, variance)', file: 'l3_s152_edge_cases.mjs', key: 'edge' },
  { name: 'Dashboards (AP CC + procurement pages)', file: 'l3_s152_dashboards.mjs', key: 'dashboards' },
];

const results = [];

console.log('='.repeat(70));
console.log('S152 PROCUREMENT E2E ACCEPTANCE TESTING — MASTER RUNNER');
console.log(`Started: ${new Date().toISOString()}`);
console.log('='.repeat(70));

for (const s of scripts) {
  if (!runAll && !args.includes(s.key)) continue;

  console.log(`\n${'─'.repeat(70)}`);
  console.log(`▶ ${s.name}`);
  console.log(`  Script: scripts/testing/${s.file}`);
  console.log('─'.repeat(70));

  const start = Date.now();
  try {
    execSync(`node scripts/testing/${s.file}`, {
      stdio: 'inherit',
      timeout: 600000, // 10 min per script
      cwd: process.cwd(),
    });
    results.push({ name: s.name, status: 'PASS', time: ((Date.now() - start) / 1000).toFixed(1) + 's' });
  } catch (err) {
    results.push({ name: s.name, status: 'FAIL', time: ((Date.now() - start) / 1000).toFixed(1) + 's', error: err.message?.slice(0, 200) });
  }
}

// === AGGREGATE SUMMARY ===
console.log('\n' + '='.repeat(70));
console.log('S152 AGGREGATE RESULTS');
console.log('='.repeat(70));

// Read all individual result files
const allResults = [];
const evidenceFiles = fs.readdirSync(OUT).filter(f => f.endsWith('_results.json'));
for (const f of evidenceFiles) {
  try {
    const data = JSON.parse(fs.readFileSync(`${OUT}/${f}`, 'utf8'));
    allResults.push(...data);
  } catch {}
}

const pass = allResults.filter(r => r.status === 'PASS').length;
const fail = allResults.filter(r => r.status === 'FAIL').length;
const skip = allResults.filter(r => r.status === 'SKIP').length;

for (const r of allResults) {
  const icon = r.status === 'PASS' ? '✓' : r.status === 'FAIL' ? '✗' : '○';
  console.log(`  [${r.status}] ${r.scenario}: ${r.test}`);
}

console.log(`\n  TOTAL: ${pass}/${allResults.length} PASS, ${fail} FAIL, ${skip} SKIP`);
console.log('\nScript-level results:');
for (const r of results) {
  console.log(`  [${r.status}] ${r.name} (${r.time})`);
}

// Write aggregate
fs.writeFileSync(`${OUT}/aggregate_results.json`, JSON.stringify({
  run_date: new Date().toISOString(),
  total: allResults.length,
  pass, fail, skip,
  scripts: results,
  scenarios: allResults,
}, null, 2));

console.log(`\nEvidence: ${OUT}/`);
console.log('='.repeat(70));
process.exit(fail > 0 ? 1 : 0);
