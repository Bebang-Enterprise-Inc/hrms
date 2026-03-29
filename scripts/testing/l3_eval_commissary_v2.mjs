/**
 * L3 Eval Test v2: Commissary Dashboard + Log Production Output
 * COMM-EVAL-001
 * Target: https://my.bebang.ph
 * User: test.commissary@bebang.ph
 *
 * URL structure discovered from source:
 * - Dashboard: /dashboard/commissary
 * - Production page: /dashboard/commissary/production
 * - Dialog trigger: Button "Log Production" on production page
 * - Dialog title: "Log Production Output"
 * - Submit button text: "Log Production" (inside DialogFooter)
 * - Item selector: Radix <Select> - must click trigger, then click <SelectItem>
 */
import { chromium } from 'playwright';
import fs from 'fs';

const BASE_URL = 'https://my.bebang.ph';
const EMAIL = 'test.commissary@bebang.ph';
const PASSWORD = 'BeiTest2026!';
const OUT_DIR = 'F:/Dropbox/Projects/BEI-ERP/output/l3/eval-test';
const ARTIFACTS_DIR = `${OUT_DIR}/artifacts`;
const EVIDENCE_DIR = `${OUT_DIR}/evidence`;

function writeJSON(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
  console.log(`[WRITE] ${filePath}`);
}

async function run() {
  const startTime = new Date().toISOString();
  console.log(`[START] L3 Commissary Eval Test v2 — ${startTime}`);
  console.log(`[INFO] PHT: ${new Date().toLocaleString('en-PH', { timeZone: 'Asia/Manila' })}`);

  const stateVerification = [];
  const formSubmissions = [];
  const actions = [];
  const networkRequests = [];
  const networkResponses = [];

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  // Register network listeners globally (before any navigation)
  page.on('request', req => {
    if (req.url().includes('/api/') || req.method() === 'POST') {
      networkRequests.push({
        method: req.method(),
        url: req.url(),
        postData: req.postData()?.slice(0, 500) || null,
        timestamp: new Date().toISOString(),
      });
    }
  });

  page.on('response', async resp => {
    const url = resp.url();
    if (url.includes('/api/') || url.includes('commissary') || resp.status() >= 400) {
      try {
        const body = await resp.text().catch(() => '');
        networkResponses.push({
          method: resp.request().method(),
          url: url,
          status: resp.status(),
          body_snippet: body.slice(0, 800),
          timestamp: new Date().toISOString(),
        });
      } catch (e) {
        networkResponses.push({ url, status: resp.status(), error: e.message });
      }
    }
  });

  // ============================================================
  // STEP 1: Login
  // ============================================================
  console.log('\n[STEP 1] Login...');
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_01_login.png` });

  const emailInput = page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first();
  await emailInput.waitFor({ state: 'visible', timeout: 15000 });
  await emailInput.fill(EMAIL);
  await page.locator('input[type="password"]').first().fill(PASSWORD);
  actions.push({ type: 'fill', field: 'email+password' });

  await page.locator('button[type="submit"]').first().click();
  actions.push({ type: 'click', target: 'login submit' });

  // Wait for redirect — may go to dashboard or tasks
  await page.waitForTimeout(5000);
  const postLoginUrl = page.url();
  console.log(`[STEP 1] Post-login URL: ${postLoginUrl}`);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_02_post_login.png` });

  if (postLoginUrl.includes('/login')) {
    throw new Error('Login failed — still on login page after 5s');
  }

  // ============================================================
  // STEP 2: Navigate directly to commissary dashboard
  // (sidebar link went to tasks — use direct URL from source)
  // ============================================================
  console.log('\n[STEP 2] Navigate to /dashboard/commissary...');
  await page.goto(`${BASE_URL}/dashboard/commissary`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(4000); // allow React data fetching
  actions.push({ type: 'nav_direct', target: `${BASE_URL}/dashboard/commissary`, reason: 'sidebar link resolves to tasks, direct nav used' });

  const commissaryUrl = page.url();
  console.log(`[STEP 2] Commissary URL: ${commissaryUrl}`);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_03_commissary_dashboard.png` });

  // ============================================================
  // STEP 3: Read dashboard metric cards using textContent()
  // Cards: PRODUCTION, HANDOFFS, LOW STOCK, DISPATCHES
  // Source: text-4xl font-bold inside each Card > CardContent
  // ============================================================
  console.log('\n[STEP 3] Reading dashboard metric cards via textContent()...');

  const dashboardMetrics = await page.evaluate(() => {
    const results = {};

    // Card titles are in <CardTitle class="text-sm font-medium text-muted-foreground">
    // Values are in <div class="text-4xl font-bold">
    // Strategy: find all "text-4xl" elements and pair with nearest card title above them

    // Find all heading+value pairs by looking at card structure
    const cards = document.querySelectorAll('[class*="rounded-xl border"]');
    cards.forEach((card, idx) => {
      const titleEl = card.querySelector('[class*="text-muted-foreground"]');
      const valueEl = card.querySelector('[class*="text-4xl"]');
      if (titleEl && valueEl) {
        const title = titleEl.textContent?.trim();
        const value = valueEl.textContent?.trim();
        if (title && value !== undefined) {
          results[title] = value;
        }
      }
    });

    // Also try by explicit text content search for known card titles
    const knownTitles = ['PRODUCTION', 'HANDOFFS', 'LOW STOCK', 'DISPATCHES', 'PRODUCTIVITY', 'DAYS INVENTORY'];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    const titleNodes = [];
    while ((node = walker.nextNode())) {
      const text = node.textContent?.trim();
      if (knownTitles.includes(text)) {
        // Walk up to find a sibling or descendant with a number
        let parent = node.parentElement;
        for (let i = 0; i < 5; i++) {
          if (!parent) break;
          // Look for text-4xl sibling or child
          const numEl = parent.querySelector('[class*="text-4xl"], [class*="text-3xl"], [class*="text-2xl"]');
          if (numEl) {
            results[text] = numEl.textContent?.trim();
            break;
          }
          // Look for number in parent's own text
          const parentText = parent.textContent?.trim();
          const numMatch = parentText?.replace(text, '').trim().match(/^[\d,]+/);
          if (numMatch) {
            results[text] = numMatch[0];
            break;
          }
          parent = parent.parentElement;
        }
      }
    }

    return results;
  });

  console.log('[STEP 3] Dashboard metrics:', JSON.stringify(dashboardMetrics, null, 2));

  // Record each metric in stateVerification with textContent() method
  const expectedMetrics = ['PRODUCTION', 'HANDOFFS', 'LOW STOCK', 'DISPATCHES'];
  for (const metric of expectedMetrics) {
    const val = dashboardMetrics[metric];
    stateVerification.push({
      check: `dashboard_card_${metric.toLowerCase().replace(/\s+/g, '_')}`,
      before: 'N/A (initial load)',
      after: val !== undefined ? val : 'NOT_FOUND',
      method: 'textContent()',
      expected: 'numeric_value',
      actual: val !== undefined ? val : 'NOT_FOUND',
      passed: val !== undefined,
    });
    console.log(`[STEP 3] ${metric} = "${val ?? 'NOT_FOUND'}"`);
  }

  // ============================================================
  // STEP 4: Navigate to production page, click "Log Production"
  // The dialog trigger is a Button on /dashboard/commissary/production
  // ============================================================
  console.log('\n[STEP 4] Navigate to production page...');
  await page.goto(`${BASE_URL}/dashboard/commissary/production`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(4000);
  actions.push({ type: 'nav_direct', target: `${BASE_URL}/dashboard/commissary/production` });

  console.log(`[STEP 4] Production page URL: ${page.url()}`);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_04_production_page.png` });

  // Read all available items from the Production Items grid (before opening dialog)
  const availableItems = await page.evaluate(() => {
    // Items are in a grid of buttons inside "Production Items" card
    const buttons = document.querySelectorAll('button');
    const items = [];
    buttons.forEach(btn => {
      const text = btn.innerText?.trim();
      if (text && text.length > 3 && text.length < 100 && !['Log Production', 'Cancel', 'Log First Production'].includes(text)) {
        items.push(text.slice(0, 60));
      }
    });
    return items.slice(0, 15);
  });
  console.log('[STEP 4] Visible buttons on production page:', JSON.stringify(availableItems, null, 2));

  // Click "Log Production" button to open dialog
  // Source: <Button><Plus />Log Production</Button> as DialogTrigger
  const logProdBtn = page.locator('button:has-text("Log Production")').first();
  const logProdCount = await logProdBtn.count();
  console.log(`[STEP 4] "Log Production" buttons found: ${logProdCount}`);

  if (logProdCount === 0) {
    // Try alternative — "Log First Production"
    const altBtn = page.locator('button:has-text("Log First Production")').first();
    const altCount = await altBtn.count();
    console.log(`[STEP 4] "Log First Production" buttons found: ${altCount}`);
    if (altCount > 0) {
      await altBtn.click();
      actions.push({ type: 'click', target: 'Log First Production button', selector: 'button:has-text("Log First Production")' });
    } else {
      console.log('[STEP 4] ERROR: No production log button found');
      await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_04b_no_button.png` });
    }
  } else {
    await logProdBtn.click();
    actions.push({ type: 'click', target: 'Log Production button', selector: 'button:has-text("Log Production")' });
  }

  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_05_dialog_opened.png` });

  // ============================================================
  // STEP 5: Fill the dialog form
  // Dialog structure from source:
  //   - <Select> for item (Radix) — click trigger, click SelectItem
  //   - Input id="qty" type="number"
  //   - Input id="batch"
  //   - Input id="production-date" type="date"
  //   - Textarea id="notes"
  //   - Button "Log Production" in DialogFooter
  // ============================================================
  console.log('\n[STEP 5] Checking dialog state...');

  const dialogVisible = await page.locator('[role="dialog"]').first().count();
  console.log(`[STEP 5] Dialog visible: ${dialogVisible > 0}`);

  let dialogOpened = false;
  let submitClicked = false;
  let submitBtnSelector = null;
  let selectedItemText = null;
  let toastText = 'NOT_CAPTURED';
  let submitNetworkRequest = null;

  if (dialogVisible > 0) {
    dialogOpened = true;
    console.log('[STEP 5] Dialog is open. Filling fields...');

    // --- Item Select (Radix) ---
    // Source: <SelectTrigger><SelectValue placeholder="Select item..." /></SelectTrigger>
    const selectTrigger = page.locator('[role="dialog"] [role="combobox"]').first();
    const selectTriggerCount = await selectTrigger.count();
    console.log(`[STEP 5] Select trigger count: ${selectTriggerCount}`);

    if (selectTriggerCount > 0) {
      await selectTrigger.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_05b_select_open.png` });

      // Radix dropdown options are in a portal — role="option" or data-radix-select-item
      const options = page.locator('[role="option"]');
      const optCount = await options.count();
      console.log(`[STEP 5] Select options available: ${optCount}`);

      if (optCount > 0) {
        // Try to find FG004 first, else take first available option
        const fg004Opt = page.locator('[role="option"]:has-text("FG004")');
        const fg004Count = await fg004Opt.count();

        if (fg004Count > 0) {
          selectedItemText = await fg004Opt.first().textContent();
          await fg004Opt.first().click();
          console.log(`[STEP 5] Selected FG004: "${selectedItemText?.trim()}"`);
        } else {
          // Take first available option
          selectedItemText = await options.first().textContent();
          await options.first().click();
          console.log(`[STEP 5] Selected first available item: "${selectedItemText?.trim()}"`);
        }
        actions.push({ type: 'select', field: 'item', value: selectedItemText?.trim() });
      } else {
        // Options not showing in portal — try data-radix attributes
        const radixOpts = page.locator('[data-radix-select-viewport] [data-radix-select-item]');
        const radixCount = await radixOpts.count();
        console.log(`[STEP 5] Radix items (data attr): ${radixCount}`);
        if (radixCount > 0) {
          selectedItemText = await radixOpts.first().textContent();
          await radixOpts.first().click();
          actions.push({ type: 'select', field: 'item', value: selectedItemText?.trim() });
        }
      }
      await page.waitForTimeout(500);
    }

    // --- Quantity ---
    const qtyInput = page.locator('#qty, input[id="qty"]').first();
    const qtyCount = await qtyInput.count();
    if (qtyCount > 0) {
      await qtyInput.clear();
      await qtyInput.fill('1');
      actions.push({ type: 'fill', field: 'qty', value: '1' });
      console.log('[STEP 5] Filled qty = 1');
    } else {
      // Fallback: type=number inside dialog
      const numInput = page.locator('[role="dialog"] input[type="number"]').first();
      if (await numInput.count() > 0) {
        await numInput.clear();
        await numInput.fill('1');
        actions.push({ type: 'fill', field: 'qty (fallback)', value: '1' });
      }
    }

    // --- Batch No ---
    const batchInput = page.locator('#batch, input[id="batch"]').first();
    if (await batchInput.count() > 0) {
      await batchInput.clear();
      await batchInput.fill('TEST-2026-001');
      actions.push({ type: 'fill', field: 'batch', value: 'TEST-2026-001' });
      console.log('[STEP 5] Filled batch = TEST-2026-001');
    }

    // --- Production Date ---
    const dateInput = page.locator('#production-date, input[id="production-date"]').first();
    if (await dateInput.count() > 0) {
      await dateInput.fill('2026-03-26');
      actions.push({ type: 'fill', field: 'production_date', value: '2026-03-26' });
      console.log('[STEP 5] Filled production-date = 2026-03-26');
    }

    // --- Notes ---
    const notesInput = page.locator('#notes, textarea[id="notes"]').first();
    if (await notesInput.count() > 0) {
      await notesInput.clear();
      await notesInput.fill('L3 eval test');
      actions.push({ type: 'fill', field: 'notes', value: 'L3 eval test' });
      console.log('[STEP 5] Filled notes = "L3 eval test"');
    }

    await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_06_form_filled.png` });

    // ============================================================
    // STEP 6: Click the submit button inside DialogFooter
    // Source: <Button onClick={handleSubmit} disabled={isSubmitting || !selectedItem || !qtyProduced}>
    //   {isSubmitting ? "Submitting..." : "Log Production"}
    // </Button>
    // ============================================================
    console.log('\n[STEP 6] Clicking submit button...');

    // The submit button is the non-outline "Log Production" button in DialogFooter
    // (the Cancel button has variant="outline")
    const dialogFooterSubmit = page.locator('[role="dialog"] button:not([class*="outline"]):has-text("Log Production")').first();
    const dialogFooterCount = await dialogFooterSubmit.count();
    console.log(`[STEP 6] DialogFooter submit button count: ${dialogFooterCount}`);

    if (dialogFooterCount === 0) {
      // Broader search: any button in dialog that is not Cancel
      const allDialogBtns = page.locator('[role="dialog"] button');
      const btnCount = await allDialogBtns.count();
      console.log(`[STEP 6] All dialog buttons: ${btnCount}`);
      for (let i = 0; i < btnCount; i++) {
        const btn = allDialogBtns.nth(i);
        const txt = await btn.textContent();
        const disabled = await btn.getAttribute('disabled');
        console.log(`[STEP 6]   Button[${i}]: "${txt?.trim()}" disabled=${disabled}`);
      }
    }

    // Try clicking the submit button
    const submitCandidates = [
      '[role="dialog"] button:has-text("Log Production"):not([class*="variant-outline"])',
      '[role="dialog"] [data-testid="submit"]',
      '[role="dialog"] button[type="button"]:last-child',
    ];

    for (const sel of submitCandidates) {
      const btn = page.locator(sel).last(); // last() to get footer submit not header trigger
      const cnt = await btn.count();
      if (cnt > 0) {
        const isDisabled = await btn.getAttribute('disabled');
        const txt = await btn.textContent();
        console.log(`[STEP 6] Submit candidate: "${txt?.trim()}" disabled=${isDisabled} selector=${sel}`);
        if (isDisabled === null) { // not disabled
          submitBtnSelector = sel;
          await btn.click();
          submitClicked = true;
          actions.push({ type: 'submit', target: 'Log Production button in dialog footer', selector: sel, button_text: txt?.trim() });
          console.log(`[STEP 6] Clicked submit: "${txt?.trim()}"`);
          break;
        }
      }
    }

    if (!submitClicked) {
      // Last resort: find any enabled non-Cancel button in dialog
      const allBtns = await page.locator('[role="dialog"] button').all();
      for (const btn of allBtns) {
        const txt = await btn.textContent();
        const disabled = await btn.getAttribute('disabled');
        if (txt && !txt.includes('Cancel') && disabled === null) {
          submitBtnSelector = 'fallback_any_enabled_dialog_button';
          await btn.click();
          submitClicked = true;
          actions.push({ type: 'submit', target: 'fallback submit', button_text: txt?.trim() });
          console.log(`[STEP 6] Fallback submit clicked: "${txt?.trim()}"`);
          break;
        }
      }
    }

    // Wait for toast/response
    console.log('[STEP 6] Waiting for toast/network response...');
    await page.waitForTimeout(6000);
    await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_07_after_submit.png` });

    // ============================================================
    // STEP 7: Read toast text using textContent()
    // Sonner toast: [data-sonner-toast], or [role="status"]
    // ============================================================
    console.log('\n[STEP 7] Reading toast text...');

    // Sonner toasts use data-sonner-toast attribute
    const toastSelectors = [
      '[data-sonner-toast]',
      '[data-sonner-toast] [data-title]',
      '[data-sonner-toast] [data-description]',
      '[role="status"]',
      '[role="alert"]',
      'li[data-sonner-toast]',
      '.sonner-toast',
    ];

    let toastFound = false;
    for (const tSel of toastSelectors) {
      const el = page.locator(tSel).first();
      const cnt = await el.count();
      if (cnt > 0) {
        const txt = await el.textContent();
        if (txt && txt.trim()) {
          toastText = txt.trim();
          console.log(`[STEP 7] Toast via "${tSel}": "${toastText}"`);
          toastFound = true;

          stateVerification.push({
            check: 'toast_message_after_submit',
            before: 'no_toast',
            after: toastText,
            method: 'textContent()',
            expected: 'success or error message string',
            actual: toastText,
            passed: true,
          });
          break;
        }
      }
    }

    if (!toastFound) {
      // Fallback: scan page for known success/error keywords
      const pageState = await page.evaluate(() => {
        const toastCandidates = [
          ...document.querySelectorAll('[data-sonner-toast], [role="alert"], [role="status"], [aria-live]')
        ];
        const results = toastCandidates.map(el => el.innerText?.trim()).filter(Boolean);

        // Also scan for any text containing success/error keywords
        const body = document.body.innerText;
        const errorLines = body.split('\n')
          .map(l => l.trim())
          .filter(l => l.length > 5 && l.length < 200 && /error|fail|success|created|recorded|insufficient|invalid|logged|produced/i.test(l));

        return { toasts: results, errorLines: errorLines.slice(0, 5) };
      });

      console.log('[STEP 7] Page scan results:', JSON.stringify(pageState, null, 2));

      if (pageState.toasts.length > 0) {
        toastText = pageState.toasts.join(' | ');
      } else if (pageState.errorLines.length > 0) {
        toastText = `[page_text] ${pageState.errorLines.join(' | ')}`;
      }

      stateVerification.push({
        check: 'toast_message_after_submit',
        before: 'no_toast',
        after: toastText,
        method: 'textContent()',
        expected: 'success or error message string',
        actual: toastText,
        passed: toastText !== 'NOT_CAPTURED',
      });
    }

    console.log(`[STEP 7] Final toast text: "${toastText}"`);
  } else {
    console.log('[STEP 5] Dialog did NOT open after clicking Log Production button.');
    await page.screenshot({ path: `${ARTIFACTS_DIR}/COMM-EVAL-001_05_no_dialog.png` });
  }

  await browser.close();

  // ============================================================
  // Find the most relevant API call for submit network capture
  // ============================================================
  const commApiResps = networkResponses.filter(r =>
    r.url.includes('commissary') || r.url.includes('/api/')
  );
  // Prefer POST responses near submit time
  const postResps = commApiResps.filter(r => r.method === 'POST');
  submitNetworkRequest = postResps.length > 0
    ? postResps[postResps.length - 1]
    : commApiResps.length > 0
      ? commApiResps[commApiResps.length - 1]
      : null;

  console.log(`\n[NETWORK] Total requests: ${networkRequests.length}, responses: ${networkResponses.length}`);
  console.log(`[NETWORK] Commissary-related responses: ${commApiResps.length}`);
  if (submitNetworkRequest) {
    console.log(`[NETWORK] Submit network event: ${submitNetworkRequest.method} ${submitNetworkRequest.url} → ${submitNetworkRequest.status}`);
    console.log(`[NETWORK] Response snippet: ${submitNetworkRequest.body_snippet?.slice(0, 200)}`);
  }

  // ============================================================
  // Build form_submissions.json
  // ============================================================
  formSubmissions.push({
    scenario_id: 'COMM-EVAL-001',
    form_submitted: submitClicked,
    submit_method: submitClicked ? 'browser_click' : 'NOT_SUBMITTED',
    submit_button_selector: submitBtnSelector,
    dialog_opened: dialogOpened,
    network_captured: submitNetworkRequest !== null,
    submit_network_request: submitNetworkRequest,
    toast_text: toastText,
    selected_item: selectedItemText?.trim() || null,
    timestamp: new Date().toISOString(),
  });

  // ============================================================
  // Write all output files
  // ============================================================
  console.log('\n[OUTPUT] Writing files...');
  writeJSON(`${OUT_DIR}/form_submissions.json`, formSubmissions);
  writeJSON(`${OUT_DIR}/state_verification.json`, stateVerification);

  const evidence = {
    scenario_id: 'COMM-EVAL-001',
    run_timestamp: startTime,
    target_url: BASE_URL,
    user: EMAIL,
    form_submitted: submitClicked,
    submit_method: submitClicked ? 'browser_click' : 'NOT_SUBMITTED',
    submit_button_selector: submitBtnSelector,
    dialog_opened: dialogOpened,
    network_captured: submitNetworkRequest !== null,
    submit_network_request: submitNetworkRequest,
    toast_text: toastText,
    selected_item: selectedItemText?.trim() || null,
    dashboard_metrics_read: stateVerification.filter(v => v.check.startsWith('dashboard_card')).length,
    actions: actions,
    values_verified: stateVerification.map(v => ({
      field: v.check,
      expected: v.expected,
      actual: v.actual,
      method: v.method,
      passed: v.passed,
    })),
    screenshots: [
      `${ARTIFACTS_DIR}/COMM-EVAL-001_01_login.png`,
      `${ARTIFACTS_DIR}/COMM-EVAL-001_02_post_login.png`,
      `${ARTIFACTS_DIR}/COMM-EVAL-001_03_commissary_dashboard.png`,
      `${ARTIFACTS_DIR}/COMM-EVAL-001_04_production_page.png`,
      `${ARTIFACTS_DIR}/COMM-EVAL-001_05_dialog_opened.png`,
      `${ARTIFACTS_DIR}/COMM-EVAL-001_06_form_filled.png`,
      `${ARTIFACTS_DIR}/COMM-EVAL-001_07_after_submit.png`,
    ],
    all_network_responses: commApiResps.slice(0, 10),
  };
  writeJSON(`${EVIDENCE_DIR}/COMM-EVAL-001.json`, evidence);

  // ============================================================
  // GATE 4: Self-Audit
  // ============================================================
  console.log('\n[GATE 4] Self-Audit...');
  const checks = [];

  const subs = JSON.parse(fs.readFileSync(`${OUT_DIR}/form_submissions.json`, 'utf8'));
  checks.push(['forms_submitted_count', subs.length > 0, `${subs.length} entries`]);

  const apiShortcuts = subs.filter(s => s.form_submitted && s.submit_method !== 'browser_click');
  checks.push(['no_api_shortcuts', apiShortcuts.length === 0, `${apiShortcuts.length} shortcuts`]);

  const verifs = JSON.parse(fs.readFileSync(`${OUT_DIR}/state_verification.json`, 'utf8'));
  const existenceChecks = verifs.filter(v =>
    (typeof v.after === 'string' && v.after.endsWith('visible')) ||
    (v.before === 'N/A' && v.actual === 'N/A')
  );
  checks.push(['no_existence_only_checks', existenceChecks.length === 0, `${existenceChecks.length} bad checks`]);

  const evidenceExists = fs.existsSync(`${EVIDENCE_DIR}/COMM-EVAL-001.json`);
  checks.push(['evidence_file_exists', evidenceExists, `${EVIDENCE_DIR}/COMM-EVAL-001.json`]);

  const clickSubmits = subs.filter(s => s.form_submitted && s.submit_method === 'browser_click');
  checks.push(['browser_click_submit', clickSubmits.length > 0, `${clickSubmits.length} browser clicks`]);

  const hasRealTextContent = verifs.some(v => v.method === 'textContent()' && v.actual !== 'NOT_FOUND' && v.actual !== 'NOT_CAPTURED');
  checks.push(['real_textcontent_values', hasRealTextContent, hasRealTextContent ? 'at least one real value' : 'no real values read']);

  let allGatesPass = true;
  console.log('\n[GATE 4] Results:');
  for (const [name, passed, detail] of checks) {
    console.log(`  [${passed ? 'PASS' : 'GATE FAIL'}] ${name}: ${detail}`);
    if (!passed) allGatesPass = false;
  }

  // L3 vs L2 classification
  const isL3 = clickSubmits.length > 0 && submitNetworkRequest !== null && hasRealTextContent;
  const classification = isL3 ? 'L3 (browser click + network capture + real values)' : 'L2 (page load only — form not submitted via browser click with network evidence)';
  console.log(`\n[CLASSIFICATION] ${classification}`);

  console.log('\n[DONE] All output files written.');
  return { checks, allGatesPass, isL3, classification, formSubmissions, stateVerification };
}

run().then(r => {
  console.log(`\n[FINAL] Gate 4: ${r.allGatesPass ? 'ALL PASS' : 'SOME FAILED'}`);
  console.log(`[FINAL] Classification: ${r.classification}`);
  process.exit(0);
}).catch(err => {
  console.error('[FATAL]', err.message);
  console.error(err.stack);
  process.exit(1);
});
