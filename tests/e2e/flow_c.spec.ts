import { test, expect } from "@playwright/test";
import { login, screenshot, frappeApi, frappeApiPost, PORTAL_URL } from "./helpers";

/**
 * Flow C: Store Inventory Management Cycle
 * Tests cycle counts, variance reporting, rejection/resubmission, returns, shelf life extensions.
 */
test.describe.serial("Flow C: Store Inventory Management", () => {
  let cycleCountName: string | null = null;
  let varianceName: string | null = null;
  let shelfExtName: string | null = null;

  test("C1 - Submit Cycle Count", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/counts`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const pageLoaded = !bodyText.includes("404");

    // Look for "New Count" button
    const newCountBtn = page.locator('button:has-text("New Count"), button:has-text("New"), a:has-text("New Count")').first();
    const hasNewBtn = await newCountBtn.count() > 0;

    if (hasNewBtn) {
      await newCountBtn.dispatchEvent("click");
      await page.waitForTimeout(2000);

      // Try to fill cycle count form
      const qtyInputs = page.locator('input[type="number"]');
      const inputCount = await qtyInputs.count();
      if (inputCount >= 2) {
        await qtyInputs.nth(0).fill("48"); // FG020: system 50, count 48
        await qtyInputs.nth(1).fill("30"); // FG003: system 30, count 30
      }

      // Submit
      const submitBtn = page.locator('button:has-text("Submit"), button:has-text("Save")').first();
      if (await submitBtn.count() > 0) {
        await submitBtn.dispatchEvent("click");
        await page.waitForTimeout(3000);
      }
    }

    // Try navigating to new count page
    if (!hasNewBtn) {
      await page.goto(`${PORTAL_URL}/dashboard/inventory/counts/new`);
      await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    }

    // API attempt
    const apiResp = await frappeApiPost(page, "hrms.api.inventory.submit_cycle_count", {
      items: [
        { item_code: "FG020", system_qty: 50, counted_qty: 48 },
        { item_code: "FG003", system_qty: 30, counted_qty: 30 },
      ],
    });
    if (apiResp?.message?.name) {
      cycleCountName = apiResp.message.name;
    }

    await screenshot(page, "FLOW_C", "C1_cycle_count_submitted");

    console.log(`C1 page_loaded=${pageLoaded}, new_btn=${hasNewBtn}, cycle_count=${cycleCountName}`);
    console.log(`C1 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("C2 - View Cycle Count History", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/counts`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasCounts = /count|cycle|submitted|variance/i.test(bodyText);

    // Look for status filters
    const statusFilter = page.locator('select, button:has-text("Status"), [data-filter]').first();
    const hasFilter = await statusFilter.count() > 0;

    // API check
    const apiResp = await frappeApi(page, "hrms.api.inventory.get_cycle_counts");
    const counts = apiResp?.message;

    await screenshot(page, "FLOW_C", "C2_count_history");

    console.log(`C2 hasCounts=${hasCounts}, hasFilter=${hasFilter}`);
    console.log(`C2 API: ${Array.isArray(counts) ? `${counts.length} counts` : JSON.stringify(counts || apiResp?.exc_type || "error")}`);
  });

  test("C3 - Supervisor Rejects Cycle Count", async ({ page }) => {
    await login(page, "store_supervisor");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/counts`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasCounts = /count|cycle|review|pending/i.test(bodyText);

    // Try to find reject button
    const rejectBtn = page.locator('button:has-text("Reject")').first();
    if (await rejectBtn.count() > 0) {
      await rejectBtn.dispatchEvent("click");
      await page.waitForTimeout(1000);

      // Enter rejection reason
      const reasonInput = page.locator('textarea, input[name*="reason"]').first();
      if (await reasonInput.count() > 0) {
        await reasonInput.fill("Please recount FG020 - variance too high");
      }

      const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Submit")').first();
      if (await confirmBtn.count() > 0) {
        await confirmBtn.dispatchEvent("click");
        await page.waitForTimeout(2000);
      }
    }

    // API attempt
    if (cycleCountName) {
      const apiResp = await frappeApiPost(page, "hrms.api.inventory.reject_cycle_count", {
        name: cycleCountName,
        reason: "Please recount FG020 - variance too high",
      });
      console.log(`C3 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
    }

    await screenshot(page, "FLOW_C", "C3_count_rejected");
    console.log(`C3 hasCounts=${hasCounts}, cycle_count=${cycleCountName}`);
  });

  test("C4 - Staff Resubmits Cycle Count", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/counts`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // Look for resubmit button or create new count
    const resubmitBtn = page.locator('button:has-text("Resubmit"), button:has-text("Recount"), button:has-text("New Count")').first();
    if (await resubmitBtn.count() > 0) {
      await resubmitBtn.dispatchEvent("click");
      await page.waitForTimeout(2000);

      // Fill corrected counts
      const qtyInputs = page.locator('input[type="number"]');
      if (await qtyInputs.count() >= 1) {
        await qtyInputs.first().fill("49"); // FG020: corrected count
      }

      const submitBtn = page.locator('button:has-text("Submit"), button:has-text("Save")').first();
      if (await submitBtn.count() > 0) {
        await submitBtn.dispatchEvent("click");
        await page.waitForTimeout(3000);
      }
    }

    // API attempt
    const apiResp = await frappeApiPost(page, "hrms.api.inventory.resubmit_cycle_count", {
      original_count: cycleCountName,
      items: [
        { item_code: "FG020", system_qty: 50, counted_qty: 49 },
        { item_code: "FG003", system_qty: 30, counted_qty: 30 },
      ],
    });

    await screenshot(page, "FLOW_C", "C4_count_resubmitted");
    console.log(`C4 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("C5 - Supervisor Accepts Recount", async ({ page }) => {
    await login(page, "store_supervisor");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/counts`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // Look for accept/approve button
    const acceptBtn = page.locator('button:has-text("Accept"), button:has-text("Approve")').first();
    if (await acceptBtn.count() > 0) {
      await acceptBtn.dispatchEvent("click");
      await page.waitForTimeout(3000);
    }

    // API attempt
    const apiResp = await frappeApiPost(page, "hrms.api.inventory.approve_cycle_count", {
      name: cycleCountName,
    });

    await screenshot(page, "FLOW_C", "C5_recount_accepted");
    console.log(`C5 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("C6 - Report Inventory Variance", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/variances`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const pageLoaded = !bodyText.includes("404");

    // Look for new variance button
    const newBtn = page.locator('button:has-text("Report"), button:has-text("New"), a:has-text("New")').first();
    if (await newBtn.count() > 0) {
      await newBtn.dispatchEvent("click");
      await page.waitForTimeout(2000);

      // Fill variance form
      const inputs = page.locator('input, textarea, select');
      // Try to fill specific fields
      const itemSelect = page.locator('select, [role="combobox"]').first();
      if (await itemSelect.count() > 0) {
        await itemSelect.selectOption({ label: "FG020" }).catch(() => {});
      }
    }

    // API attempt
    const apiResp = await frappeApiPost(page, "hrms.api.inventory.report_variance", {
      item_code: "FG020",
      system_qty: 50,
      actual_qty: 48,
      variance_type: "Shortage",
      explanation: "2 units found damaged during count",
    });
    if (apiResp?.message?.name) {
      varianceName = apiResp.message.name;
    }

    await screenshot(page, "FLOW_C", "C6_variance_reported");
    console.log(`C6 page_loaded=${pageLoaded}, variance=${varianceName}`);
    console.log(`C6 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("C7 - View Variances List", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/variances`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasVariances = /variance|discrepancy|shortage/i.test(bodyText);

    // API check
    const apiResp = await frappeApi(page, "hrms.api.inventory.get_variances");

    await screenshot(page, "FLOW_C", "C7_variances_list");
    console.log(`C7 hasVariances=${hasVariances}`);
    console.log(`C7 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("C8 - Submit Return Request", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/returns`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const pageLoaded = !bodyText.includes("404");

    // Look for new return button
    const newBtn = page.locator('button:has-text("New Return"), button:has-text("New"), a:has-text("Return")').first();
    if (await newBtn.count() > 0) {
      await newBtn.dispatchEvent("click");
      await page.waitForTimeout(2000);

      // Check for return reasons dropdown
      const reasonSelect = page.locator('select, [role="combobox"]');
      const hasReasons = await reasonSelect.count() > 0;
      console.log(`C8 reason_dropdown=${hasReasons}`);
    }

    // API attempt
    const apiResp = await frappeApiPost(page, "hrms.api.inventory.submit_return_request", {
      items: [{
        item_code: "FG020",
        qty: 2,
        reason: "Damaged Packaging",
        notes: "Found during cycle count",
      }],
    });

    await screenshot(page, "FLOW_C", "C8_return_submitted");
    console.log(`C8 page_loaded=${pageLoaded}`);
    console.log(`C8 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("C9 - Request Shelf Life Extension", async ({ page }) => {
    await login(page, "store_staff");
    await page.goto(`${PORTAL_URL}/dashboard/inventory/shelf-life`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const pageLoaded = !bodyText.includes("404");

    // Look for new request button
    const newBtn = page.locator('button:has-text("New"), button:has-text("Request"), a:has-text("New")').first();
    if (await newBtn.count() > 0) {
      await newBtn.dispatchEvent("click");
      await page.waitForTimeout(2000);

      // Try to fill shelf life form
      const inputs = page.locator('input');
      const inputCount = await inputs.count();
      console.log(`C9 form_inputs=${inputCount}`);
    }

    // API attempt
    const apiResp = await frappeApiPost(page, "hrms.api.inventory.request_shelf_extension", {
      item_code: "FG003",
      original_expiry: "2026-02-10",
      requested_expiry: "2026-02-15",
      qty: 5,
      reason: "Product still in good condition, visual inspection passed",
    });
    if (apiResp?.message?.name) {
      shelfExtName = apiResp.message.name;
    }

    await screenshot(page, "FLOW_C", "C9_shelf_extension_requested");
    console.log(`C9 page_loaded=${pageLoaded}, extension=${shelfExtName}`);
    console.log(`C9 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
  });

  test("C10 - Supervisor Approves Shelf Life Extension", async ({ page }) => {
    await login(page, "store_supervisor");

    // Try shelf life page or approval queue
    await page.goto(`${PORTAL_URL}/dashboard/inventory/shelf-life`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    const bodyText = await page.locator("body").textContent() || "";
    const hasExtensions = /shelf|extension|expiry|approve/i.test(bodyText);

    // Look for approve button
    const approveBtn = page.locator('button:has-text("Approve")').first();
    if (await approveBtn.count() > 0) {
      await approveBtn.dispatchEvent("click");
      await page.waitForTimeout(2000);

      // Fill modified expiry date if there's an input
      const dateInput = page.locator('input[type="date"]').first();
      if (await dateInput.count() > 0) {
        await dateInput.fill("2026-02-14");
      }

      const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Submit")').first();
      if (await confirmBtn.count() > 0) {
        await confirmBtn.dispatchEvent("click");
        await page.waitForTimeout(2000);
      }
    }

    // API attempt
    if (shelfExtName) {
      const apiResp = await frappeApiPost(page, "hrms.api.inventory.approve_shelf_extension", {
        name: shelfExtName,
        approved_expiry: "2026-02-14",
      });
      console.log(`C10 API: ${JSON.stringify(apiResp?.message || apiResp?.exc_type || "error")}`);
    }

    await screenshot(page, "FLOW_C", "C10_shelf_extension_approved");
    console.log(`C10 hasExtensions=${hasExtensions}, extension=${shelfExtName}`);
  });
});
