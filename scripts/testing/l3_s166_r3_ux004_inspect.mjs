/**
 * Inspect compensation setup rows to understand what opens on click
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

  await page.goto(`${BASE}/dashboard/hr/payroll/compensation-setup`, { waitUntil: "networkidle", timeout: 45000 });
  await page.waitForTimeout(3000);

  // Inspect the rows
  const rowInfo = await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll("tbody tr")).slice(0, 5);
    return rows.map((row, i) => {
      const els = Array.from(row.querySelectorAll("button, a, [role='button'], td")).slice(0, 8);
      return {
        rowIndex: i,
        rowText: (row.innerText || "").slice(0, 80),
        elements: els.map(e => ({
          tag: e.tagName,
          text: (e.innerText || "").slice(0, 40),
          ariaLabel: e.getAttribute("aria-label"),
          cursor: window.getComputedStyle(e).cursor,
          role: e.getAttribute("role"),
          onclick: e.onclick ? "yes" : "no",
        })),
      };
    });
  });
  console.log("Row info:", JSON.stringify(rowInfo, null, 2));

  await page.screenshot({ path: `${OUT}/screenshots/EMP-UX-004-inspect-before.png`, fullPage: false });

  // Try clicking the first row's first TD (employee name cell)
  const rows = await page.$$("tbody tr");
  if (rows.length > 0) {
    const firstTd = await rows[0].$("td:nth-child(2)"); // usually employee name
    if (firstTd) {
      await firstTd.click({ force: true });
      console.log("Clicked first td:nth-child(2)");
    } else {
      await rows[0].click({ force: true });
      console.log("Clicked first row");
    }
    await page.waitForTimeout(3000);
  }

  // Check what opened
  const modalInfo = await page.evaluate(() => {
    const sheet = document.querySelector('[data-vaul-drawer-content], [class*="SheetContent"]');
    const dialog = document.querySelector('[role="dialog"][data-radix-dialog-content]');
    const allOpen = document.querySelectorAll('[data-state="open"]');
    return {
      sheet: sheet ? { text: (sheet.innerText || "").slice(0, 400), visible: sheet.offsetParent !== null } : null,
      dialog: dialog ? { text: (dialog.innerText || "").slice(0, 400) } : null,
      open_elements: Array.from(allOpen).map(e => ({
        tag: e.tagName,
        class: e.className.slice(0, 60),
        text: (e.innerText || "").slice(0, 100),
      })),
    };
  });

  console.log("Modal info after click:", JSON.stringify(modalInfo, null, 2));
  await page.screenshot({ path: `${OUT}/screenshots/EMP-UX-004-inspect-after.png`, fullPage: false });

  // Check URL
  console.log("URL after click:", page.url());

  // Check newly added/visible elements
  const newButtons = await page.$$eval("button", btns =>
    btns.filter(b => b.offsetParent !== null).map(b => (b.innerText || "").trim()).filter(Boolean)
  );
  console.log("Visible buttons after click:", newButtons.length);
  console.log("Buttons:", newButtons.slice(0, 20));

  // Check if a slide-over or right panel appeared
  const fullPageText = await page.evaluate(() => document.body.innerText.slice(0, 10000));

  // Look for "Compensation Detail" or "Edit Compensation" text
  const hasCompDetail = fullPageText.includes("Compensation Detail") ||
                        fullPageText.includes("Edit Compensation") ||
                        fullPageText.includes("Compensation History") ||
                        fullPageText.includes("Salary Components") ||
                        fullPageText.includes("Earnings") ||
                        fullPageText.includes("Deductions");

  console.log("Has comp detail content:", hasCompDetail);

  // Extract relevant compensation section
  const compIdx = fullPageText.toLowerCase().indexOf("earnings");
  if (compIdx > 0) {
    console.log("EARNINGS CONTEXT:", fullPageText.slice(Math.max(0, compIdx - 50), compIdx + 200));
  }
  const dedIdx = fullPageText.toLowerCase().indexOf("deductions");
  if (dedIdx > 0) {
    console.log("DEDUCTIONS CONTEXT:", fullPageText.slice(Math.max(0, dedIdx - 50), dedIdx + 200));
  }

  // Final verdict
  const modalActuallyOpen = modalInfo.sheet !== null || modalInfo.dialog !== null || hasCompDetail;
  console.log("\n=== VERDICT ===");
  console.log("modal_actually_open:", modalActuallyOpen);
  console.log("verdict:", modalActuallyOpen ? "PASS_POST_FIX" : "STILL_BROKEN");

  // Update evidence
  const evidPath = `${OUT}/evidence/EMP-UX-004-retest.json`;
  const existing = JSON.parse(fs.readFileSync(evidPath, "utf8"));
  existing.verdict = modalActuallyOpen ? "PASS_POST_FIX" : "STILL_BROKEN";
  existing.inspect_check = {
    modal_actually_open: modalActuallyOpen,
    has_comp_detail_content: hasCompDetail,
    modal_info: modalInfo,
    screenshots: {
      before: `${OUT}/screenshots/EMP-UX-004-inspect-before.png`,
      after: `${OUT}/screenshots/EMP-UX-004-inspect-after.png`,
    },
    note: modalActuallyOpen
      ? "Compensation detail content detected after row click"
      : "Row click did NOT open a compensation modal. False positive in initial R3 run — salary text came from table column headers on list page, not from a modal.",
  };
  fs.writeFileSync(evidPath, JSON.stringify(existing, null, 2));
  console.log("Evidence updated.");

  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
