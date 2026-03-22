import { test, expect } from "@playwright/test";
import { login, screenshot, frappeApi, frappeApiPost, PORTAL_URL } from "./helpers";

/**
 * Flow B: Commissary Production -> Warehouse -> Store Delivery
 * Tests the full production-to-store delivery cycle.
 */
test.describe.serial("Flow B: Commissary to Store Delivery", () => {
  let mrName: string | null = null;

  test("B1 - Commissary Dashboard", async ({ page }) => {
    await login(page, "commissary");
    await page.goto(`${PORTAL_URL}/dashboard/commissary`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";

    // Document what's visible on the commissary dashboard
    const features = {
      has_shift: /shift|AM|PM/i.test(bodyText),
      has_production: /production/i.test(bodyText),
      has_orders: /order/i.test(bodyText),
      has_stock: /stock|inventory/i.test(bodyText),
      has_dispatch: /dispatch/i.test(bodyText),
      has_quick_actions: /quick action/i.test(bodyText),
      has_kpi: /kpi|card|total|count/i.test(bodyText),
    };

    // Check API
    const apiResp = await frappeApi(page, "hrms.api.commissary.get_commissary_dashboard");
    const apiKeys = Object.keys(apiResp?.message || apiResp || {});

    await screenshot(page, "FLOW_B", "B1_commissary_dashboard");

    console.log(`B1 UI features: ${JSON.stringify(features)}`);
    console.log(`B1 API keys: ${JSON.stringify(apiKeys)}`);
    console.log(`B1 Page URL: ${page.url()}`);
  });

  test("B2 - View Production Items", async ({ page }) => {
    await login(page, "commissary");
    await page.goto(`${PORTAL_URL}/dashboard/commissary/production`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasItems = /fg|item|product/i.test(bodyText);

    // Check API
    const apiResp = await frappeApi(page, "hrms.api.commissary.get_production_items");
    const items = apiResp?.message;

    await screenshot(page, "FLOW_B", "B2_production_items");

    console.log(`B2 has_items_in_ui=${hasItems}, api_items=${Array.isArray(items) ? items.length : JSON.stringify(items)}`);
    console.log(`B2 Page URL: ${page.url()}`);
  });

  test("B3 - Log Commissary Production", async ({ page }) => {
    await login(page, "commissary");
    await page.goto(`${PORTAL_URL}/dashboard/commissary/production`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // Try to find FG020 item in the production grid
    const itemButton = page.locator(':text("FG020")').first();
    const fg020Exists = await itemButton.count() > 0;

    if (fg020Exists) {
      await itemButton.click();
      await page.waitForTimeout(1000);

      // Fill quantity
      const qtyInput = page.locator('input[type="number"]').first();
      if (await qtyInput.count() > 0) {
        await qtyInput.fill("200");
      }

      // Fill batch
      const batchInput = page.locator('input[name*="batch"], input[placeholder*="Batch" i]').first();
      if (await batchInput.count() > 0) {
        await batchInput.fill("BATCH-E2E-001");
      }

      // Submit
      const submitBtn = page.locator('button:has-text("Submit"), button:has-text("Log")').first();
      if (await submitBtn.count() > 0) {
        await submitBtn.dispatchEvent("click");
        await page.waitForTimeout(3000);
      }
    }

    // Try API with token auth
    const apiResp = await frappeApiPost(page, "hrms.api.commissary.submit_production_output", {
      item_code: "FG020", qty: 200, batch_no: "BATCH-E2E-001",
    });

    await screenshot(page, "FLOW_B", "B3_production_logged");

    console.log(`B3 fg020_ui=${fg020Exists}, api=${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("B4 - Verify Commissary Inventory Updated", async ({ page }) => {
    await login(page, "commissary");
    await page.goto(`${PORTAL_URL}/dashboard/commissary/inventory`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";

    // Check API for inventory levels
    const apiResp = await frappeApi(page, "hrms.api.commissary.get_inventory_levels");
    const items = apiResp?.message || [];
    const fg020 = Array.isArray(items) ? items.find((i: any) => i.item_code === "FG020") : null;

    await screenshot(page, "FLOW_B", "B4_commissary_inventory");

    console.log(`B4 fg020_api=${JSON.stringify(fg020 || "not found")}, total_items=${Array.isArray(items) ? items.length : "unknown"}`);
    console.log(`B4 Page URL: ${page.url()}`);
  });

  test("B5 - View Low Stock Alerts", async ({ page }) => {
    await login(page, "commissary");
    await page.goto(`${PORTAL_URL}/dashboard/commissary/inventory`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // Look for low stock filter/toggle
    const toggle = page.locator('button:has-text("Low Stock"), label:has-text("Low")').first();
    if (await toggle.count() > 0) {
      await toggle.dispatchEvent("click");
      await page.waitForTimeout(1000);
    }

    const apiResp = await frappeApi(page, "hrms.api.commissary.get_low_stock_alerts");
    const alerts = apiResp?.message || [];

    await screenshot(page, "FLOW_B", "B5_low_stock_alerts");

    console.log(`B5 low_stock_alerts=${Array.isArray(alerts) ? alerts.length : JSON.stringify(alerts)}`);
  });

  test("B6 - Store Places Order (Material Request)", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/ordering`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasSearch = (await page.locator('input[type="search"], input[placeholder*="search" i]').count()) > 0;
    const hasItems = /fg|item|sku/i.test(bodyText);
    const hasQtyControls = (await page.locator('button:has-text("+")').count()) > 0;

    // Try UI ordering flow
    if (hasQtyControls) {
      const plusBtns = page.locator('button:has-text("+")');
      for (let i = 0; i < Math.min(await plusBtns.count(), 2); i++) {
        for (let j = 0; j < 10; j++) {
          await plusBtns.nth(i).click({ timeout: 2000 }).catch(() => {});
          await page.waitForTimeout(50);
        }
      }

      const submitBtn = page.locator('button:has-text("Submit Order"), button:has-text("Place Order")').first();
      if (await submitBtn.count() > 0) {
        await submitBtn.dispatchEvent("click");
        await page.waitForTimeout(2000);
        const confirmBtn = page.locator('button:has-text("Confirm")').first();
        if (await confirmBtn.count() > 0) {
          await confirmBtn.dispatchEvent("click");
          await page.waitForTimeout(3000);
        }
      }
    }

    // API attempt
    const apiResp = await frappeApiPost(page, "hrms.api.store.submit_order", {
      items: [{ item_code: "FG020", qty: 50 }, { item_code: "FG003", qty: 30 }],
    });
    if (apiResp?.message?.name) {
      mrName = apiResp.message.name;
    }

    await screenshot(page, "FLOW_B", "B6_store_order_placed");

    console.log(`B6 search=${hasSearch}, items=${hasItems}, qty_controls=${hasQtyControls}, mr_name=${mrName}`);
    console.log(`B6 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("B7 - Warehouse Sees Pending Order", async ({ page }) => {
    await login(page, "warehouse");
    await page.goto(`${PORTAL_URL}/dashboard/warehouse/approve`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasMR = /pending|material request|mr-|approve/i.test(bodyText);

    // API check
    const apiResp = await frappeApi(page, "hrms.api.warehouse.get_pending_material_requests");
    const pending = apiResp?.message || [];

    if (!mrName && Array.isArray(pending) && pending.length > 0) {
      mrName = pending[0].name || pending[0].mr_name;
    }

    await screenshot(page, "FLOW_B", "B7_pending_mr_list");

    console.log(`B7 hasMR_ui=${hasMR}, pending_count=${Array.isArray(pending) ? pending.length : "unknown"}, mr_name=${mrName}`);
  });

  test("B8 - Warehouse Approves Order", async ({ page }) => {
    await login(page, "warehouse");

    // Navigate to approve page
    if (mrName) {
      await page.goto(`${PORTAL_URL}/dashboard/warehouse/approve/${mrName}`);
    } else {
      await page.goto(`${PORTAL_URL}/dashboard/warehouse/approve`);
    }
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // Try approve button in UI
    const approveBtn = page.locator('button:has-text("Approve"), button:has-text("Approve All")').first();
    if (await approveBtn.count() > 0) {
      await approveBtn.dispatchEvent("click");
      await page.waitForTimeout(3000);
    }

    // API attempt
    if (mrName) {
      const apiResp = await frappeApiPost(page, "hrms.api.warehouse.approve_material_request", {
        mr_name: mrName, modifications: [],
      });
      console.log(`B8 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
    }

    await screenshot(page, "FLOW_B", "B8_mr_approved");
    console.log(`B8 mr_name=${mrName}`);
  });

  test("B9 - Warehouse Creates Stock Transfer (Dispatch)", async ({ page }) => {
    await login(page, "warehouse");
    await page.goto(`${PORTAL_URL}/dashboard/warehouse/dispatch`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasDispatch = /dispatch|transfer|ready/i.test(bodyText);

    // Try dispatch button
    const dispatchBtn = page.locator('button:has-text("Dispatch"), button:has-text("Transfer"), button:has-text("Create Transfer")').first();
    if (await dispatchBtn.count() > 0) {
      await dispatchBtn.dispatchEvent("click");
      await page.waitForTimeout(3000);
    }

    // API attempt
    if (mrName) {
      const apiResp = await frappeApiPost(page, "hrms.api.warehouse.create_stock_transfer", {
        mr_name: mrName,
      });
      console.log(`B9 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
    }

    await screenshot(page, "FLOW_B", "B9_stock_transfer");
    console.log(`B9 dispatch_content=${hasDispatch}, mr_name=${mrName}`);
  });

  test("B10 - Verify Stock Moved (Commissary Side)", async ({ page }) => {
    await login(page, "commissary");
    await page.goto(`${PORTAL_URL}/dashboard/commissary/inventory`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const apiResp = await frappeApi(page, "hrms.api.commissary.get_inventory_levels");
    const items = apiResp?.message || [];
    const fg020 = Array.isArray(items) ? items.find((i: any) => i.item_code === "FG020") : null;
    const fg003 = Array.isArray(items) ? items.find((i: any) => i.item_code === "FG003") : null;

    await screenshot(page, "FLOW_B", "B10_commissary_after_dispatch");

    console.log(`B10 FG020=${JSON.stringify(fg020 || "not found")}, FG003=${JSON.stringify(fg003 || "not found")}`);
  });

  test("B11 - Distribution Trip (Dispatch Page)", async ({ page }) => {
    await login(page, "warehouse");
    await page.goto(`${PORTAL_URL}/dashboard/warehouse/dispatch`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";

    const features = {
      coming_soon: /coming soon/i.test(bodyText),
      create_transfer_erp: /create transfer in erp/i.test(bodyText),
      trip: /trip|distribution/i.test(bodyText),
      summary: /stores|items|orders/i.test(bodyText),
    };

    const erpLink = page.locator('a[href*="hq.bebang.ph"], a[href*="stock-entry"]');
    features.coming_soon = features.coming_soon || (await erpLink.count()) > 0;

    // Try dispatch API
    const apiResp = await frappeApiPost(page, "hrms.api.dispatch.create_trip", {
      trip_date: "2026-02-08", route_name: "E2E Test Route", stops: [],
    });

    await screenshot(page, "FLOW_B", "B11_trip_departed");

    console.log(`B11 features: ${JSON.stringify(features)}`);
    console.log(`B11 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
    console.log(`B11 NOTE: Dispatch may be partially functional - trip creation may need Frappe Desk`);
  });

  test("B12 - Store Confirms Receiving", async ({ page }) => {
    await login(page, "store_staff");

    // Try multiple possible routes
    const routes = [
      "/dashboard/store-ops/receiving",
      "/dashboard/store-ops/deliveries",
      "/dashboard/inventory/receiving",
    ];

    let foundPage = false;
    for (const route of routes) {
      await page.goto(`${PORTAL_URL}${route}`);
      await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
      const bodyText = await page.locator("body").textContent() || "";
      if (!bodyText.includes("404") && !bodyText.includes("Page not found")) {
        foundPage = true;
        break;
      }
    }

    const bodyText = await page.locator("body").textContent() || "";
    const hasDelivery = /deliver|receiv|confirm/i.test(bodyText);

    // Try confirm button
    const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Received"), button:has-text("Accept")').first();
    if (await confirmBtn.count() > 0) {
      await confirmBtn.dispatchEvent("click");
      await page.waitForTimeout(3000);
    }

    await screenshot(page, "FLOW_B", "B12_store_receiving_confirmed");

    console.log(`B12 found_page=${foundPage}, delivery_content=${hasDelivery}`);
    console.log(`B12 final_url=${page.url()}`);
    console.log(`B12 NOTE: Store receiving may be placeholder - documenting actual state`);
  });
});
