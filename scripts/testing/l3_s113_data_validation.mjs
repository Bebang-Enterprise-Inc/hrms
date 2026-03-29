/**
 * S113 L3 Data Validation — Verify API responses return accurate financial data
 * Tests actual backend responses, not just rendering.
 */
import { chromium } from "playwright";
import { writeFileSync, readFileSync } from "fs";
import { join } from "path";

const BASE = "https://my.bebang.ph";
const DIR = "output/l3/s113";
const HR = { email: "test.hr@bebang.ph", pw: "BeiTest2026!" };

const dataChecks = [];

function check(name, result, details) {
  dataChecks.push({ check: name, passed: result, details, ts: new Date().toISOString() });
  console.log(`  [${result ? "PASS" : "FAIL"}] ${name}: ${typeof details === "object" ? JSON.stringify(details) : details}`);
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.waitForTimeout(1500);
  await page.locator('input[name="email"], input[type="email"]').first().fill(HR.email);
  await page.locator('input[type="password"]').first().fill(HR.pw);
  await page.locator('button[type="submit"]').first().click();
  await page.waitForURL("**/dashboard**", { timeout: 12000 });
}

async function run() {
  console.log("=".repeat(60));
  console.log("S113 DATA VALIDATION — Financial Accuracy Check");
  console.log("=".repeat(60));

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();

  // Capture ALL API responses
  const apiResponses = {};
  page.on("response", async (resp) => {
    const url = resp.url();
    if (url.includes("hrms.api.payroll.")) {
      const endpoint = url.split("hrms.api.payroll.")[1]?.split("?")[0];
      try {
        const body = await resp.json();
        apiResponses[endpoint] = { status: resp.status(), data: body?.message, url };
      } catch {
        apiResponses[endpoint] = { status: resp.status(), error: "non-json", url };
      }
    }
  });

  try {
    await login(page);

    // ── 1. Dashboard API ──
    console.log("\n=== get_payroll_dashboard ===");
    await page.goto(`${BASE}/dashboard/hr/payroll`, { waitUntil: "networkidle", timeout: 25000 });
    await page.waitForTimeout(3000);

    const dashboard = apiResponses["get_payroll_dashboard"];
    if (dashboard) {
      console.log(`  Status: ${dashboard.status}`);
      const d = dashboard.data;

      // Check response shape matches our interface
      check("dashboard.has_from_date", d?.from_date !== undefined, d?.from_date);
      check("dashboard.has_to_date", d?.to_date !== undefined, d?.to_date);
      check("dashboard.has_processing_status", d?.processing_status !== undefined, typeof d?.processing_status);
      check("dashboard.has_summary", d?.summary !== undefined, typeof d?.summary);
      check("dashboard.has_recent_entries", Array.isArray(d?.recent_entries), `is array: ${Array.isArray(d?.recent_entries)}`);

      // Validate processing status shape
      const ps = d?.processing_status;
      if (ps) {
        check("processing_status.has_total_employees", ps.total_employees !== undefined, ps.total_employees);
        check("processing_status.has_processed", ps.processed !== undefined, ps.processed);
        check("processing_status.has_pending", ps.pending !== undefined, ps.pending);
        check("processing_status.has_failed", ps.failed !== undefined, ps.failed);
        // Verify math: processed + pending + failed should be <= total_employees or near it
        const sum = (ps.processed || 0) + (ps.pending || 0) + (ps.failed || 0);
        const total = ps.total_employees || 0;
        check("processing_status.math_consistent", total === 0 || sum <= total * 2,
          `processed(${ps.processed})+pending(${ps.pending})+failed(${ps.failed})=${sum} vs total=${total}`);
      }

      // Validate summary shape
      const s = d?.summary;
      if (s) {
        check("summary.has_summary_block", s.summary !== undefined, typeof s.summary);
        check("summary.has_breakdown", Array.isArray(s.breakdown), `is array: ${Array.isArray(s.breakdown)}`);

        const ss = s.summary;
        if (ss) {
          check("summary.total_employees_is_number", typeof ss.total_employees === "number", ss.total_employees);
          check("summary.total_gross_is_number", typeof ss.total_gross === "number", ss.total_gross);
          check("summary.total_deductions_is_number", typeof ss.total_deductions === "number", ss.total_deductions);
          check("summary.total_net_is_number", typeof ss.total_net === "number", ss.total_net);

          // Financial math: gross - deductions should equal net (within rounding)
          if (ss.total_gross > 0) {
            const expectedNet = ss.total_gross - ss.total_deductions;
            const diff = Math.abs(expectedNet - ss.total_net);
            check("summary.financial_math_gross_minus_deductions_equals_net",
              diff < 1, // Allow 1 peso rounding
              `gross(${ss.total_gross}) - deductions(${ss.total_deductions}) = ${expectedNet}, actual net=${ss.total_net}, diff=${diff}`);
          } else {
            check("summary.no_payroll_data_expected_zeros",
              ss.total_gross === 0 && ss.total_net === 0,
              `BEI has no payroll: gross=${ss.total_gross}, net=${ss.total_net}`);
          }

          // Check no negative values in financials
          check("summary.no_negative_gross", ss.total_gross >= 0, ss.total_gross);
          check("summary.no_negative_net", ss.total_net >= 0, ss.total_net);
          check("summary.no_negative_employees", ss.total_employees >= 0, ss.total_employees);
        }

        // Validate breakdown department totals
        if (s.breakdown && s.breakdown.length > 0) {
          for (const dept of s.breakdown) {
            check(`breakdown.${dept.department}.fields_present`,
              dept.employee_count !== undefined && dept.gross_pay !== undefined && dept.net_pay !== undefined,
              { employee_count: dept.employee_count, gross_pay: dept.gross_pay, deductions: dept.deductions, net_pay: dept.net_pay });

            // Dept math: gross - deductions = net
            if (dept.gross_pay > 0) {
              const deptExpected = dept.gross_pay - dept.deductions;
              const deptDiff = Math.abs(deptExpected - dept.net_pay);
              check(`breakdown.${dept.department}.financial_math`,
                deptDiff < 1,
                `gross(${dept.gross_pay}) - ded(${dept.deductions}) = ${deptExpected}, net=${dept.net_pay}`);
            }
          }

          // Cross-check: sum of dept breakdowns should equal summary totals
          const deptTotalGross = s.breakdown.reduce((a, d) => a + (d.gross_pay || 0), 0);
          const deptTotalNet = s.breakdown.reduce((a, d) => a + (d.net_pay || 0), 0);
          const deptTotalEmps = s.breakdown.reduce((a, d) => a + (d.employee_count || 0), 0);

          if (ss) {
            check("breakdown.sum_gross_matches_summary",
              Math.abs(deptTotalGross - ss.total_gross) < 1,
              `dept_sum=${deptTotalGross} vs summary=${ss.total_gross}`);
            check("breakdown.sum_net_matches_summary",
              Math.abs(deptTotalNet - ss.total_net) < 1,
              `dept_sum=${deptTotalNet} vs summary=${ss.total_net}`);
            check("breakdown.sum_employees_matches_summary",
              deptTotalEmps === ss.total_employees,
              `dept_sum=${deptTotalEmps} vs summary=${ss.total_employees}`);
          }
        }
      }

      // Write raw API response for audit
      writeFileSync(join(DIR, "api_dashboard_raw.json"), JSON.stringify(d, null, 2));
    } else {
      check("dashboard.api_called", false, "get_payroll_dashboard not intercepted");
    }

    // ── 2. Salary Slip List API ──
    console.log("\n=== get_salary_slip_list ===");
    await page.goto(`${BASE}/dashboard/hr/payroll/review-output`, { waitUntil: "networkidle", timeout: 25000 });
    await page.waitForTimeout(3000);

    const slipList = apiResponses["get_salary_slip_list"];
    if (slipList) {
      console.log(`  Status: ${slipList.status}`);
      const sl = slipList.data;

      check("salary_slips.has_data_array", Array.isArray(sl?.data), `is array: ${Array.isArray(sl?.data)}`);
      check("salary_slips.has_total", typeof sl?.total === "number", sl?.total);
      check("salary_slips.has_page", typeof sl?.page === "number", sl?.page);
      check("salary_slips.has_page_size", typeof sl?.page_size === "number", sl?.page_size);

      // Validate each slip's financial data
      if (sl?.data?.length > 0) {
        for (const slip of sl.data.slice(0, 5)) {
          check(`slip.${slip.employee}.gross_is_number`, typeof slip.gross_pay === "number", slip.gross_pay);
          check(`slip.${slip.employee}.net_is_number`, typeof slip.net_pay === "number", slip.net_pay);
          check(`slip.${slip.employee}.deduction_is_number`, typeof slip.total_deduction === "number", slip.total_deduction);

          // Math: gross - deduction = net
          const diff = Math.abs((slip.gross_pay - slip.total_deduction) - slip.net_pay);
          check(`slip.${slip.employee}.financial_math`, diff < 1,
            `gross(${slip.gross_pay}) - ded(${slip.total_deduction}) = ${slip.gross_pay - slip.total_deduction}, net=${slip.net_pay}`);
        }
      } else {
        check("salary_slips.empty_expected", sl?.total === 0, `BEI has 0 payroll entries, total=${sl?.total}`);
      }

      writeFileSync(join(DIR, "api_salary_slips_raw.json"), JSON.stringify(sl, null, 2));
    } else {
      check("salary_slips.api_called", false, "get_salary_slip_list not intercepted");
    }

    // ── 3. Comparison API ──
    console.log("\n=== get_payroll_comparison ===");
    await page.goto(`${BASE}/dashboard/hr/payroll/history?view=comparison`, { waitUntil: "networkidle", timeout: 25000 });
    await page.waitForTimeout(3000);

    const comp = apiResponses["get_payroll_comparison"];
    if (comp) {
      console.log(`  Status: ${comp.status}`);
      const c = comp.data;

      check("comparison.has_mode", c?.mode !== undefined, c?.mode);
      check("comparison.has_comparison_array", Array.isArray(c?.comparison), `is array, len=${c?.comparison?.length}`);
      check("comparison.has_summary", c?.summary !== undefined, typeof c?.summary);

      if (c?.summary) {
        check("comparison.summary.frappe_count_is_number", typeof c.summary.frappe_count === "number", c.summary.frappe_count);
        check("comparison.summary.variance_is_number", typeof c.summary.variance_net_total === "number", c.summary.variance_net_total);
      }

      // If comparison rows exist, validate each
      if (c?.comparison?.length > 0) {
        for (const row of c.comparison.slice(0, 5)) {
          if (row.frappe_net !== null && row.apex_net !== null && row.variance_net !== null) {
            const expectedVariance = row.frappe_net - row.apex_net;
            const vDiff = Math.abs(expectedVariance - row.variance_net);
            check(`comparison.${row.employee}.variance_math`, vDiff < 1,
              `frappe(${row.frappe_net}) - apex(${row.apex_net}) = ${expectedVariance}, variance=${row.variance_net}`);
          }
        }
      }

      writeFileSync(join(DIR, "api_comparison_raw.json"), JSON.stringify(c, null, 2));
    } else {
      check("comparison.api_called", false, "get_payroll_comparison not intercepted — may not have loaded");
    }

    // ── 4. Attendance Summary API ──
    console.log("\n=== get_attendance_summary ===");
    await page.goto(`${BASE}/dashboard/hr/payroll/current-cutoff`, { waitUntil: "networkidle", timeout: 25000 });
    await page.waitForTimeout(3000);

    const att = apiResponses["get_attendance_summary"];
    if (att) {
      console.log(`  Status: ${att.status}`);
      const rows = att.data;

      check("attendance.is_array", Array.isArray(rows), `is array, len=${rows?.length}`);

      if (Array.isArray(rows) && rows.length > 0) {
        for (const row of rows.slice(0, 3)) {
          check(`attendance.${row.employee}.has_present_days`, typeof row.present_days === "number", row.present_days);
          check(`attendance.${row.employee}.has_ot_hours`, typeof row.ot_hours === "number", row.ot_hours);
          check(`attendance.${row.employee}.no_negative_present`, row.present_days >= 0, row.present_days);
          check(`attendance.${row.employee}.no_negative_absent`, row.absent_days >= 0, row.absent_days);
        }
      }

      writeFileSync(join(DIR, "api_attendance_raw.json"), JSON.stringify(rows, null, 2));
    } else {
      check("attendance.api_called", false, "get_attendance_summary not intercepted");
    }

    // ── 5. Processing Status API ──
    console.log("\n=== get_payroll_processing_status ===");
    const ps = apiResponses["get_payroll_processing_status"];
    if (ps) {
      console.log(`  Status: ${ps.status}`);
      writeFileSync(join(DIR, "api_processing_status_raw.json"), JSON.stringify(ps.data, null, 2));
    }

    // ── 6. Summary API (standalone) ──
    const summ = apiResponses["get_payroll_summary"];
    if (summ) {
      writeFileSync(join(DIR, "api_summary_raw.json"), JSON.stringify(summ.data, null, 2));
    }

  } finally {
    await ctx.close();
    await browser.close();
  }

  // Write data validation results
  writeFileSync(join(DIR, "data_validation.json"), JSON.stringify(dataChecks, null, 2));

  // Summary
  const passed = dataChecks.filter(c => c.passed).length;
  const failed = dataChecks.filter(c => !c.passed).length;
  console.log(`\n${"=".repeat(60)}`);
  console.log(`DATA VALIDATION: ${passed}/${dataChecks.length} PASS, ${failed} FAIL`);
  if (failed > 0) {
    console.log("\nFailed checks:");
    for (const c of dataChecks.filter(c => !c.passed)) {
      console.log(`  [FAIL] ${c.check}: ${typeof c.details === "object" ? JSON.stringify(c.details) : c.details}`);
    }
  }
  console.log("=".repeat(60));

  process.exit(failed > 0 ? 1 : 0);
}

run().catch(e => { console.error("FATAL:", e); process.exit(2); });
