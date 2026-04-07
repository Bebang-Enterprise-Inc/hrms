/**
 * Precise EMP-UX-004 retest — checks if clicking a compensation row opens a modal
 * with rich content vs just table column headers
 */
import { chromium } from "playwright";
import fs from "fs";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const HR_USER = "test.hr@bebang.ph";
const OUT = "F:/Dropbox/Projects/BEI-ERP/output/l3/s166/lanes/retest/r3_ux_reobserve";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  // Login Frappe
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 45000 });
  await page.fill('input[name="usr"]', HR_USER);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);

  // Login my.bebang.ph
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(800);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', HR_USER).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
  console.log("Logged in:", page.url());

  // Navigate to compensation setup
  await page.goto(`${BASE}/dashboard/hr/payroll/compensation-setup`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(3000);

  // Capture baseline buttons
  const baselineButtons = await page.$$eval('button, a[role="button"]', els =>
    els.map(e => (e.innerText || "").trim()).filter(Boolean)
  );
  console.log(`Baseline buttons: ${baselineButtons.length}`);

  await page.screenshot({ path: `${OUT}/screenshots/EMP-UX-004-precise-baseline.png`, fullPage: false });

  // Click first employee button
  let clicked = false;
  let clickInfo = "none";

  const empBtns = await page.$$("tbody tr td button");
  if (empBtns.length > 0) {
    await empBtns[0].scrollIntoViewIfNeeded().catch(() => {});
    await empBtns[0].click({ force: true });
    clicked = true;
    clickInfo = "tbody td button[0]";
    console.log("Clicked first td button");
  } else {
    const rows = await page.$$("tbody tr");
    if (rows.length > 0) {
      await rows[0].click();
      clicked = true;
      clickInfo = "tbody tr[0]";
      console.log("Clicked first row");
    }
  }

  // Wait for modal animation
  await page.waitForTimeout(3000);

  // Check post-click state
  const postButtons = await page.$$eval('button, a[role="button"]', els =>
    els.map(e => (e.innerText || "").trim()).filter(Boolean)
  );
  const newButtons = postButtons.filter(b => !baselineButtons.includes(b));
  const postUrl = page.url();

  // Check overlays
  const overlays = await page.evaluate(() => {
    const sels = [
      '[role="dialog"]',
      '[data-radix-dialog-content]',
      '[data-vaul-drawer-content]',
      '[class*="SheetContent"]',
      '[class*="DrawerContent"]',
      '[class*="DialogContent"]',
      '[data-state="open"]',
      '[aria-modal="true"]',
    ];
    const found = [];
    for (const sel of sels) {
      const el = document.querySelector(sel);
      if (el) {
        found.push({
          selector: sel,
          visible: el.offsetParent !== null,
          text: (el.innerText || "").slice(0, 300),
        });
      }
    }
    return found;
  });

  console.log("Post-click URL:", postUrl);
  console.log("New buttons:", newButtons.length, newButtons.slice(0, 5));
  console.log("Overlays:", overlays.length);
  overlays.forEach(o => console.log(" Overlay:", o.selector, "visible:", o.visible, "text:", o.text.slice(0, 80)));

  await page.screenshot({ path: `${OUT}/screenshots/EMP-UX-004-precise-postclick.png`, fullPage: false });

  const urlChanged = postUrl !== `${BASE}/dashboard/hr/payroll/compensation-setup`;
  const modalOpened = overlays.length > 0 || newButtons.length > 3 || urlChanged;

  const result = {
    modal_detected: modalOpened,
    overlay_count: overlays.length,
    new_buttons_count: newButtons.length,
    new_buttons: newButtons,
    url_changed: urlChanged,
    post_url: postUrl,
    click_info: clickInfo,
    overlays_detail: overlays,
    verdict: modalOpened ? "PASS_POST_FIX" : "STILL_BROKEN",
    note: modalOpened
      ? "Modal/sheet/navigation detected after row click"
      : "Row click produced no modal, no overlay, no navigation — modal still absent. False positive in initial R3 run (salary text was from table column headers, not modal content).",
  };

  console.log("\n=== PRECISE RESULT ===");
  console.log(JSON.stringify(result, null, 2));

  // Update evidence
  const evidPath = `${OUT}/evidence/EMP-UX-004-retest.json`;
  const existing = JSON.parse(fs.readFileSync(evidPath, "utf8"));
  existing.verdict = result.verdict;
  existing.precise_check = result;
  existing.verdict_note = result.note;
  fs.writeFileSync(evidPath, JSON.stringify(existing, null, 2));
  console.log("Evidence updated:", evidPath);

  await browser.close();
  return result;
}

main().catch(e => { console.error(e); process.exit(1); });
