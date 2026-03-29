/**
 * S142 Phase A — Page Surface Audit
 * Load every procurement page with every role.
 * Classify as WORKS / EMPTY / SHELL / BROKEN / 403 / 404.
 * Take screenshot. Record to tmp/s142_page_audit.json.
 *
 * Run: node scripts/testing/s142_phase_a_pages.mjs
 */

import {
  ensureDirs, launchBrowser, loginAs, screenshot, classifyPage,
  readText, readTableRows, PAGES, RISKY_PAGES, ACCOUNTS, BASE,
  ResultTracker
} from './s142_utils.mjs';
import fs from 'fs';

const ROLES = ['ceo', 'staff', 'warehouse', 'crew'];

// Track record IDs discovered on list pages for detail page testing
const discoveredIds = {};

async function testPageWithRole(browser, pageInfo, role, tracker) {
  const tag = `${pageInfo.id}_${role}`;
  let session;

  try {
    session = await loginAs(browser, role);
  } catch (err) {
    tracker.fail(tag, `Login as ${role}`, `Cannot login`, err.message);
    return { status: 'LOGIN_FAIL' };
  }

  const { page, ctx, consoleErrors } = session;

  try {
    // Skip detail pages for now — they need IDs from list pages
    if (pageInfo.needsId) {
      const listId = pageInfo.listPage;
      const ids = discoveredIds[listId];
      if (!ids || ids.length === 0) {
        tracker.skip(tag, `${pageInfo.name} (${role})`, `No record IDs from list page ${listId}`);
        await ctx.close();
        return { status: 'SKIP' };
      }
      // Use first discovered ID
      const recordId = ids[0];
      const route = pageInfo.route.replace('[id]', recordId);
      await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle', timeout: 60000 });
    } else {
      await page.goto(`${BASE}${pageInfo.route}`, { waitUntil: 'networkidle', timeout: 60000 });
    }

    await page.waitForTimeout(3000);

    const screenshotPath = await screenshot(page, tag);
    const classification = await classifyPage(page);

    // For list pages, discover record IDs by finding links in the first table row
    if (!pageInfo.needsId && ['A2', 'A5', 'A8', 'A12', 'A15', 'A18'].includes(pageInfo.id) && classification.status === 'WORKS') {
      const firstLink = await page.locator('table tbody tr:first-child a').first().getAttribute('href').catch(() => null);
      if (firstLink) {
        const idMatch = firstLink.match(/\/([^/]+)$/);
        if (idMatch) {
          discoveredIds[pageInfo.id] = [idMatch[1]];
          console.log(`    Discovered ID for ${pageInfo.id}: ${idMatch[1]}`);
        }
      }
    }

    // Read data count if it's a list page
    let dataCount = null;
    const paginationText = await page.locator('text=/Showing \\d+/').first().innerText().catch(() => null);
    if (paginationText) {
      const totalMatch = paginationText.match(/of\s+(\d+)/);
      if (totalMatch) dataCount = totalMatch[1];
    }
    if (!dataCount) {
      const tableCount = await page.locator('table tbody tr').count().catch(() => 0);
      if (tableCount > 0) dataCount = String(tableCount);
    }

    // Detect console errors
    const errors = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('hydration'));

    const result = {
      status: classification.status,
      has_data: classification.status === 'WORKS',
      data_count: dataCount,
      console_errors: errors,
      screenshot: screenshotPath,
      notes: classification.text.substring(0, 200)
    };

    if (classification.status === 'WORKS' || classification.status === 'EMPTY') {
      tracker.pass(tag, `${pageInfo.name} (${role})`, `Status: ${classification.status}, Data: ${dataCount || 'N/A'}`);
    } else if (classification.status === '403') {
      // 403 might be expected for non-procurement roles
      if (role === 'crew' || role === 'warehouse') {
        tracker.pass(tag, `${pageInfo.name} (${role}) — RBAC blocks correctly`, 'Access Restricted');
      } else {
        tracker.fail(tag, `${pageInfo.name} (${role})`, `Unexpected 403 for ${role}`, 'Role should have access');
        tracker.defect(`${role} blocked from ${pageInfo.name}`, 'MAJOR', 'COLLATERAL', tag,
          `${role} gets Access Restricted on ${pageInfo.route}`, `${role} cannot access ${pageInfo.name}`,
          'RBAC configuration may be too restrictive', `Check roles.ts MODULES.PROCUREMENT access for ${role}`);
      }
    } else {
      tracker.fail(tag, `${pageInfo.name} (${role})`, `Status: ${classification.status}`, classification.text.substring(0, 100));
      if (classification.status === 'BROKEN') {
        tracker.defect(`${pageInfo.name} is broken`, 'CRITICAL', 'COLLATERAL', tag,
          `Page returns ${classification.status}`, `${pageInfo.name} is unusable`,
          'Unknown — page does not render', 'Investigate page component');
      }
    }

    await ctx.close();
    return result;

  } catch (err) {
    const screenshotPath = await screenshot(page, `${tag}_error`).catch(() => null);
    tracker.fail(tag, `${pageInfo.name} (${role})`, '', err.message);
    await ctx.close();
    return { status: 'ERROR', error: err.message };
  }
}

async function run() {
  ensureDirs();
  const tracker = new ResultTracker();
  const browser = await launchBrowser();

  console.log('═══════════════════════════════════════');
  console.log('S142 Phase A — Page Surface Audit');
  console.log(`Pages: ${PAGES.length} | Roles: ${ROLES.length}`);
  console.log('═══════════════════════════════════════\n');

  const pageResults = {};

  // First pass: test all non-detail pages with CEO to discover record IDs
  console.log('── Pass 1: CEO on all list/direct pages (discover record IDs) ──\n');
  for (const pageInfo of PAGES.filter(p => !p.needsId)) {
    console.log(`\n[${pageInfo.id}] ${pageInfo.name} (${pageInfo.route})`);
    const key = pageInfo.id;
    if (!pageResults[key]) pageResults[key] = { page_id: key, route: pageInfo.route, page_name: pageInfo.name, roles_tested: {} };
    pageResults[key].roles_tested.ceo = await testPageWithRole(browser, pageInfo, 'ceo', tracker);
  }

  // Second pass: test detail pages with CEO (now that we have IDs)
  console.log('\n── Pass 2: CEO on detail pages ──\n');
  for (const pageInfo of PAGES.filter(p => p.needsId)) {
    console.log(`\n[${pageInfo.id}] ${pageInfo.name}`);
    const key = pageInfo.id;
    if (!pageResults[key]) pageResults[key] = { page_id: key, route: pageInfo.route, page_name: pageInfo.name, roles_tested: {} };
    pageResults[key].roles_tested.ceo = await testPageWithRole(browser, pageInfo, 'ceo', tracker);
  }

  // Third pass: test ALL pages with remaining roles
  for (const role of ['staff', 'warehouse', 'crew']) {
    console.log(`\n── Pass 3: ${role} on all pages ──\n`);
    for (const pageInfo of PAGES) {
      console.log(`\n[${pageInfo.id}] ${pageInfo.name} (${role})`);
      const key = pageInfo.id;
      if (!pageResults[key]) pageResults[key] = { page_id: key, route: pageInfo.route, page_name: pageInfo.name, roles_tested: {} };
      pageResults[key].roles_tested[role] = await testPageWithRole(browser, pageInfo, role, tracker);
    }
  }

  // Test risky item pages (A25/A26/A27) if control tower had data
  console.log('\n── Risky Item Pages (A25/A26/A27) ──');
  // These require dynamic IDs from the control tower — try to discover from A23
  const ctPage = pageResults['A23'];
  if (ctPage?.roles_tested?.ceo?.status === 'WORKS') {
    // Navigate to control tower and find first risky item link
    const { page: ceoPage2, ctx: ceoCtx2 } = await loginAs(browser, 'ceo');
    await ceoPage2.goto(`${BASE}/dashboard/procurement/critical-items-control-tower`, { waitUntil: 'networkidle', timeout: 60000 });
    await ceoPage2.waitForTimeout(3000);
    const riskyLink = await ceoPage2.locator('a[href*="/risky-items/"]').first().getAttribute('href').catch(() => null);
    if (riskyLink) {
      for (const rp of RISKY_PAGES) {
        const route = riskyLink + (rp.id === 'A26' ? '/delayed-deliveries' : rp.id === 'A27' ? '/inbound-pipeline' : '');
        await ceoPage2.goto(`${BASE}${route}`, { waitUntil: 'networkidle', timeout: 60000 });
        await ceoPage2.waitForTimeout(3000);
        const screenshotPath = await screenshot(ceoPage2, `${rp.id}_ceo`);
        const mainText = await ceoPage2.innerText('main').catch(() => '');
        const status = mainText.length > 50 ? 'WORKS' : 'EMPTY';
        pageResults[rp.id] = { page_id: rp.id, route, page_name: rp.name, roles_tested: { ceo: { status, screenshot: screenshotPath } } };
        tracker.pass(`${rp.id}_ceo`, `${rp.name} (ceo)`, `Status: ${status}`);
      }
    } else {
      for (const rp of RISKY_PAGES) {
        tracker.skip(`${rp.id}_ceo`, rp.name, 'No risky item links in control tower');
      }
    }
    await ceoCtx2.close();
  } else {
    for (const rp of RISKY_PAGES) {
      tracker.skip(`${rp.id}_ceo`, rp.name, 'Control tower page did not load');
    }
  }

  // Write page audit JSON
  tracker.pageAudit.push(...Object.values(pageResults));

  // Build RBAC matrix
  let rbacMd = '# S142 RBAC Matrix\n\n';
  rbacMd += '| Page | CEO | Staff | Warehouse | Crew |\n';
  rbacMd += '|------|-----|-------|-----------|------|\n';
  for (const [key, pr] of Object.entries(pageResults)) {
    const row = [key];
    for (const role of ROLES) {
      const r = pr.roles_tested[role];
      row.push(r ? r.status : 'NOT_TESTED');
    }
    rbacMd += `| ${pr.page_name} | ${row.slice(1).join(' | ')} |\n`;
  }
  fs.writeFileSync('tmp/s142_rbac_matrix.md', rbacMd);

  await browser.close();
  tracker.writeAll();
  tracker.printSummary();

  console.log('\nPhase A complete. Output files:');
  console.log('  tmp/s142_page_audit.json');
  console.log('  tmp/s142_rbac_matrix.md');
  console.log('  tmp/s142_screenshots/ (screenshots)');
}

run().catch(err => { console.error('FATAL:', err); process.exit(1); });
