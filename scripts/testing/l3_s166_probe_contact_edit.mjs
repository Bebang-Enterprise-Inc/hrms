/**
 * Quick probe: find cell_number input in employee dialog (edit mode)
 */
import { chromium } from "playwright";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const HR_EMAIL = "test.hr@bebang.ph";

async function login(page) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', HR_EMAIL);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(800);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', HR_EMAIL).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2000);
  }
  console.log("Logged in:", page.url());
}

const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const page = await ctx.newPage();

await login(page);
await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
await page.waitForTimeout(2000);

// Open first employee
const firstRow = page.locator("tbody tr").first();
await firstRow.locator("button").first().click();
await page.waitForTimeout(2000);

const dialog = page.locator('[role="dialog"]').first();
const allButtons = await dialog.locator("button").allTextContents();
console.log("All dialog buttons:", JSON.stringify(allButtons));

const editBtns = dialog.locator("button").filter({ hasText: /^Edit$/ });
const editCount = await editBtns.count();
console.log("Edit button count:", editCount);

// For each Edit button, examine what section it belongs to and what inputs appear
for (let i = 0; i < editCount; i++) {
  const btn = editBtns.nth(i);
  // Get the section heading by walking up
  const sectionContext = await btn.evaluate(el => {
    // Walk up to find the section container
    let cur = el.parentElement;
    for (let d = 0; d < 10; d++) {
      if (!cur) break;
      const headings = cur.querySelectorAll("h1,h2,h3,h4,h5,h6,[class*='section'],[class*='heading']");
      if (headings.length) return { html: cur.outerHTML.substring(0, 300), heading: headings[0].textContent };
      cur = cur.parentElement;
    }
    return { html: el.closest('[class]')?.className, heading: 'unknown' };
  });
  console.log(`Edit button ${i} section heading:`, sectionContext.heading, '| HTML prefix:', sectionContext.html?.substring(0, 150));

  // Click this edit button and see what inputs appear
  await btn.click();
  await page.waitForTimeout(800);

  const inputs = await dialog.locator("input").evaluateAll(els =>
    els.map((e, idx) => {
      let parent = e.parentElement;
      let labelText = "";
      for (let depth = 0; depth < 8; depth++) {
        if (!parent) break;
        const lbl = parent.querySelector("label, p.font-medium, span.font-medium");
        if (lbl && lbl.textContent.trim()) { labelText = lbl.textContent.trim().substring(0, 60); break; }
        parent = parent.parentElement;
      }
      return { idx, placeholder: e.placeholder, id: e.id, value: e.value.substring(0, 20), labelText };
    })
  );
  console.log(`Inputs visible after clicking Edit ${i}:`, JSON.stringify(inputs));

  // Click Cancel/Close to reset
  const cancelBtn = dialog.locator("button").filter({ hasText: /cancel|close/i }).first();
  if (await cancelBtn.count()) await cancelBtn.click().catch(() => {});
  await page.waitForTimeout(500);
}

await browser.close();
