/**
 * L3 S124 Retest — Production & Wastage Form Submissions
 * After inventory re-sync: Shaw BLVD - BKI now has 99 items with stock.
 * Focused retest: fill form, submit, verify SUCCESS toast.
 */
import { chromium } from "playwright";
import fs from "fs";

const BASE = "https://my.bebang.ph";
const USER = "test.commissary@bebang.ph";
const PW = "BeiTest2026!";
const OUT = "output/l3/S124";
const ART = `${OUT}/artifacts`;
for (const d of [OUT, ART]) fs.mkdirSync(d, { recursive: true });

const formSubmissions = [];
const stateVerification = [];

function ts() { return new Date().toISOString(); }

async function snap(page, name) {
  const p = `${ART}/retest_${name}.png`;
  await page.screenshot({ path: p, fullPage: false });
  console.log(`  [SCREENSHOT] ${p}`);
  return p;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  // Capture all console errors
  const consoleErrors = [];
  page.on("console", msg => { if (msg.type() === "error") consoleErrors.push(msg.text()); });

  // ── LOGIN ──────────────────────────────────────────────────────────
  console.log("\n=== LOGIN ===");
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2000);
  await page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first().fill(USER);
  await page.locator('input[type="password"]').first().fill(PW);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL("**/dashboard**", { timeout: 30000 });
  console.log("  Logged in OK");
  await page.waitForTimeout(2000);

  // ── TEST 1: PRODUCTION ─────────────────────────────────────────────
  console.log("\n=== TEST 1: PRODUCTION FORM ===");
  await page.goto(`${BASE}/dashboard/commissary/production`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  await snap(page, "01_production_page");

  // Read current state
  const prodPageText = await page.locator("body").innerText();
  console.log("  Page loaded. Looking for Log Production button...");

  // Click "Log Production" trigger button
  const logProdBtn = page.locator('button').filter({ hasText: /Log Production/i }).first();
  await logProdBtn.click();
  await page.waitForTimeout(2000);
  await snap(page, "02_production_dialog");
  console.log("  Dialog opened.");

  // Discover form elements in dialog
  const dialogEls = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button[role="combobox"], input[type="number"], input[type="text"]'))
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
      .map(e => ({
        tag: e.tagName, type: e.type || "", role: e.getAttribute("role") || "",
        text: (e.innerText || "").substring(0, 80),
        placeholder: e.placeholder || "",
        y: Math.round(e.getBoundingClientRect().y)
      }));
  });
  console.log("  Form elements:", JSON.stringify(dialogEls, null, 2));

  // Select item from combobox
  console.log("  Clicking item combobox...");
  await page.locator('button[role="combobox"]').first().click();
  await page.waitForTimeout(1500);
  await snap(page, "03_production_combobox_open");

  // List available options
  const options = await page.locator('[role="option"]').allInnerTexts();
  console.log(`  Available options (${options.length}):`, options.slice(0, 10).join(" | "));

  // Select first option
  await page.locator('[role="option"]').first().click();
  await page.waitForTimeout(1500);
  const selectedItem = await page.locator('button[role="combobox"]').first().innerText();
  console.log(`  Selected item: ${selectedItem}`);

  // Fill quantity
  const qtyInput = page.locator('input[type="number"]').first();
  await qtyInput.fill("1");
  console.log("  Quantity filled: 1");
  await snap(page, "04_production_filled");

  // Set up network listener BEFORE clicking submit
  const prodNetworkPromise = page.waitForResponse(
    resp => resp.url().includes("/api") && resp.request().method() === "POST",
    { timeout: 15000 }
  ).catch(e => null);

  // Find and click the submit button (the one inside the dialog, y > 300)
  console.log("  Looking for submit button in dialog...");
  const allBtns = await page.locator('button').filter({ hasText: /Log Production/i }).all();
  let submitClicked = false;
  for (const btn of allBtns) {
    const box = await btn.boundingBox();
    if (box && box.y > 300) {
      console.log(`  Found dialog submit button at y=${Math.round(box.y)}, clicking...`);
      await btn.click();
      submitClicked = true;
      break;
    }
  }
  if (!submitClicked) {
    // Fallback: click last matching button
    console.log("  No button at y>300 found, trying last matching button...");
    const lastBtn = allBtns[allBtns.length - 1];
    if (lastBtn) {
      await lastBtn.click();
      submitClicked = true;
    }
  }
  console.log(`  Submit clicked: ${submitClicked}`);

  // Wait for network response
  const prodResponse = await prodNetworkPromise;
  let prodNetworkResult = null;
  if (prodResponse) {
    const respStatus = prodResponse.status();
    let respBody = null;
    try { respBody = await prodResponse.json(); } catch { try { respBody = await prodResponse.text(); } catch {} }
    prodNetworkResult = { url: prodResponse.url(), status: respStatus, body: respBody };
    console.log(`  Network response: ${respStatus} ${prodResponse.url()}`);
    console.log(`  Response body:`, JSON.stringify(respBody).substring(0, 500));
  } else {
    console.log("  No network response captured (timeout or no POST)");
  }

  // Wait for toast
  let prodToast = null;
  try {
    await page.waitForSelector('[data-sonner-toast]', { timeout: 10000 });
    prodToast = await page.locator('[data-sonner-toast]').first().innerText();
    console.log(`  TOAST: "${prodToast}"`);
  } catch {
    console.log("  No toast appeared within 10s");
    // Try alternative toast selectors
    const altToast = await page.locator('[role="status"], .toast, [data-toast]').first().innerText().catch(() => null);
    if (altToast) {
      prodToast = altToast;
      console.log(`  ALT TOAST: "${altToast}"`);
    }
  }
  await snap(page, "05_production_after_submit");

  // Check if dialog closed (success indicator)
  await page.waitForTimeout(2000);
  const dialogStillOpen = await page.locator('[role="dialog"]').isVisible().catch(() => false);
  console.log(`  Dialog still open: ${dialogStillOpen}`);

  const prodSuccess = prodToast && /success|recorded|logged|created/i.test(prodToast) && !(/insufficient|error|fail/i.test(prodToast));
  console.log(`  PRODUCTION RESULT: ${prodSuccess ? "SUCCESS" : "FAILED"}`);

  formSubmissions.push({
    test: "PRODUCTION",
    timestamp: ts(),
    item_selected: selectedItem,
    quantity: 1,
    submit_clicked: submitClicked,
    network_response: prodNetworkResult,
    toast_text: prodToast,
    dialog_closed: !dialogStillOpen,
    success: prodSuccess,
    console_errors: [...consoleErrors]
  });

  stateVerification.push({
    test: "PRODUCTION",
    timestamp: ts(),
    page_loaded: true,
    dialog_opened: true,
    items_available: options.length,
    item_selected: selectedItem,
    form_filled: true,
    submit_clicked: submitClicked,
    network_status: prodNetworkResult?.status || "NO_RESPONSE",
    toast_text: prodToast,
    dialog_closed_after_submit: !dialogStillOpen,
    verdict: prodSuccess ? "PASS" : "FAIL"
  });

  // ── TEST 2: WASTAGE ─────────────────────────────────────────────────
  console.log("\n=== TEST 2: WASTAGE FORM ===");
  consoleErrors.length = 0; // reset for this test
  await page.goto(`${BASE}/dashboard/commissary/wastage`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  await snap(page, "06_wastage_page");

  // Read current wastage stats
  const wastPageText = await page.locator("body").innerText();
  const entriesMatch = wastPageText.match(/(\d+)\s*ENTRIES/i) || wastPageText.match(/ENTRIES\s*(\d+)/i);
  const entriesBefore = entriesMatch ? parseInt(entriesMatch[1]) : null;
  console.log(`  Wastage page loaded. ENTRIES before: ${entriesBefore}`);

  // Click "Log Wastage" trigger
  const logWastBtn = page.locator('button').filter({ hasText: /Log Wastage/i }).first();
  await logWastBtn.click();
  await page.waitForTimeout(2000);
  await snap(page, "07_wastage_dialog");
  console.log("  Dialog opened.");

  // Discover form elements
  const wastDialogEls = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button[role="combobox"], input[type="number"], input[type="text"]'))
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
      .map(e => ({
        tag: e.tagName, type: e.type || "", role: e.getAttribute("role") || "",
        text: (e.innerText || "").substring(0, 80),
        placeholder: e.placeholder || "",
        y: Math.round(e.getBoundingClientRect().y)
      }));
  });
  console.log("  Form elements:", JSON.stringify(wastDialogEls, null, 2));

  // Select item from combobox INSIDE the dialog (use force to bypass overlay)
  console.log("  Clicking item combobox (inside dialog)...");
  const dialog = page.locator('[role="dialog"]');
  const dialogCombos = dialog.locator('button[role="combobox"]');
  const dialogComboCount = await dialogCombos.count();
  console.log(`  Comboboxes inside dialog: ${dialogComboCount}`);

  // First combobox in dialog = "Select item"
  await dialogCombos.first().click({ force: true });
  await page.waitForTimeout(1500);
  await snap(page, "08_wastage_item_combobox");

  const wastOptions = await page.locator('[role="option"]').allInnerTexts();
  console.log(`  Available options (${wastOptions.length}):`, wastOptions.slice(0, 10).join(" | "));

  // Select BANANA CINNAMON (known to have stock from production test) instead of first item
  let wastItemClicked = false;
  const allOpts = await page.locator('[role="option"]').all();
  for (const opt of allOpts) {
    const txt = await opt.innerText();
    if (/BANANA CINNAMON/i.test(txt)) {
      await opt.click();
      wastItemClicked = true;
      console.log(`  Clicked: ${txt}`);
      break;
    }
  }
  if (!wastItemClicked) {
    // Fallback: skip first item (CREAM CHEESE FROSTING has no stock), pick second
    console.log("  BANANA CINNAMON not found, picking second option...");
    await page.locator('[role="option"]').nth(1).click();
  }
  await page.waitForTimeout(1500);
  const wastSelectedItem = await dialogCombos.first().innerText();
  console.log(`  Selected item: ${wastSelectedItem}`);

  // Fill quantity
  const wastQty = dialog.locator('input[type="number"]').first();
  await wastQty.fill("1");
  console.log("  Quantity filled: 1");

  // Select reason (second combobox in dialog)
  console.log("  Clicking reason combobox...");
  await page.waitForTimeout(500);
  const dialogCombos2 = dialog.locator('button[role="combobox"]');
  const comboCount = await dialogCombos2.count();
  console.log(`  Comboboxes in dialog now: ${comboCount}`);
  if (comboCount >= 2) {
    await dialogCombos2.nth(1).click({ force: true });
    await page.waitForTimeout(1500);
    await snap(page, "09_wastage_reason_combobox");

    const reasonOptions = await page.locator('[role="option"]').allInnerTexts();
    console.log(`  Reason options: ${reasonOptions.join(" | ")}`);

    // Select first reason
    await page.locator('[role="option"]').first().click();
    await page.waitForTimeout(1000);
    const selectedReason = await dialogCombos2.nth(1).innerText();
    console.log(`  Selected reason: ${selectedReason}`);
  } else {
    console.log("  WARNING: Less than 2 comboboxes in dialog, trying 3rd overall...");
    // The reason combobox might be the 3rd overall combobox on page
    const allCombos = page.locator('button[role="combobox"]');
    const allCount = await allCombos.count();
    console.log(`  Total comboboxes on page: ${allCount}`);
    // Find the one with "Select reason" text
    for (let i = 0; i < allCount; i++) {
      const txt = await allCombos.nth(i).innerText();
      if (/reason/i.test(txt)) {
        await allCombos.nth(i).click({ force: true });
        await page.waitForTimeout(1500);
        const reasonOpts = await page.locator('[role="option"]').allInnerTexts();
        console.log(`  Reason options: ${reasonOpts.join(" | ")}`);
        await page.locator('[role="option"]').first().click();
        await page.waitForTimeout(1000);
        break;
      }
    }
  }

  await snap(page, "10_wastage_filled");

  // Set up network listener
  const wastNetworkPromise = page.waitForResponse(
    resp => resp.url().includes("/api") && resp.request().method() === "POST",
    { timeout: 15000 }
  ).catch(e => null);

  // Find and click the submit button in dialog
  console.log("  Looking for wastage submit button...");
  const wastBtns = await page.locator('button').filter({ hasText: /Log Wastage/i }).all();
  let wastSubmitClicked = false;
  for (const btn of wastBtns) {
    const box = await btn.boundingBox();
    if (box && box.y > 300) {
      console.log(`  Found dialog submit button at y=${Math.round(box.y)}, clicking...`);
      await btn.click();
      wastSubmitClicked = true;
      break;
    }
  }
  if (!wastSubmitClicked && wastBtns.length > 0) {
    console.log("  Fallback: clicking last matching button...");
    await wastBtns[wastBtns.length - 1].click();
    wastSubmitClicked = true;
  }
  console.log(`  Submit clicked: ${wastSubmitClicked}`);

  // Wait for network response
  const wastResponse = await wastNetworkPromise;
  let wastNetworkResult = null;
  if (wastResponse) {
    const respStatus = wastResponse.status();
    let respBody = null;
    try { respBody = await wastResponse.json(); } catch { try { respBody = await wastResponse.text(); } catch {} }
    wastNetworkResult = { url: wastResponse.url(), status: respStatus, body: respBody };
    console.log(`  Network response: ${respStatus} ${wastResponse.url()}`);
    console.log(`  Response body:`, JSON.stringify(respBody).substring(0, 500));
  } else {
    console.log("  No network response captured");
  }

  // Wait for toast
  let wastToast = null;
  try {
    await page.waitForSelector('[data-sonner-toast]', { timeout: 10000 });
    wastToast = await page.locator('[data-sonner-toast]').first().innerText();
    console.log(`  TOAST: "${wastToast}"`);
  } catch {
    console.log("  No toast appeared within 10s");
    const altToast = await page.locator('[role="status"], .toast, [data-toast]').first().innerText().catch(() => null);
    if (altToast) {
      wastToast = altToast;
      console.log(`  ALT TOAST: "${altToast}"`);
    }
  }
  await snap(page, "11_wastage_after_submit");

  // Check dialog closed
  await page.waitForTimeout(2000);
  const wastDialogStillOpen = await page.locator('[role="dialog"]').isVisible().catch(() => false);
  console.log(`  Dialog still open: ${wastDialogStillOpen}`);

  const wastSuccess = wastToast && /success|recorded|logged|created/i.test(wastToast) && !(/insufficient|error|fail/i.test(wastToast));
  console.log(`  WASTAGE RESULT: ${wastSuccess ? "SUCCESS" : "FAILED"}`);

  // Re-read ENTRIES count
  let entriesAfter = null;
  if (wastSuccess || !wastDialogStillOpen) {
    await page.waitForTimeout(2000);
    // Reload to get fresh count
    await page.goto(`${BASE}/dashboard/commissary/wastage`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(3000);
    const wastPageText2 = await page.locator("body").innerText();
    const entriesMatch2 = wastPageText2.match(/(\d+)\s*ENTRIES/i) || wastPageText2.match(/ENTRIES\s*(\d+)/i);
    entriesAfter = entriesMatch2 ? parseInt(entriesMatch2[1]) : null;
    console.log(`  ENTRIES after: ${entriesAfter}`);
    if (entriesBefore !== null && entriesAfter !== null) {
      console.log(`  ENTRIES delta: ${entriesAfter - entriesBefore}`);
    }
    await snap(page, "12_wastage_after_reload");
  }

  formSubmissions.push({
    test: "WASTAGE",
    timestamp: ts(),
    item_selected: wastSelectedItem,
    quantity: 1,
    submit_clicked: wastSubmitClicked,
    network_response: wastNetworkResult,
    toast_text: wastToast,
    dialog_closed: !wastDialogStillOpen,
    success: wastSuccess,
    console_errors: [...consoleErrors]
  });

  stateVerification.push({
    test: "WASTAGE",
    timestamp: ts(),
    page_loaded: true,
    dialog_opened: true,
    items_available: wastOptions.length,
    item_selected: wastSelectedItem,
    form_filled: true,
    submit_clicked: wastSubmitClicked,
    network_status: wastNetworkResult?.status || "NO_RESPONSE",
    toast_text: wastToast,
    dialog_closed_after_submit: !wastDialogStillOpen,
    entries_before: entriesBefore,
    entries_after: entriesAfter,
    entries_increased: entriesAfter !== null && entriesBefore !== null ? entriesAfter > entriesBefore : null,
    verdict: wastSuccess ? "PASS" : "FAIL"
  });

  // ── SUMMARY ─────────────────────────────────────────────────────────
  console.log("\n=== SUMMARY ===");
  console.log(`  Production: ${prodSuccess ? "PASS" : "FAIL"} | Toast: "${prodToast}"`);
  console.log(`  Wastage:    ${wastSuccess ? "PASS" : "FAIL"} | Toast: "${wastToast}"`);
  console.log(`  Entries:    Before=${entriesBefore} After=${entriesAfter}`);

  // Write output files
  fs.writeFileSync(`${OUT}/retest_form_submissions.json`, JSON.stringify(formSubmissions, null, 2));
  fs.writeFileSync(`${OUT}/retest_state_verification.json`, JSON.stringify(stateVerification, null, 2));
  console.log(`\n  Output written to ${OUT}/retest_*.json`);

  await browser.close();
  console.log("\nDone.");
})();
