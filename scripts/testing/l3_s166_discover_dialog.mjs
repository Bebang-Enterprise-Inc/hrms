/**
 * S166 — Discover Add New Employee dialog structure.
 * Login as HR, open dialog, dump every field/button/combobox so we can
 * write reliable selectors.
 */
import { chromium } from "playwright";
import fs from "fs";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const PASSWORD = "BeiTest2026!";
const RUN_DIR = "data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution";
fs.mkdirSync(RUN_DIR, { recursive: true });

async function login(page, email) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', email);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForLoadState("networkidle", { timeout: 30000 });
  }
}

async function run() {
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage", "--disable-gpu"] });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  try {
    await login(page, "test.hr@bebang.ph");
    await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${RUN_DIR}/discover_01_emp_master.png` });

    // Click Add New Employee
    const addBtn = page.getByRole("button", { name: /add new employee/i }).first();
    await addBtn.waitFor({ state: "visible", timeout: 10000 });
    await addBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${RUN_DIR}/discover_02_dialog_open.png`, fullPage: true });

    // Dump dialog DOM structure
    const dialogHtml = await page.locator('[role="dialog"]').first().innerHTML().catch(() => "no dialog");
    fs.writeFileSync(`${RUN_DIR}/discover_dialog_html.html`, dialogHtml);

    // Enumerate inputs in the dialog
    const inputs = await page.locator('[role="dialog"] input, [role="dialog"] select, [role="dialog"] textarea, [role="dialog"] button').evaluateAll(
      els => els.map(el => ({
        tag: el.tagName,
        type: el.getAttribute("type"),
        name: el.getAttribute("name"),
        id: el.id,
        placeholder: el.getAttribute("placeholder"),
        ariaLabel: el.getAttribute("aria-label"),
        role: el.getAttribute("role"),
        text: el.innerText?.substring(0, 80),
      }))
    );
    fs.writeFileSync(`${RUN_DIR}/discover_dialog_inputs.json`, JSON.stringify(inputs, null, 2));

    // Enumerate labels in the dialog
    const labels = await page.locator('[role="dialog"] label').evaluateAll(
      els => els.map(el => ({ text: el.innerText?.trim(), for: el.getAttribute("for") }))
    );
    fs.writeFileSync(`${RUN_DIR}/discover_dialog_labels.json`, JSON.stringify(labels, null, 2));

    console.log(`\n=== DIALOG INPUTS (${inputs.length}) ===`);
    for (const i of inputs) console.log(JSON.stringify(i));
    console.log(`\n=== DIALOG LABELS (${labels.length}) ===`);
    for (const l of labels) console.log(JSON.stringify(l));
  } finally {
    await ctx.close();
    await browser.close();
  }
}
run().catch(e => { console.error(e); process.exit(1); });
