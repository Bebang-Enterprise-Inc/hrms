/**
 * S142 Phase E — Build Proof Matrix
 * Reads results from Phases A-D and produces the 4-dimension Proof Matrix.
 *
 * Run AFTER phases A-D complete:
 *   node scripts/testing/s142_phase_e_proof_matrix.mjs
 */

import fs from 'fs';

function loadJSON(path) {
  try { return JSON.parse(fs.readFileSync(path, 'utf8')); }
  catch { return null; }
}

function run() {
  console.log('═══════════════════════════════════════');
  console.log('S142 Phase E — Proof Matrix Builder');
  console.log('═══════════════════════════════════════\n');

  const pageAudit = loadJSON('tmp/s142_page_audit.json') || [];
  const ctaMatrix = loadJSON('tmp/s142_cta_matrix.json') || [];
  const dataMatch = loadJSON('tmp/s142_data_match.json') || {};
  const e2eWorkflow = loadJSON('tmp/s142_e2e_workflow.json') || [];

  const pages = [
    { id: 'A1',  name: 'Dashboard' },
    { id: 'A2',  name: 'PR List' },
    { id: 'A3',  name: 'PR New' },
    { id: 'A4',  name: 'PR Detail' },
    { id: 'A5',  name: 'PO List' },
    { id: 'A6',  name: 'PO New' },
    { id: 'A7',  name: 'PO Detail' },
    { id: 'A8',  name: 'Supplier List' },
    { id: 'A9',  name: 'Supplier New' },
    { id: 'A10', name: 'Supplier Detail' },
    { id: 'A11', name: 'Supplier Edit' },
    { id: 'A12', name: 'GR List' },
    { id: 'A13', name: 'GR New' },
    { id: 'A14', name: 'GR Detail' },
    { id: 'A15', name: 'Invoice List' },
    { id: 'A16', name: 'Invoice New' },
    { id: 'A17', name: 'Invoice Detail' },
    { id: 'A18', name: 'Payment List' },
    { id: 'A19', name: 'Payment New' },
    { id: 'A20', name: 'Payment Detail' },
    { id: 'A21', name: 'Approvals' },
    { id: 'A22', name: 'OR Follow-Up' },
    { id: 'A23', name: 'Critical Items CT' },
    { id: 'A24', name: 'Stockout Incidents' },
    { id: 'A28', name: 'Reports Hub' },
    { id: 'A29', name: 'Monthly Spend' },
    { id: 'A30', name: 'Supplier Performance' },
    { id: 'A31', name: 'Single-Source' },
    { id: 'A32', name: 'Three-Way Match' },
    { id: 'A33', name: 'Payment Disbursement' },
    { id: 'A34', name: 'GR Log' },
    { id: 'A35', name: 'PO Aging' },
    { id: 'A36', name: 'Price History' },
    { id: 'A37', name: 'Settings' },
    { id: 'A38', name: 'SOA' },
  ];

  let md = '# S142 Procurement Proof Matrix\n\n';
  md += `**Generated:** ${new Date().toISOString()}\n\n`;
  md += '## 4-Dimension Summary\n\n';
  md += '| Page | Data Accuracy | Functional (CTAs) | UX/Design | Business Rules | Overall |\n';
  md += '|------|:---:|:---:|:---:|:---:|:---:|\n';

  for (const p of pages) {
    // Dimension 1: Data Accuracy — from Phase D
    let dataStatus = 'N/A';
    if (['A5', 'A1'].includes(p.id)) {
      const poMatches = (dataMatch.pos || []).filter(po => po.supplier_match && po.amount_match);
      dataStatus = poMatches.length >= 3 ? '✅' : poMatches.length > 0 ? '⚠️' : '❌';
    } else if (p.id === 'A8') {
      const supMatches = (dataMatch.suppliers || []).filter(s => s.name_match);
      dataStatus = supMatches.length >= 3 ? '✅' : supMatches.length > 0 ? '⚠️' : '❌';
    } else if (p.id === 'A12') {
      const grMatches = (dataMatch.grs || []).filter(g => g.found_in_api);
      dataStatus = grMatches.length >= 3 ? '✅' : grMatches.length > 0 ? '⚠️' : '❌';
    } else if (['A15', 'A16', 'A17', 'A18', 'A19', 'A20'].includes(p.id)) {
      dataStatus = '⚠️ NO_DATA';
    }

    // Dimension 2: Functional — from Phase B CTA matrix
    const pageCTAs = ctaMatrix.filter(c => c.page === p.id);
    const working = pageCTAs.filter(c => c.result === 'WORKS').length;
    const broken = pageCTAs.filter(c => c.result === 'BROKEN').length;
    const notFound = pageCTAs.filter(c => c.result === 'NOT_FOUND').length;
    let funcStatus = 'N/A';
    if (pageCTAs.length > 0) {
      funcStatus = broken === 0 ? `✅ ${working}/${pageCTAs.length}` : `❌ ${working}/${pageCTAs.length}`;
    }

    // Dimension 3: UX/Design — from Phase A screenshots
    const pageResult = pageAudit.find(pa => pa.page_id === p.id);
    const ceoStatus = pageResult?.roles_tested?.ceo?.status;
    let uxStatus = 'N/A';
    if (ceoStatus === 'WORKS') uxStatus = '✅';
    else if (ceoStatus === 'EMPTY') uxStatus = '⚠️ empty';
    else if (ceoStatus === 'SHELL') uxStatus = '❌ shell';
    else if (ceoStatus === 'BROKEN') uxStatus = '❌ broken';
    else if (ceoStatus === '403') uxStatus = '🔒 403';

    // Dimension 4: Business Rules — from Phase C E2E + specific checks
    let bizStatus = 'N/A';
    if (p.id === 'A5' || p.id === 'A7') {
      // PO pages — check approval workflow
      const approvalStep = e2eWorkflow.find(w => w.step === 'C6');
      bizStatus = approvalStep?.result === 'PASS' ? '✅' : '⚠️';
    } else if (p.id === 'A37') {
      // Settings — check thresholds display
      const settingsCTA = ctaMatrix.find(c => c.cta_id === 'B37.5');
      bizStatus = settingsCTA?.result === 'WORKS' ? '✅' : '❌';
    }

    // Overall
    const allDimensions = [dataStatus, funcStatus, uxStatus, bizStatus];
    const hasFail = allDimensions.some(d => d.startsWith('❌'));
    const hasWarn = allDimensions.some(d => d.startsWith('⚠️'));
    const overall = hasFail ? 'FAIL' : hasWarn ? 'WARNING' : 'PASS';

    md += `| ${p.name} | ${dataStatus} | ${funcStatus} | ${uxStatus} | ${bizStatus} | ${overall} |\n`;
  }

  md += '\n## Legend\n\n';
  md += '- ✅ PASS — verified with evidence\n';
  md += '- ⚠️ WARNING — partial data or expected empty state\n';
  md += '- ❌ FAIL — defect found\n';
  md += '- N/A — dimension not applicable to this page\n';
  md += '- 🔒 403 — RBAC blocked (may be expected)\n';

  // Statistics
  md += '\n## Statistics\n\n';
  md += `- Pages audited: ${pageAudit.length}\n`;
  md += `- CTAs tested: ${ctaMatrix.length}\n`;
  md += `- CTAs working: ${ctaMatrix.filter(c => c.result === 'WORKS').length}\n`;
  md += `- CTAs broken: ${ctaMatrix.filter(c => c.result === 'BROKEN').length}\n`;
  md += `- CTAs not found: ${ctaMatrix.filter(c => c.result === 'NOT_FOUND').length}\n`;
  md += `- POs spot-checked: ${(dataMatch.pos || []).length}\n`;
  md += `- Suppliers spot-checked: ${(dataMatch.suppliers || []).length}\n`;
  md += `- GRs spot-checked: ${(dataMatch.grs || []).length}\n`;
  md += `- E2E workflow steps: ${e2eWorkflow.length}\n`;

  fs.writeFileSync('tmp/s142_proof_matrix.md', md);
  console.log('Proof Matrix written to: tmp/s142_proof_matrix.md');
  console.log(md);
}

run();
