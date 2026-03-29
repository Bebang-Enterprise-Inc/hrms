import { chromium } from "playwright";
import fs from "fs";

const BASE = "https://my.bebang.ph";
const OUT = "output/l3/S124/ux_review";
fs.mkdirSync(OUT, { recursive: true });

const pages = [
  { path: "/dashboard/commissary", name: "dashboard" },
  { path: "/dashboard/commissary/production", name: "production" },
  { path: "/dashboard/commissary/wastage", name: "wastage" },
  { path: "/dashboard/commissary/quality", name: "quality" },
  { path: "/dashboard/commissary/inventory", name: "inventory" },
  { path: "/dashboard/commissary/raw-materials", name: "raw_materials" },
  { path: "/dashboard/commissary/expiring", name: "expiring" },
  { path: "/dashboard/commissary/transfer", name: "transfer" },
  { path: "/dashboard/commissary/fulfillment", name: "fulfillment" },
  { path: "/dashboard/commissary/work-orders", name: "work_orders" },
  { path: "/dashboard/commissary/labor-plan", name: "labor_plan" },
  { path: "/dashboard/commissary/wastage-trends", name: "wastage_trends" },
];

async function main() {
  const browser = await chromium.launch({ headless: true });

  // Desktop context
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  // Login
  console.log("Logging in...");
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2000);
  await page.locator('input[autocomplete="username"], input[name="email"], input[type="email"]').first().fill("test.commissary@bebang.ph");
  await page.locator('input[type="password"]').first().fill("BeiTest2026!");
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL("**/dashboard**", { timeout: 30000 });
  console.log("Login successful.");

  for (const p of pages) {
    console.log(`Capturing ${p.name}...`);
    await page.goto(`${BASE}${p.path}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(4000);

    // Desktop
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${OUT}/${p.name}_desktop.png`, fullPage: true });
    console.log(`  -> ${p.name}_desktop.png`);

    // Mobile
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${OUT}/${p.name}_mobile.png`, fullPage: true });
    console.log(`  -> ${p.name}_mobile.png`);

    // Reset
    await page.setViewportSize({ width: 1280, height: 900 });
  }

  await browser.close();
  console.log(`\nDone. ${pages.length * 2} screenshots saved to ${OUT}/`);
}

main().catch(e => { console.error(e); process.exit(1); });
