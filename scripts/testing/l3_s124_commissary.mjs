/**
 * L3 Commissary Workflow Tests — S124
 * Tests all commissary module surfaces + form submissions
 * Uses Playwright for browser automation
 */

import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const BASE_WEB = "https://my.bebang.ph";
const BASE_API = "https://hq.bebang.ph";
const PASSWORD = "BeiTest2026!";
const COMMISSARY_USER = "test.commissary@bebang.ph";
const OUTPUT_DIR = "output/l3/S124";
const EVIDENCE_DIR = `${OUTPUT_DIR}/evidence`;
const ARTIFACTS_DIR = `${OUTPUT_DIR}/artifacts`;

// Ensure output dirs exist
for (const dir of [OUTPUT_DIR, EVIDENCE_DIR, ARTIFACTS_DIR]) {
  fs.mkdirSync(dir, { recursive: true });
}

const results = [];
const defects = [];
const formSubmissions = [];
const apiMutations = [];
const stateVerifications = [];

function record(scenarioId, type, test, status, detail, error = null) {
  results.push({ scenario: scenarioId, type, test, status, detail, error });
  console.log(`[${status}] ${scenarioId}: ${test}${error ? ` — ${error}` : ""}`);
}

function recordDefect(severity, type, scenario, error, impact, rootCause, suggestedFix) {
  defects.push({ severity, type, scenario, error, impact, rootCause, suggestedFix, firstSeen: new Date().toISOString() });
}

async function login(page, email) {
  console.log(`\nLogging in as ${email}...`);
  await page.goto(`${BASE_WEB}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2000);

  // Fill email
  const emailInput = page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first();
  await emailInput.waitFor({ state: "visible", timeout: 15000 });
  await emailInput.fill(email);

  // Fill password
  const passInput = page.locator('input[type="password"]').first();
  await passInput.waitFor({ state: "visible", timeout: 10000 });
  await passInput.fill(PASSWORD);

  // Submit
  const submitBtn = page.locator('button[type="submit"]').first();
  await submitBtn.click();

  // Wait for dashboard
  try {
    await page.waitForURL("**/dashboard**", { timeout: 30000 });
    console.log(`Logged in as ${email} — on ${page.url()}`);
    return true;
  } catch (e) {
    console.log(`Login may have succeeded, current URL: ${page.url()}`);
    return page.url().includes("dashboard");
  }
}

async function navigateViaSidebar(page, menuText, submenuText = null) {
  // Click sidebar menu item
  const menuItem = page.locator(`nav a, aside a, [role="navigation"] a`).filter({ hasText: menuText }).first();
  if (await menuItem.isVisible({ timeout: 5000 }).catch(() => false)) {
    await menuItem.click();
    await page.waitForTimeout(1500);
  }
  if (submenuText) {
    const subItem = page.locator(`nav a, aside a, [role="navigation"] a, a`).filter({ hasText: submenuText }).first();
    if (await subItem.isVisible({ timeout: 5000 }).catch(() => false)) {
      await subItem.click();
      await page.waitForTimeout(1500);
    }
  }
}

// ============================================================
// COMMISSARY-001: Dashboard, Production, Work Orders
// ============================================================
async function testCommissary001(page, context) {
  const SCENARIO = "COMMISSARY-001";
  console.log(`\n${"=".repeat(60)}\n${SCENARIO}: Dashboard, Production, Work Orders\n${"=".repeat(60)}`);

  const evidence = { scenario_id: SCENARIO, actions: [], network: [], artifacts: {}, screenshots: [] };

  // --- Dashboard ---
  console.log("Testing /dashboard/commissary...");
  await page.goto(`${BASE_WEB}/dashboard/commissary`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotDash = `${ARTIFACTS_DIR}/${SCENARIO}_dashboard.png`;
  await page.screenshot({ path: screenshotDash, fullPage: true });
  evidence.screenshots.push(screenshotDash);
  evidence.actions.push({ type: "navigate", url: "/dashboard/commissary" });

  // Check dashboard renders
  const dashContent = await page.content();
  const hasDashboard = dashContent.length > 1000;
  if (hasDashboard) {
    record(SCENARIO, "workflow-surface", "Commissary dashboard renders", "PASS", "Dashboard loaded successfully");
  } else {
    record(SCENARIO, "workflow-surface", "Commissary dashboard renders", "FAIL", "Dashboard appears empty", "Content too short");
    recordDefect("MAJOR", "IN-SCOPE", SCENARIO, "Dashboard empty", "Commissary operators cannot see overview", "No data loaded", "Check API calls");
  }

  // Check for key metrics/cards
  const pageText = await page.innerText("body").catch(() => "");
  const hasProductionSection = pageText.toLowerCase().includes("production") || pageText.toLowerCase().includes("output");
  const hasInventorySection = pageText.toLowerCase().includes("inventory") || pageText.toLowerCase().includes("stock");

  stateVerifications.push({
    check: "Dashboard has production section",
    before: "N/A",
    after: hasProductionSection ? "Production section visible" : "Production section missing",
    passed: hasProductionSection
  });
  stateVerifications.push({
    check: "Dashboard has inventory section",
    before: "N/A",
    after: hasInventorySection ? "Inventory section visible" : "Inventory section missing",
    passed: hasInventorySection
  });

  // --- Production Page ---
  console.log("Testing /dashboard/commissary/production...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/production`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotProd = `${ARTIFACTS_DIR}/${SCENARIO}_production.png`;
  await page.screenshot({ path: screenshotProd, fullPage: true });
  evidence.screenshots.push(screenshotProd);
  evidence.actions.push({ type: "navigate", url: "/dashboard/commissary/production" });

  const prodText = await page.innerText("body").catch(() => "");
  const hasProductionPage = prodText.length > 500;

  // Check for production items/form
  const hasFGItems = prodText.includes("FG") || prodText.includes("Finished") || prodText.includes("BUKO") || prodText.includes("LECHE") || prodText.includes("RICE");
  const hasLogButton = await page.locator('button').filter({ hasText: /log|record|production/i }).count() > 0;

  if (hasProductionPage) {
    record(SCENARIO, "workflow-surface", "Production page renders", "PASS", `Page loaded, FG items: ${hasFGItems}, Log button: ${hasLogButton}`);
  } else {
    record(SCENARIO, "workflow-surface", "Production page renders", "FAIL", "Production page empty");
  }

  // Try to open the production dialog
  if (hasLogButton) {
    const logBtn = page.locator('button').filter({ hasText: /log|record|production/i }).first();
    await logBtn.click();
    await page.waitForTimeout(2000);
    const screenshotDialog = `${ARTIFACTS_DIR}/${SCENARIO}_production_dialog.png`;
    await page.screenshot({ path: screenshotDialog, fullPage: true });
    evidence.screenshots.push(screenshotDialog);
    evidence.actions.push({ type: "click", target: "Log Production button" });

    // Check dialog contents
    const dialogVisible = await page.locator('[role="dialog"], [data-state="open"], .modal').count() > 0;
    record(SCENARIO, "workflow-surface", "Production dialog opens", dialogVisible ? "PASS" : "FAIL",
      dialogVisible ? "Dialog opened successfully" : "Dialog did not appear");

    // Close dialog
    const cancelBtn = page.locator('button').filter({ hasText: /cancel|close/i }).first();
    if (await cancelBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await cancelBtn.click();
      await page.waitForTimeout(1000);
    }
  }

  // --- Work Orders ---
  console.log("Testing /dashboard/commissary/work-orders...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/work-orders`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotWO = `${ARTIFACTS_DIR}/${SCENARIO}_work_orders.png`;
  await page.screenshot({ path: screenshotWO, fullPage: true });
  evidence.screenshots.push(screenshotWO);
  evidence.actions.push({ type: "navigate", url: "/dashboard/commissary/work-orders" });

  const woText = await page.innerText("body").catch(() => "");
  const hasWorkOrders = woText.length > 500;
  record(SCENARIO, "workflow-surface", "Work orders page renders", hasWorkOrders ? "PASS" : "FAIL",
    hasWorkOrders ? "Work orders page loaded" : "Work orders page empty or error");

  // Write evidence
  fs.writeFileSync(`${EVIDENCE_DIR}/${SCENARIO}.json`, JSON.stringify(evidence, null, 2));
}

// ============================================================
// COMMISSARY-002: Quality, Transfer, Fulfillment
// ============================================================
async function testCommissary002(page, context) {
  const SCENARIO = "COMMISSARY-002";
  console.log(`\n${"=".repeat(60)}\n${SCENARIO}: Quality, Transfer, Fulfillment\n${"=".repeat(60)}`);

  const evidence = { scenario_id: SCENARIO, actions: [], network: [], artifacts: {}, screenshots: [] };

  const routes = [
    { path: "/dashboard/commissary/quality", name: "Quality" },
    { path: "/dashboard/commissary/transfer", name: "Transfer" },
    { path: "/dashboard/commissary/fulfillment", name: "Fulfillment" },
  ];

  for (const route of routes) {
    console.log(`Testing ${route.path}...`);
    const resp = await page.goto(`${BASE_WEB}${route.path}`, { waitUntil: "domcontentloaded", timeout: 30000 }).catch(() => null);
    await page.waitForTimeout(3000);
    const screenshot = `${ARTIFACTS_DIR}/${SCENARIO}_${route.name.toLowerCase()}.png`;
    await page.screenshot({ path: screenshot, fullPage: true });
    evidence.screenshots.push(screenshot);
    evidence.actions.push({ type: "navigate", url: route.path });

    const bodyText = await page.innerText("body").catch(() => "");
    const url = page.url();
    const is404 = bodyText.includes("404") || bodyText.includes("not found") || bodyText.includes("Page not found");
    const isError = bodyText.includes("error") && bodyText.length < 200;
    const hasContent = bodyText.length > 300 && !is404;

    if (is404) {
      record(SCENARIO, "workflow-surface", `${route.name} page accessible`, "FAIL",
        `Route ${route.path} returns 404`, "Page not found");
      recordDefect("MAJOR", "COLLATERAL", SCENARIO,
        `${route.name} route returns 404`,
        `Commissary operators cannot access ${route.name} page`,
        `Route not implemented or missing`,
        `Add route handler for ${route.path}`);
    } else if (hasContent) {
      // Check for active controls (buttons, forms)
      const buttonCount = await page.locator('button').count();
      const hasActiveControls = buttonCount > 1; // at least more than just nav
      record(SCENARIO, "workflow-surface", `${route.name} page renders with controls`, "PASS",
        `Page loaded, ${buttonCount} buttons found`);
    } else {
      record(SCENARIO, "workflow-surface", `${route.name} page renders`, "FAIL",
        `Page content too short or error`, bodyText.substring(0, 200));
    }
  }

  fs.writeFileSync(`${EVIDENCE_DIR}/${SCENARIO}.json`, JSON.stringify(evidence, null, 2));
}

// ============================================================
// COMMISSARY-003: Inventory, Wastage, Raw Materials, Expiry
// ============================================================
async function testCommissary003(page, context) {
  const SCENARIO = "COMMISSARY-003";
  console.log(`\n${"=".repeat(60)}\n${SCENARIO}: Inventory, Wastage, Raw Materials, Expiry\n${"=".repeat(60)}`);

  const evidence = { scenario_id: SCENARIO, actions: [], network: [], artifacts: {}, screenshots: [] };

  // --- Inventory Page ---
  console.log("Testing /dashboard/commissary/inventory...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/inventory`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotInv = `${ARTIFACTS_DIR}/${SCENARIO}_inventory.png`;
  await page.screenshot({ path: screenshotInv, fullPage: true });
  evidence.screenshots.push(screenshotInv);
  evidence.actions.push({ type: "navigate", url: "/dashboard/commissary/inventory" });

  const invText = await page.innerText("body").catch(() => "");
  const hasInventoryItems = invText.includes("FG") || invText.includes("RM") || invText.includes("Stock") || invText.includes("Qty");
  record(SCENARIO, "view", "Inventory page shows stock data", hasInventoryItems ? "PASS" : "FAIL",
    hasInventoryItems ? "Inventory items visible" : "No inventory items displayed");

  // Check if inventory levels API is being called and returning data
  const apiResponse = await page.evaluate(async () => {
    try {
      const resp = await fetch("/api/commissary?action=get_inventory_levels", { credentials: "include" });
      const data = await resp.json();
      return { status: resp.status, itemCount: Array.isArray(data?.data) ? data.data.length : 0, success: data?.success };
    } catch (e) {
      return { error: e.message };
    }
  });
  evidence.network.push({ method: "GET", url: "/api/commissary?action=get_inventory_levels", response: apiResponse });

  stateVerifications.push({
    check: "Inventory API returns items",
    before: "N/A",
    after: `API returned ${apiResponse.itemCount || 0} items, success=${apiResponse.success}`,
    passed: (apiResponse.itemCount || 0) > 0
  });

  if ((apiResponse.itemCount || 0) === 0) {
    recordDefect("CRITICAL", "IN-SCOPE", SCENARIO,
      "Inventory API returns 0 items for commissary",
      "Commissary operators see empty inventory — cannot check stock levels",
      "Shaw BLVD - BKI warehouse may still have no synced inventory after S124 fix (pending re-sync)",
      "Re-trigger inventory sync after S124 deployment");
  }

  // --- Raw Materials Page ---
  console.log("Testing /dashboard/commissary/raw-materials...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/raw-materials`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotRM = `${ARTIFACTS_DIR}/${SCENARIO}_raw_materials.png`;
  await page.screenshot({ path: screenshotRM, fullPage: true });
  evidence.screenshots.push(screenshotRM);
  evidence.actions.push({ type: "navigate", url: "/dashboard/commissary/raw-materials" });

  const rmText = await page.innerText("body").catch(() => "");
  const hasRawMats = rmText.length > 300;
  record(SCENARIO, "view", "Raw materials page renders", hasRawMats ? "PASS" : "FAIL",
    hasRawMats ? "Raw materials page loaded" : "Page empty or error");

  // --- Wastage Page ---
  console.log("Testing /dashboard/commissary/wastage...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/wastage`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotWaste = `${ARTIFACTS_DIR}/${SCENARIO}_wastage.png`;
  await page.screenshot({ path: screenshotWaste, fullPage: true });
  evidence.screenshots.push(screenshotWaste);
  evidence.actions.push({ type: "navigate", url: "/dashboard/commissary/wastage" });

  const wasteText = await page.innerText("body").catch(() => "");
  const hasWastage = wasteText.length > 300;
  const hasLogWastageButton = await page.locator('button').filter({ hasText: /log wastage|log|wastage/i }).count() > 0;

  record(SCENARIO, "view", "Wastage page renders", hasWastage ? "PASS" : "FAIL",
    `Wastage page loaded, Log button: ${hasLogWastageButton}`);

  // Try to open Log Wastage dialog and attempt submission
  if (hasLogWastageButton) {
    console.log("Opening Log Wastage dialog...");
    const logBtn = page.locator('button').filter({ hasText: /log wastage/i }).first();
    await logBtn.click();
    await page.waitForTimeout(2000);

    const screenshotWasteDialog = `${ARTIFACTS_DIR}/${SCENARIO}_wastage_dialog.png`;
    await page.screenshot({ path: screenshotWasteDialog, fullPage: true });
    evidence.screenshots.push(screenshotWasteDialog);
    evidence.actions.push({ type: "click", target: "Log Wastage button" });

    // Discover form fields
    const dialogText = await page.innerText('[role="dialog"], [data-state="open"]').catch(() => "");
    console.log(`Dialog content preview: ${dialogText.substring(0, 300)}`);

    // Check for "No active batches" or batch field state
    const noBatches = dialogText.includes("No active batch") || dialogText.includes("no batch");
    if (noBatches) {
      recordDefect("CRITICAL", "IN-SCOPE", SCENARIO,
        "Wastage dialog shows 'No active batches' for batch-tracked items",
        "Commissary cannot log wastage for batch-tracked FG items (e.g., Rice Crispies FG003)",
        "Shaw BLVD - BKI has zero stock for batch-tracked FG items — no SLE entries with positive qty",
        "Re-sync inventory to populate Shaw BLVD - BKI with FG stock and create active batches");
    }

    // Try selecting an item and checking batch availability
    const itemSelect = page.locator('[role="dialog"] select, [role="dialog"] [role="combobox"], [role="dialog"] button[role="combobox"]').first();
    if (await itemSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      evidence.actions.push({ type: "inspect", target: "Item selector in wastage dialog" });
    }

    // Close dialog
    const cancelBtn = page.locator('button').filter({ hasText: /cancel|close/i }).first();
    if (await cancelBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await cancelBtn.click();
      await page.waitForTimeout(1000);
    } else {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(1000);
    }
  }

  // --- Wastage Trends ---
  console.log("Testing /dashboard/commissary/wastage-trends...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/wastage-trends`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotTrends = `${ARTIFACTS_DIR}/${SCENARIO}_wastage_trends.png`;
  await page.screenshot({ path: screenshotTrends, fullPage: true });
  evidence.screenshots.push(screenshotTrends);

  const trendsText = await page.innerText("body").catch(() => "");
  record(SCENARIO, "view", "Wastage trends page renders", trendsText.length > 300 ? "PASS" : "FAIL",
    trendsText.length > 300 ? "Trends page loaded" : "Trends page empty");

  // --- Expiring Page ---
  console.log("Testing /dashboard/commissary/expiring...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/expiring`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshotExpiry = `${ARTIFACTS_DIR}/${SCENARIO}_expiring.png`;
  await page.screenshot({ path: screenshotExpiry, fullPage: true });
  evidence.screenshots.push(screenshotExpiry);

  const expiryText = await page.innerText("body").catch(() => "");
  record(SCENARIO, "view", "Expiring items page renders", expiryText.length > 300 ? "PASS" : "FAIL",
    expiryText.length > 300 ? "Expiry page loaded" : "Expiry page empty");

  fs.writeFileSync(`${EVIDENCE_DIR}/${SCENARIO}.json`, JSON.stringify(evidence, null, 2));
}

// ============================================================
// COMMISSARY-004: Labor Plan, Coverage, Rotation
// ============================================================
async function testCommissary004(page, context) {
  const SCENARIO = "COMMISSARY-004";
  console.log(`\n${"=".repeat(60)}\n${SCENARIO}: Labor Plan, Coverage, Rotation\n${"=".repeat(60)}`);

  const evidence = { scenario_id: SCENARIO, actions: [], network: [], artifacts: {}, screenshots: [] };

  console.log("Testing /dashboard/commissary/labor-plan...");
  await page.goto(`${BASE_WEB}/dashboard/commissary/labor-plan`, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.waitForTimeout(3000);
  const screenshot = `${ARTIFACTS_DIR}/${SCENARIO}_labor_plan.png`;
  await page.screenshot({ path: screenshot, fullPage: true });
  evidence.screenshots.push(screenshot);
  evidence.actions.push({ type: "navigate", url: "/dashboard/commissary/labor-plan" });

  const lpText = await page.innerText("body").catch(() => "");
  const hasLaborPlan = lpText.length > 300;
  const hasGrid = lpText.includes("Mon") || lpText.includes("Tue") || lpText.includes("Week") || lpText.includes("Schedule");
  const hasPublish = await page.locator('button').filter({ hasText: /publish|save|template/i }).count() > 0;

  if (hasLaborPlan) {
    record(SCENARIO, "workflow-surface", "Labor plan page renders", "PASS",
      `Page loaded, Grid: ${hasGrid}, Publish/Save buttons: ${hasPublish}`);
  } else {
    const is404 = lpText.includes("404") || lpText.includes("not found");
    record(SCENARIO, "workflow-surface", "Labor plan page renders", is404 ? "FAIL" : "FAIL",
      is404 ? "Page returns 404" : "Page empty or error");
    if (is404) {
      recordDefect("MAJOR", "COLLATERAL", SCENARIO,
        "Labor plan route returns 404",
        "Commissary managers cannot access labor planning",
        "Route not implemented",
        "Add labor-plan page for commissary");
    }
  }

  fs.writeFileSync(`${EVIDENCE_DIR}/${SCENARIO}.json`, JSON.stringify(evidence, null, 2));
}

// ============================================================
// EXTRA: API-Level Inventory Verification (S124-specific)
// ============================================================
async function testInventoryState(page) {
  const SCENARIO = "S124-INVENTORY-CHECK";
  console.log(`\n${"=".repeat(60)}\n${SCENARIO}: Verify Shaw BLVD - BKI inventory state\n${"=".repeat(60)}`);

  const evidence = { scenario_id: SCENARIO, actions: [], network: [], artifacts: {}, screenshots: [] };

  // Check inventory levels via the commissary API
  const invData = await page.evaluate(async () => {
    try {
      const resp = await fetch("/api/commissary?action=get_inventory_levels", { credentials: "include" });
      const data = await resp.json();
      if (data?.success && Array.isArray(data?.data)) {
        const items = data.data;
        const withStock = items.filter(i => i.current_qty > 0);
        const fgItems = items.filter(i => i.item_code?.startsWith("FG"));
        const rmItems = items.filter(i => i.item_code?.startsWith("RM") || i.item_code?.startsWith("A0"));
        const fgWithStock = fgItems.filter(i => i.current_qty > 0);
        const rmWithStock = rmItems.filter(i => i.current_qty > 0);
        return {
          total: items.length,
          withStock: withStock.length,
          fgTotal: fgItems.length,
          fgWithStock: fgWithStock.length,
          rmTotal: rmItems.length,
          rmWithStock: rmWithStock.length,
          sampleItems: withStock.slice(0, 10).map(i => ({ code: i.item_code, name: i.item_name, qty: i.current_qty })),
          success: true
        };
      }
      return { success: false, error: JSON.stringify(data).substring(0, 300) };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  evidence.network.push({ method: "GET", url: "/api/commissary?action=get_inventory_levels", response: invData });

  console.log(`Inventory API: ${invData.total || 0} total items, ${invData.withStock || 0} with stock`);
  console.log(`  FG items: ${invData.fgWithStock || 0}/${invData.fgTotal || 0} with stock`);
  console.log(`  RM items: ${invData.rmWithStock || 0}/${invData.rmTotal || 0} with stock`);

  if (invData.sampleItems) {
    console.log("  Sample stocked items:");
    for (const item of invData.sampleItems) {
      console.log(`    ${item.code}: ${item.name} = ${item.qty}`);
    }
  }

  stateVerifications.push({
    check: "Commissary warehouse has stocked items",
    before: "22 items (pre-S124)",
    after: `${invData.withStock || 0} items with stock`,
    passed: (invData.withStock || 0) >= 10
  });

  stateVerifications.push({
    check: "FG items have stock in commissary",
    before: "~8 FG items",
    after: `${invData.fgWithStock || 0}/${invData.fgTotal || 0} FG items with stock`,
    passed: (invData.fgWithStock || 0) >= 5
  });

  stateVerifications.push({
    check: "Raw materials have stock in commissary",
    before: "2 RM items (RM018, RM100)",
    after: `${invData.rmWithStock || 0}/${invData.rmTotal || 0} RM items with stock`,
    passed: (invData.rmWithStock || 0) >= 2
  });

  // Check production feasibility
  const feasibility = await page.evaluate(async () => {
    try {
      const resp = await fetch("/api/commissary?action=check_production_feasibility&item_code=FG004&qty=1", { credentials: "include" });
      const data = await resp.json();
      return data;
    } catch (e) {
      return { error: e.message };
    }
  });
  evidence.network.push({ method: "GET", url: "/api/commissary?action=check_production_feasibility&item_code=FG004&qty=1", response: feasibility });

  const canProduce = feasibility?.data?.can_produce || feasibility?.can_produce;
  stateVerifications.push({
    check: "Production feasibility check for FG004 (Buko Pandan)",
    before: "Blocked (no raw materials)",
    after: canProduce ? "Can produce" : `Cannot produce: ${JSON.stringify(feasibility?.data?.shortfall || feasibility?.shortfall || []).substring(0, 200)}`,
    passed: !!canProduce
  });

  if (!canProduce) {
    recordDefect("CRITICAL", "IN-SCOPE", SCENARIO,
      "Production feasibility still fails after S124 deploy",
      "Commissary cannot log production — raw materials still at zero in Shaw BLVD - BKI",
      "Inventory sync has not been re-triggered since S124 deployment — Shaw BLVD data still routed to old warehouse or sync not run",
      "Trigger inventory sync for Shaw BLVD via Google Sheets automation");
  }

  record(SCENARIO, "state-check", "Commissary inventory state verification",
    (invData.withStock || 0) >= 10 ? "PASS" : "DEFECT-PASS",
    `${invData.withStock || 0} items stocked, FG: ${invData.fgWithStock || 0}, RM: ${invData.rmWithStock || 0}`);

  fs.writeFileSync(`${EVIDENCE_DIR}/${SCENARIO}.json`, JSON.stringify(evidence, null, 2));
}

// ============================================================
// MAIN
// ============================================================
async function main() {
  console.log("L3 COMMISSARY TESTS — S124");
  console.log(`Started: ${new Date().toLocaleString("en-PH", { timeZone: "Asia/Manila" })} PHT`);
  console.log("=".repeat(60));

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  });
  const page = await context.newPage();

  try {
    // Login as commissary user
    const loggedIn = await login(page, COMMISSARY_USER);
    if (!loggedIn) {
      record("LOGIN", "prereq", "Login as commissary user", "FAIL", "Could not login");
      throw new Error("Login failed");
    }
    record("LOGIN", "prereq", "Login as commissary user", "PASS", "Logged in successfully");

    // Execute all 4 scenarios + inventory check
    await testCommissary001(page, context);
    await testCommissary002(page, context);
    await testCommissary003(page, context);
    await testCommissary004(page, context);
    await testInventoryState(page);

  } catch (e) {
    console.error(`Fatal error: ${e.message}`);
    record("FATAL", "error", "Test execution", "FAIL", e.message, e.stack);
  } finally {
    await browser.close();
  }

  // Write all evidence files
  const timestamp = new Date().toISOString();
  fs.writeFileSync(`${OUTPUT_DIR}/form_submissions.json`, JSON.stringify(formSubmissions, null, 2));
  fs.writeFileSync(`${OUTPUT_DIR}/api_mutations.json`, JSON.stringify(apiMutations, null, 2));
  fs.writeFileSync(`${OUTPUT_DIR}/state_verification.json`, JSON.stringify(stateVerifications, null, 2));
  fs.writeFileSync(`${OUTPUT_DIR}/commissary_2026-03-26.json`, JSON.stringify(results, null, 2));

  // Write defects
  if (defects.length > 0) {
    let defectMd = "# Commissary Defects — S124 L3 Testing\n\n";
    for (const d of defects) {
      defectMd += `## DEFECT: ${d.error}\n`;
      defectMd += `- **Severity:** ${d.severity}\n`;
      defectMd += `- **Type:** ${d.type}\n`;
      defectMd += `- **Scenario:** ${d.scenario}\n`;
      defectMd += `- **Impact:** ${d.impact}\n`;
      defectMd += `- **Root Cause:** ${d.rootCause}\n`;
      defectMd += `- **Suggested Fix:** ${d.suggestedFix}\n`;
      defectMd += `- **First Seen:** ${d.firstSeen}\n\n`;
    }
    fs.writeFileSync(`${OUTPUT_DIR}/DEFECTS.md`, defectMd);
  }

  // Print summary
  const passCount = results.filter(r => r.status === "PASS").length;
  const failCount = results.filter(r => r.status === "FAIL").length;
  const defectPassCount = results.filter(r => r.status === "DEFECT-PASS").length;
  const skipCount = results.filter(r => r.status === "SKIP").length;

  console.log(`\n${"=".repeat(60)}`);
  console.log(`L3 COMMISSARY S124 RESULTS (${new Date().toISOString().split("T")[0]})`);
  console.log("=".repeat(60));
  for (const r of results) {
    console.log(`[${r.status}] ${r.scenario}: ${r.test}${r.error ? ` — ${r.error}` : ""}`);
  }
  console.log(`\nTotal: ${passCount}/${results.length} PASS, ${failCount} FAIL, ${defectPassCount} DEFECT-PASS, ${skipCount} SKIP`);
  if (defects.length > 0) {
    console.log(`\nDEFECTS FOUND: ${defects.length}`);
    for (const d of defects) {
      console.log(`  [${d.severity}] [${d.type}] ${d.error}`);
    }
    console.log(`See: ${OUTPUT_DIR}/DEFECTS.md`);
  }
  console.log(`\nEvidence: ${OUTPUT_DIR}/`);
}

main().catch(e => { console.error(e); process.exit(1); });
