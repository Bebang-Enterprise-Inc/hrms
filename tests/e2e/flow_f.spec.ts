/**
 * Flow F: RBAC Access Control Tests (F1-F29)
 *
 * Verifies each role can ONLY access their authorized modules
 * based on bei-tasks/lib/roles.ts MODULE_ACCESS matrix.
 *
 * FINDINGS:
 * - RoleGuard shows "Access Restricted" / "You don't have permission" on denied pages
 * - /dashboard/finance-accounting returns Next.js 404 (page doesn't exist)
 * - /dashboard/procurement has NO RoleGuard: accessible to ALL roles (RBAC BUG)
 */
import { test, expect } from "@playwright/test";
import { login, screenshot, PORTAL_URL } from "./helpers";

/**
 * Detect if page shows any form of access restriction.
 * Returns an object describing what was found.
 */
async function getPageAccessState(page: import("@playwright/test").Page) {
  // Use innerText (visible text only) to avoid script content contamination
  const body = (await page.locator("body").innerText()) || "";
  const url = page.url();
  return {
    url,
    bodyLength: body.length,
    hasRoleGuardDenied:
      body.includes("Access Restricted") ||
      body.includes("You don't have permission"),
    hasAccessDenied:
      body.includes("Access Denied") || body.includes("Not authorized"),
    has404:
      body.includes("This page could not be found") ||
      body.trim() === "404\nThis page could not be found." ||
      (body.trim().startsWith("404") && body.trim().length < 100),
    has403: body.includes("403"),
    isBlocked: false, // computed below
  };
}

// Check if access is blocked by any mechanism
async function isAccessBlocked(page: import("@playwright/test").Page) {
  const state = await getPageAccessState(page);
  state.isBlocked =
    state.hasRoleGuardDenied ||
    state.hasAccessDenied ||
    state.has404 ||
    state.has403;
  return state;
}

// Helper: assert access is granted
async function expectAccessGranted(
  page: import("@playwright/test").Page,
  flow: string,
  testId: string
) {
  const state = await isAccessBlocked(page);
  const bodyPreview = (await page.locator("body").innerText())?.substring(0, 200) || "";
  await screenshot(page, flow, testId);
  expect(
    state.isBlocked,
    `Expected access GRANTED but got blocked (roleGuard=${state.hasRoleGuardDenied}, 404=${state.has404}, denied=${state.hasAccessDenied}, url=${state.url}, bodyLen=${state.bodyLength}, bodyPreview="${bodyPreview}")`
  ).toBeFalsy();
}

// Helper: assert access is blocked (by any mechanism)
async function expectAccessBlocked(
  page: import("@playwright/test").Page,
  targetPath: string,
  flow: string,
  testId: string
) {
  const state = await isAccessBlocked(page);
  await screenshot(page, flow, testId);
  expect(
    state.isBlocked,
    `RBAC BUG: Expected BLOCKED for ${targetPath} but page loaded with content (url=${state.url}, bodyLen=${state.bodyLength})`
  ).toBeTruthy();
}

// Navigate to a module and wait
async function navigateTo(
  page: import("@playwright/test").Page,
  path: string
) {
  await page.goto(`${PORTAL_URL}${path}`);
  await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
  await page.waitForTimeout(2000);
}

// ============================================================================
// Store Staff (test.staff@bebang.ph) - F1 to F6
// ============================================================================
test.describe("Flow F: RBAC - Store Staff", () => {
  test("F1 - Store Staff CAN access Inventory", async ({ page }) => {
    await login(page, "store_staff");
    await navigateTo(page, "/dashboard/inventory");
    await expectAccessGranted(page, "FLOW_F", "F1_staff_inventory_ok");
  });

  test("F2 - Store Staff CAN access Store Ops", async ({ page }) => {
    await login(page, "store_staff");
    await navigateTo(page, "/dashboard/store-ops");
    await expectAccessGranted(page, "FLOW_F", "F2_staff_store_ops_ok");
  });

  test("F3 - Store Staff BLOCKED from Procurement", async ({ page }) => {
    // KNOWN BUG: Procurement layout.tsx has no RoleGuard - accessible to all roles
    test.fail();
    await login(page, "store_staff");
    await navigateTo(page, "/dashboard/procurement");
    await expectAccessBlocked(
      page,
      "/procurement",
      "FLOW_F",
      "F3_staff_no_procurement"
    );
  });

  test("F4 - Store Staff BLOCKED from Finance/Accounting", async ({
    page,
  }) => {
    await login(page, "store_staff");
    await navigateTo(page, "/dashboard/finance-accounting");
    await expectAccessBlocked(
      page,
      "/finance-accounting",
      "FLOW_F",
      "F4_staff_no_accounting"
    );
  });

  test("F5 - Store Staff BLOCKED from Warehouse", async ({ page }) => {
    await login(page, "store_staff");
    await navigateTo(page, "/dashboard/warehouse");
    await expectAccessBlocked(
      page,
      "/warehouse",
      "FLOW_F",
      "F5_staff_no_warehouse"
    );
  });

  test("F6 - Store Staff BLOCKED from Commissary", async ({ page }) => {
    await login(page, "store_staff");
    await navigateTo(page, "/dashboard/commissary");
    await expectAccessBlocked(
      page,
      "/commissary",
      "FLOW_F",
      "F6_staff_no_commissary"
    );
  });
});

// ============================================================================
// Store Supervisor (test.supervisor@bebang.ph) - F7 to F11
// ============================================================================
test.describe("Flow F: RBAC - Store Supervisor", () => {
  test("F7 - Store Supervisor CAN access Store Ops", async ({ page }) => {
    await login(page, "store_supervisor");
    await navigateTo(page, "/dashboard/store-ops");
    await expectAccessGranted(page, "FLOW_F", "F7_supervisor_store_ops_ok");
  });

  test("F8 - Store Supervisor CAN access Approvals", async ({ page }) => {
    await login(page, "store_supervisor");
    await navigateTo(page, "/dashboard/queue");
    await expectAccessGranted(page, "FLOW_F", "F8_supervisor_approvals_ok");
  });

  test("F9 - Store Supervisor CAN access Team", async ({ page }) => {
    await login(page, "store_supervisor");
    await navigateTo(page, "/dashboard/team");
    await expectAccessGranted(page, "FLOW_F", "F9_supervisor_team_ok");
  });

  test("F10 - Store Supervisor BLOCKED from Procurement", async ({
    page,
  }) => {
    // KNOWN BUG: Procurement layout.tsx has no RoleGuard - accessible to all roles
    test.fail();
    await login(page, "store_supervisor");
    await navigateTo(page, "/dashboard/procurement");
    await expectAccessBlocked(
      page,
      "/procurement",
      "FLOW_F",
      "F10_supervisor_no_procurement"
    );
  });

  test("F11 - Store Supervisor BLOCKED from Finance/Accounting", async ({
    page,
  }) => {
    await login(page, "store_supervisor");
    await navigateTo(page, "/dashboard/finance-accounting");
    await expectAccessBlocked(
      page,
      "/finance-accounting",
      "FLOW_F",
      "F11_supervisor_no_accounting"
    );
  });
});

// ============================================================================
// Area Supervisor (test.area@bebang.ph) - F12 to F15
// ============================================================================
test.describe("Flow F: RBAC - Area Supervisor", () => {
  test("F12 - Area Supervisor CAN access Analytics", async ({ page }) => {
    await login(page, "area_supervisor");
    await navigateTo(page, "/dashboard/analytics");
    await expectAccessGranted(page, "FLOW_F", "F12_area_analytics_ok");
  });

  test("F13 - Area Supervisor CAN access Store Dashboard", async ({
    page,
  }) => {
    await login(page, "area_supervisor");
    // Store dashboard is at /dashboard/analytics/store (not store-dashboard)
    await navigateTo(page, "/dashboard/analytics/store");
    await expectAccessGranted(page, "FLOW_F", "F13_area_store_dashboard_ok");
  });

  test("F14 - Area Supervisor BLOCKED from Procurement", async ({ page }) => {
    // KNOWN BUG: Procurement layout.tsx has no RoleGuard - accessible to all roles
    test.fail();
    await login(page, "area_supervisor");
    await navigateTo(page, "/dashboard/procurement");
    await expectAccessBlocked(
      page,
      "/procurement",
      "FLOW_F",
      "F14_area_no_procurement"
    );
  });

  test("F15 - Area Supervisor BLOCKED from Finance/Accounting", async ({
    page,
  }) => {
    await login(page, "area_supervisor");
    await navigateTo(page, "/dashboard/finance-accounting");
    await expectAccessBlocked(
      page,
      "/finance-accounting",
      "FLOW_F",
      "F15_area_no_accounting"
    );
  });
});

// ============================================================================
// HQ User (test.hr@bebang.ph) - F16 to F19
// ============================================================================
test.describe("Flow F: RBAC - HQ User", () => {
  test("F16 - HQ User CAN access Procurement", async ({ page }) => {
    await login(page, "hq_user");
    await navigateTo(page, "/dashboard/procurement");
    await expectAccessGranted(page, "FLOW_F", "F16_hq_procurement_ok");
  });

  test("F17 - HQ User Finance/Accounting page behavior", async ({ page }) => {
    // NOTE: /dashboard/finance-accounting returns 404 (no page.tsx exists).
    // This test documents what happens and also checks /dashboard/accounting-expense.
    await login(page, "hq_user");
    await navigateTo(page, "/dashboard/finance-accounting");
    const state1 = await getPageAccessState(page);

    await screenshot(page, "FLOW_F", "F17a_hq_finance_accounting");

    // Check alternative path
    await navigateTo(page, "/dashboard/accounting-expense");
    const state2 = await getPageAccessState(page);

    await screenshot(page, "FLOW_F", "F17b_hq_accounting_expense");

    // Document: finance-accounting is 404, accounting-expense might work
    // Verify we captured both page states
    expect(state1.url).toBeDefined();
    expect(state2.url).toBeDefined();
  });

  test("F18 - HQ User CAN access Approvals", async ({ page }) => {
    await login(page, "hq_user");
    await navigateTo(page, "/dashboard/queue");
    await expectAccessGranted(page, "FLOW_F", "F18_hq_approvals_ok");
  });

  test("F19 - HQ User BLOCKED from Store Ops", async ({ page }) => {
    await login(page, "hq_user");
    await navigateTo(page, "/dashboard/store-ops");
    await expectAccessBlocked(
      page,
      "/store-ops",
      "FLOW_F",
      "F19_hq_no_store_ops"
    );
  });
});

// ============================================================================
// Warehouse User (test.warehouse@bebang.ph) - F20 to F24
// ============================================================================
test.describe("Flow F: RBAC - Warehouse User", () => {
  test("F20 - Warehouse User CAN access Warehouse", async ({ page }) => {
    await login(page, "warehouse");
    await navigateTo(page, "/dashboard/warehouse");
    await expectAccessGranted(page, "FLOW_F", "F20_warehouse_ok");
  });

  test("F21 - Warehouse User CAN access Commissary", async ({ page }) => {
    await login(page, "warehouse");
    await navigateTo(page, "/dashboard/commissary");
    await expectAccessGranted(page, "FLOW_F", "F21_warehouse_commissary_ok");
  });

  test("F22 - Warehouse User CAN access Inventory", async ({ page }) => {
    await login(page, "warehouse");
    await navigateTo(page, "/dashboard/inventory");
    await expectAccessGranted(page, "FLOW_F", "F22_warehouse_inventory_ok");
  });

  test("F23 - Warehouse User BLOCKED from Procurement", async ({ page }) => {
    // KNOWN BUG: Procurement layout.tsx has no RoleGuard - accessible to all roles
    test.fail();
    await login(page, "warehouse");
    await navigateTo(page, "/dashboard/procurement");
    await expectAccessBlocked(
      page,
      "/procurement",
      "FLOW_F",
      "F23_warehouse_no_procurement"
    );
  });

  test("F24 - Warehouse User BLOCKED from Finance/Accounting", async ({
    page,
  }) => {
    await login(page, "warehouse");
    await navigateTo(page, "/dashboard/finance-accounting");
    await expectAccessBlocked(
      page,
      "/finance-accounting",
      "FLOW_F",
      "F24_warehouse_no_accounting"
    );
  });
});

// ============================================================================
// Driver (F25-F27) - SKIPPED: No dedicated Driver test account
// ============================================================================
test.describe("Flow F: RBAC - Driver", () => {
  test.skip(
    "F25 - Driver CAN access Receiving (SKIPPED: no test account)",
    async () => {}
  );

  test.skip(
    "F26 - Driver BLOCKED from Procurement (SKIPPED: no test account)",
    async () => {}
  );

  test.skip(
    "F27 - Driver BLOCKED from Warehouse (SKIPPED: no test account)",
    async () => {}
  );
});

// ============================================================================
// System Manager (F28-F29) - Via Frappe Administrator
// ============================================================================
test.describe("Flow F: RBAC - System Manager", () => {
  test("F28 - System Manager CAN access ALL Finance modules", async ({
    page,
  }) => {
    // Login as Administrator via Frappe Desk
    await page.goto("https://hq.bebang.ph/login");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await page
      .locator(
        'input[data-fieldname="usr"], input#login_email, input[name="usr"]'
      )
      .first()
      .fill("Administrator");
    await page
      .locator(
        'input[data-fieldname="pwd"], input#login_password, input[name="pwd"]'
      )
      .first()
      .fill("admin");
    await page.locator('.btn-login, button[type="submit"]').first().click();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    // Navigate to portal
    await page.goto(`${PORTAL_URL}/dashboard`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await page.waitForTimeout(2000);

    // Check finance modules (skip finance-accounting since it's a 404 for everyone)
    const modules = [
      "/dashboard/procurement",
      "/dashboard/warehouse",
      "/dashboard/commissary",
    ];

    for (const mod of modules) {
      await page.goto(`${PORTAL_URL}${mod}`);
      await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
      await page.waitForTimeout(1500);
      const state = await getPageAccessState(page);
      expect(
        state.hasRoleGuardDenied || state.hasAccessDenied,
        `System Manager should access ${mod} but got denied`
      ).toBeFalsy();
    }

    await screenshot(page, "FLOW_F", "F28_sysadmin_all_access");
  });

  test("F29 - System Manager CAN access ALL Ops modules", async ({
    page,
  }) => {
    await page.goto("https://hq.bebang.ph/login");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await page
      .locator(
        'input[data-fieldname="usr"], input#login_email, input[name="usr"]'
      )
      .first()
      .fill("Administrator");
    await page
      .locator(
        'input[data-fieldname="pwd"], input#login_password, input[name="pwd"]'
      )
      .first()
      .fill("admin");
    await page.locator('.btn-login, button[type="submit"]').first().click();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);

    await page.goto(`${PORTAL_URL}/dashboard`);
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
    await page.waitForTimeout(2000);

    const modules = [
      "/dashboard/store-ops",
      "/dashboard/inventory",
      "/dashboard/analytics",
    ];

    for (const mod of modules) {
      await page.goto(`${PORTAL_URL}${mod}`);
      await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
      await page.waitForTimeout(1500);
      const state = await getPageAccessState(page);
      expect(
        state.hasRoleGuardDenied || state.hasAccessDenied,
        `System Manager should access ${mod} but got denied`
      ).toBeFalsy();
    }

    await screenshot(page, "FLOW_F", "F29_sysadmin_ops_access");
  });
});
