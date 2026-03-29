/**
 * S142 Master Runner — Execute All Phases
 *
 * Runs phases A → B → C → D → E in sequence.
 * Each phase writes its own output files.
 * Phase E reads all previous output to build the Proof Matrix.
 *
 * Run: node scripts/testing/s142_run_all.mjs
 *
 * Or run individually:
 *   node scripts/testing/s142_phase_a_pages.mjs    # Phase A: 38 pages x 4 roles
 *   node scripts/testing/s142_phase_b_ctas.mjs     # Phase B: 200+ CTAs
 *   node scripts/testing/s142_phase_c_e2e.mjs      # Phase C: E2E workflow
 *   node scripts/testing/s142_phase_d_data_match.mjs # Phase D: Three-way data match
 *   node scripts/testing/s142_phase_e_proof_matrix.mjs # Phase E: Build Proof Matrix
 */

import { execSync } from 'child_process';
import fs from 'fs';

const phases = [
  { name: 'Phase A: Page Surface Audit',    script: 'scripts/testing/s142_phase_a_pages.mjs' },
  { name: 'Phase B: CTA / Button Audit (list pages)',      script: 'scripts/testing/s142_phase_b_ctas.mjs' },
  { name: 'Phase B2: CTA / Detail+Creation Pages',        script: 'scripts/testing/s142_phase_b2_detail_pages.mjs' },
  { name: 'Phase C: E2E Workflow',                         script: 'scripts/testing/s142_phase_c_e2e.mjs' },
  { name: 'Phase D: Data Validation',         script: 'scripts/testing/s142_phase_d_data_validation.mjs' },
  { name: 'Phase E: Proof Matrix',           script: 'scripts/testing/s142_phase_e_proof_matrix.mjs' },
];

console.log('╔═══════════════════════════════════════════╗');
console.log('║  S142 Full Procurement Module QA Audit    ║');
console.log('║  38 pages · 4 roles · 200+ CTAs           ║');
console.log('║  E2E workflow · Data match · Proof Matrix  ║');
console.log('╚═══════════════════════════════════════════╝\n');
console.log(`Start time: ${new Date().toISOString()}\n`);

const phaseResults = [];

for (const phase of phases) {
  console.log(`\n${'═'.repeat(50)}`);
  console.log(`Starting: ${phase.name}`);
  console.log('═'.repeat(50));

  const startTime = Date.now();
  try {
    execSync(`node ${phase.script}`, {
      stdio: 'inherit',
      timeout: 600000, // 10 min per phase
      cwd: process.cwd(),
    });
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    phaseResults.push({ phase: phase.name, status: 'COMPLETE', duration: `${duration}s` });
    console.log(`\n✓ ${phase.name} completed in ${duration}s`);
  } catch (err) {
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    phaseResults.push({ phase: phase.name, status: 'FAILED', duration: `${duration}s`, error: err.message });
    console.log(`\n✗ ${phase.name} FAILED after ${duration}s: ${err.message}`);
    // Continue to next phase — don't abort the whole run
  }
}

// Summary
console.log('\n\n╔═══════════════════════════════════════════╗');
console.log('║  S142 AUDIT COMPLETE                       ║');
console.log('╚═══════════════════════════════════════════╝\n');

for (const r of phaseResults) {
  console.log(`  [${r.status === 'COMPLETE' ? '✓' : '✗'}] ${r.phase} (${r.duration})`);
}

console.log('\nOutput files:');
const outputs = [
  'tmp/s142_page_audit.json',
  'tmp/s142_cta_matrix.json',
  'tmp/s142_e2e_workflow.json',
  'tmp/s142_data_match.json',
  'tmp/s142_proof_matrix.md',
  'tmp/s142_rbac_matrix.md',
  'output/l3/S142/DEFECTS.md',
];
for (const f of outputs) {
  const exists = fs.existsSync(f);
  console.log(`  ${exists ? '✓' : '✗'} ${f}`);
}

console.log(`\nEnd time: ${new Date().toISOString()}`);
console.log(`Screenshots: tmp/s142_screenshots/`);
