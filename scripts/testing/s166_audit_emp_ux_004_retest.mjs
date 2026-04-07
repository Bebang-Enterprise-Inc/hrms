/**
 * S166 audit retest — EMP-UX-004 conclusive verification.
 * User directive 2026-04-08: 5-min Playwright retest to definitively confirm
 * whether the compensation list-page row-click modal is still broken.
 *
 * Run by orchestrator directly (not subagent).
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const EMAIL = "test.hr@bebang.ph";
const PASSWORD = "BeiTest2026!";
const OUT_DIR = "output/l3/s166/AUDIT_2026-04-08/EMP-UX-004-retest";

fs.mkdirSync(OUT_DIR, { recursive: true });

async function loginMyBebang(page) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', EMAIL);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2000);
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', EMAIL).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);
  }
  await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);
  return page.url();
}

const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const page = await ctx.newPage();

const result = { retest_at: new Date().toISOString(), steps: [] };

try {
  console.log("=== EMP-UX-004 audit retest ===");
  const finalUrl = await loginMyBebang(page);
  console.log("logged in:", finalUrl);
  result.steps.push({ step: "login", url: finalUrl });

  // Navigate to compensation setup list page
  await page.goto(`${BASE}/dashboard/hr/payroll/compensation-setup`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${OUT_DIR}/01_list_page.png`, fullPage: true });
  result.steps.push({ step: "navigate to comp list", url: page.url() });

  // Inspect the table — find a row with a real employee
  const rowCount = await page.locator('tbody tr').count();
  console.log(`tbody tr count: ${rowCount}`);
  result.steps.push({ step: "row count", count: rowCount });

  // Try multiple click targets to open the row dialog
  // Strategy 1: click the first employee NAME (text, not avatar)
  const firstRow = page.locator('tbody tr').first();
  // Enumerate all buttons in the first row
  const rowButtons = await firstRow.locator('button').evaluateAll(els => els.map(b => ({ text: b.innerText?.trim().substring(0,40), ariaLabel: b.getAttribute('aria-label') })));
  console.log(`row buttons: ${JSON.stringify(rowButtons)}`);
  result.steps.push({ step: "row buttons enumeration", buttons: rowButtons });

  // Find the button containing employee name text (e.g. "ABALLAR" or any letters)
  let clicked = false;
  for (let i = 0; i < rowButtons.length; i++) {
    const txt = rowButtons[i].text || "";
    if (txt && /[A-Z]{2,}/.test(txt)) {
      console.log(`clicking button[${i}] = "${txt}"`);
      await firstRow.locator('button').nth(i).click({ force: true });
      clicked = true;
      result.steps.push({ step: "clicked button", index: i, text: txt });
      break;
    }
  }
  if (!clicked) {
    // Fallback: click the row's first cell content area
    console.log("no name button found — trying first td/cell click");
    await firstRow.locator('td').first().click({ force: true }).catch(()=>{});
    result.steps.push({ step: "fallback td click" });
  }
  await page.waitForTimeout(2500);

  await page.screenshot({ path: `${OUT_DIR}/02_after_row_click.png`, fullPage: true });
  result.steps.push({ step: "screenshot after row click" });

  // Check if a dialog opened
  const dialogCount = await page.locator('[role="dialog"]').count();
  console.log(`dialog count: ${dialogCount}`);
  result.steps.push({ step: "dialog count", count: dialogCount });

  if (dialogCount > 0) {
    // Inspect dialog content
    const dialog = page.locator('[role="dialog"]').first();
    const dialogText = await dialog.textContent();
    const dialogHtml = await dialog.innerHTML();
    fs.writeFileSync(`${OUT_DIR}/03_dialog_html.html`, dialogHtml || "");

    // Count input fields, labels, buttons in dialog
    const inputs = await dialog.locator('input').count();
    const labels = await dialog.locator('label').count();
    const buttons = await dialog.locator('button').count();
    const headings = await dialog.locator('h1, h2, h3, h4').count();

    console.log(`dialog: ${inputs} inputs, ${labels} labels, ${buttons} buttons, ${headings} headings`);
    console.log(`dialog text preview: "${dialogText?.substring(0, 200)}"`);

    result.dialog = {
      opened: true,
      text_preview: dialogText?.substring(0, 500),
      input_count: inputs,
      label_count: labels,
      button_count: buttons,
      heading_count: headings,
    };

    // Take a focused screenshot of just the dialog
    try {
      await dialog.screenshot({ path: `${OUT_DIR}/04_dialog_only.png` });
    } catch (e) {
      console.log("dialog screenshot failed:", e.message);
    }

    // Verdict logic
    if (inputs >= 3 || labels >= 5 || (dialogText && dialogText.length > 500 && /salary|allowance|deduction|base/i.test(dialogText))) {
      result.verdict = "PASS_POST_FIX";
      result.verdict_reason = "Dialog has rich content with form fields";
    } else if (inputs <= 1 && labels <= 2 && (dialogText || "").length < 200) {
      result.verdict = "STILL_BROKEN";
      result.verdict_reason = `Dialog rendered but contains only ${inputs} inputs, ${labels} labels, ${buttons} buttons. Text preview: "${(dialogText || "").substring(0, 200)}"`;
    } else {
      result.verdict = "AMBIGUOUS";
      result.verdict_reason = `Dialog has ${inputs} inputs, ${labels} labels — needs manual review`;
    }
  } else {
    result.dialog = { opened: false };
    result.verdict = "NO_DIALOG";
    result.verdict_reason = "Row click did not open a dialog at all";
  }

  console.log(`\nVERDICT: ${result.verdict}`);
  console.log(`REASON: ${result.verdict_reason}`);

} catch (e) {
  console.error("ERROR:", e.message);
  result.error = e.message;
  result.verdict = "RETEST_FAILED";
} finally {
  fs.writeFileSync(`${OUT_DIR}/RETEST_RESULT.json`, JSON.stringify(result, null, 2));
  console.log(`\nWrote ${OUT_DIR}/RETEST_RESULT.json`);
  await ctx.close();
  await browser.close();
}
