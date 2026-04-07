/**
 * S166 Wave 0 — Combobox Spike
 *
 * Goal: find a reliable interaction sequence that opens the Gender shadcn
 * combobox inside the Add New Employee dialog and selects "Male", then
 * closes the dialog WITHOUT submitting. Verifies same pattern on Branch.
 *
 * DO NOT submit the form. DO NOT create any employee.
 */
import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const FRAPPE = "https://hq.bebang.ph";
const BASE = "https://my.bebang.ph";
const EMAIL = "test.hr@bebang.ph";
const PASSWORD = "BeiTest2026!";

const OUT_DIR = "data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution/wave0";
const SHOT_OPEN = path.join(OUT_DIR, "spike_dialog_opened.png");
const SHOT_SELECTED = path.join(OUT_DIR, "spike_gender_selected.png");
const SHOT_BRANCH = path.join(OUT_DIR, "spike_branch_selected.png");
const REPORT = path.join(OUT_DIR, "COMBOBOX_WORKAROUND.md");

fs.mkdirSync(OUT_DIR, { recursive: true });

const attempts = []; // {method, label, popoverOpened, optionClicked, triggerValue, error}

function log(...a) { console.log(...a); }

async function loginMyBebang(page) {
  await page.goto(`${FRAPPE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.fill('input[name="usr"]', EMAIL);
  await page.fill('input[name="pwd"]', PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(800);
  if (page.url().includes("/login")) {
    await page.fill('input[name="email"]', EMAIL).catch(() => {});
    await page.fill('input[name="password"]', PASSWORD).catch(() => {});
    await page.click('button[type="submit"]').catch(() => {});
    await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(1500);
  }
  log("logged in:", page.url());
}

async function openDialog(page) {
  await page.goto(`${BASE}/dashboard/hr/employee-master`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1500);
  let btn = page.getByRole("button", { name: /add new employee/i }).first();
  if (await btn.count() === 0) {
    // enumerate
    const buttons = await page.locator("button").all();
    for (const b of buttons) {
      const t = (await b.innerText().catch(() => "")).toLowerCase();
      if (t.includes("add") && t.includes("employee")) { btn = b; break; }
    }
  }
  await btn.waitFor({ state: "visible", timeout: 15000 });
  await btn.click();
  await page.waitForTimeout(1500);
  // Wait for dialog
  await page.locator('[role="dialog"]').first().waitFor({ state: "visible", timeout: 10000 });
  await page.waitForTimeout(500);
}

/**
 * Enumerate all role=combobox in the dialog and locate by adjacent label text.
 * Returns the Playwright Locator for the trigger matching `labelRegex`.
 */
async function findComboboxTrigger(page, labelRegex) {
  const dialog = page.locator('[role="dialog"]').first();
  const combos = await dialog.locator('button[role="combobox"]').all();
  log(`  found ${combos.length} combobox buttons in dialog`);
  for (let i = 0; i < combos.length; i++) {
    const c = combos[i];
    // Look for label via aria-labelledby, inner text, or preceding label
    const info = await c.evaluate((el, rxSrc) => {
      const rx = new RegExp(rxSrc, "i");
      const out = { idx: -1, ariaLabel: el.getAttribute("aria-label"), text: el.innerText, labelledBy: el.getAttribute("aria-labelledby") };
      // check aria-labelledby
      if (out.labelledBy) {
        const lbl = document.getElementById(out.labelledBy);
        out.labelledByText = lbl?.innerText || "";
      }
      // walk up to find a label in the same form-item container
      let p = el.parentElement;
      let nearest = "";
      for (let k = 0; k < 5 && p; k++) {
        const lbl = p.querySelector("label");
        if (lbl) { nearest = lbl.innerText; break; }
        p = p.parentElement;
      }
      out.nearestLabel = nearest;
      out.match = rx.test(out.ariaLabel || "") || rx.test(out.labelledByText || "") || rx.test(nearest || "") || rx.test(out.text || "");
      return out;
    }, labelRegex.source);
    log(`    combo[${i}] label="${info.nearestLabel}" aria="${info.ariaLabel}" text="${info.text}" match=${info.match}`);
    if (info.match) return { locator: c, index: i, info };
  }
  return null;
}

async function getTriggerDisplayText(trigger) {
  return (await trigger.innerText().catch(() => "")).trim();
}

async function popoverOpen(page) {
  // Radix popover content with role=listbox or data-state=open
  const ct = await page.locator('[role="listbox"], [cmdk-list], [data-radix-popper-content-wrapper]').count();
  return ct > 0;
}

async function clickOption(page, optionText) {
  const opt = page.locator('[role="option"]').filter({ hasText: new RegExp(`^\\s*${optionText}\\s*$`, "i") }).first();
  if (await opt.count() === 0) {
    // relax
    const opt2 = page.locator('[role="option"]').filter({ hasText: new RegExp(optionText, "i") }).first();
    if (await opt2.count() === 0) return false;
    await opt2.click({ timeout: 3000 }).catch(() => {});
    return true;
  }
  await opt.click({ timeout: 3000 }).catch(() => {});
  return true;
}

async function closePopoverIfOpen(page) {
  if (await popoverOpen(page)) {
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  }
}

/**
 * Run all workaround attempts on a given combobox until one succeeds.
 * Returns the letter (a..h) of the first successful method, or null.
 */
async function tryWorkarounds(page, labelRegex, optionText, label) {
  const methods = [
    {
      letter: "a",
      name: "trigger.click({force:true}) + option click",
      fn: async (trig) => {
        await trig.click({ force: true });
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        const ok = await clickOption(page, optionText);
        await page.waitForTimeout(300);
        return { popover: true, selected: ok };
      },
    },
    {
      letter: "b",
      name: "trigger.focus + Enter + ArrowDown + Enter",
      fn: async (trig) => {
        await trig.focus();
        await page.keyboard.press("Enter");
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        await page.keyboard.press("ArrowDown");
        await page.keyboard.press("Enter");
        await page.waitForTimeout(300);
        return { popover: true, selected: true };
      },
    },
    {
      letter: "c",
      name: "trigger.evaluate(el=>el.click()) + option click",
      fn: async (trig) => {
        await trig.evaluate((el) => el.click());
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        const ok = await clickOption(page, optionText);
        await page.waitForTimeout(300);
        return { popover: true, selected: ok };
      },
    },
    {
      letter: "d",
      name: "keyboard Tab until focused + Space + ArrowDown + Enter",
      fn: async (trig) => {
        // focus directly — simulate Tab-reach by using trig.focus()
        await trig.focus();
        await page.keyboard.press(" ");
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        await page.keyboard.press("ArrowDown");
        await page.keyboard.press("Enter");
        await page.waitForTimeout(300);
        return { popover: true, selected: true };
      },
    },
    {
      letter: "e",
      name: "dispatchEvent pointerdown+click",
      fn: async (trig) => {
        await trig.evaluate((el) => {
          el.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
          el.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
          el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        });
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        const ok = await clickOption(page, optionText);
        await page.waitForTimeout(300);
        return { popover: true, selected: ok };
      },
    },
    {
      letter: "f",
      name: "locator.press('Enter')",
      fn: async (trig) => {
        await trig.press("Enter");
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        const ok = await clickOption(page, optionText);
        await page.waitForTimeout(300);
        return { popover: true, selected: ok };
      },
    },
    {
      letter: "g",
      name: "mouse.click at boundingBox center",
      fn: async (trig) => {
        const box = await trig.boundingBox();
        if (!box) return { popover: false, selected: false };
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        const ok = await clickOption(page, optionText);
        await page.waitForTimeout(300);
        return { popover: true, selected: ok };
      },
    },
    {
      letter: "h",
      name: "force click + position corner",
      fn: async (trig) => {
        await trig.click({ force: true, position: { x: 5, y: 5 } });
        await page.waitForTimeout(400);
        if (!(await popoverOpen(page))) return { popover: false, selected: false };
        const ok = await clickOption(page, optionText);
        await page.waitForTimeout(300);
        return { popover: true, selected: ok };
      },
    },
  ];

  for (const m of methods) {
    log(`\n  [${label}] attempt (${m.letter}) ${m.name}`);
    let popover = false, selected = false, triggerValue = "", error = null;
    try {
      const found = await findComboboxTrigger(page, labelRegex);
      if (!found) {
        attempts.push({ label, method: m.letter, name: m.name, popoverOpened: false, optionClicked: false, triggerValue: "", error: "combobox not found" });
        log(`    combobox not found for ${labelRegex}`);
        continue;
      }
      const trig = found.locator;
      const res = await m.fn(trig);
      popover = res.popover;
      selected = res.selected;
      triggerValue = await getTriggerDisplayText(trig);
      log(`    popoverOpened=${popover} optionClicked=${selected} triggerValue="${triggerValue}"`);
    } catch (e) {
      error = String(e).substring(0, 200);
      log(`    ERROR: ${error}`);
    }
    attempts.push({ label, method: m.letter, name: m.name, popoverOpened: popover, optionClicked: selected, triggerValue, error });

    // Success = popover opened, option clicked, and trigger value now reflects the option
    const success = popover && selected && new RegExp(optionText, "i").test(triggerValue);
    if (success) {
      log(`  SUCCESS on method (${m.letter}) for ${label}`);
      return m.letter;
    }

    // cleanup: close any open popover before next attempt
    await closePopoverIfOpen(page);
    await page.waitForTimeout(200);
  }
  return null;
}

async function run() {
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  let genderWinner = null;
  let branchWinner = null;
  let fatal = null;

  try {
    await loginMyBebang(page);
    await openDialog(page);
    await page.screenshot({ path: SHOT_OPEN, fullPage: false });
    log(`saved ${SHOT_OPEN}`);

    // Dump all comboboxes in the dialog for diagnostics
    const dialog = page.locator('[role="dialog"]').first();
    const combos = await dialog.locator('button[role="combobox"]').all();
    log(`\n=== dialog has ${combos.length} combobox triggers ===`);
    for (let i = 0; i < combos.length; i++) {
      const info = await combos[i].evaluate((el) => {
        let p = el.parentElement, lbl = "";
        for (let k = 0; k < 5 && p; k++) {
          const l = p.querySelector("label");
          if (l) { lbl = l.innerText; break; }
          p = p.parentElement;
        }
        return { text: el.innerText, aria: el.getAttribute("aria-label"), label: lbl };
      });
      log(`  [${i}] label="${info.label}" aria="${info.aria}" text="${info.text}"`);
    }

    // ── GENDER ──
    log("\n=== GENDER combobox ===");
    genderWinner = await tryWorkarounds(page, /gender/i, "Male", "Gender");
    if (genderWinner) {
      await page.screenshot({ path: SHOT_SELECTED, fullPage: false });
      log(`saved ${SHOT_SELECTED}`);
    }

    // ── BRANCH ──
    log("\n=== BRANCH combobox ===");
    // Use same winning method first if gender worked; else run full sweep
    if (genderWinner) {
      // Just verify the same method works on Branch
      branchWinner = await tryWorkarounds(page, /branch|store|location/i, "ARANETA GATEWAY", "Branch");
    } else {
      branchWinner = await tryWorkarounds(page, /branch|store|location/i, "ARANETA GATEWAY", "Branch");
    }
    if (branchWinner) {
      await page.screenshot({ path: SHOT_BRANCH, fullPage: false });
    }

    // Close dialog with Escape, verify closed
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    const stillOpen = await page.locator('[role="dialog"]').count();
    log(`\ndialog still open after Escape: ${stillOpen > 0}`);
  } catch (e) {
    fatal = String(e);
    log("FATAL:", e);
  } finally {
    await ctx.close();
    await browser.close();
  }

  // Write report
  const lines = [];
  lines.push("# S166 Wave 0 — Combobox Workaround Spike Report");
  lines.push("");
  lines.push(`**Run:** ${new Date().toISOString()}`);
  lines.push(`**Target:** Add New Employee dialog on https://my.bebang.ph/dashboard/hr/employee-master`);
  lines.push(`**Actor:** ${EMAIL}`);
  lines.push("");
  lines.push("## Result");
  lines.push("");
  lines.push(`- **Gender combobox cracked:** ${genderWinner ? `YES (method ${genderWinner})` : "NO"}`);
  lines.push(`- **Branch combobox cracked:** ${branchWinner ? `YES (method ${branchWinner})` : "NO"}`);
  lines.push(`- **Generalizes:** ${genderWinner && branchWinner && genderWinner === branchWinner ? "YES — same method works on both" : (genderWinner && branchWinner ? `PARTIAL — gender=${genderWinner}, branch=${branchWinner}` : "NO")}`);
  if (fatal) lines.push(`- **Fatal:** ${fatal}`);
  lines.push("");
  lines.push("## Attempts");
  lines.push("");
  lines.push("| Field | Method | Name | Popover | Option | Trigger Value | Error |");
  lines.push("|-------|--------|------|---------|--------|---------------|-------|");
  for (const a of attempts) {
    lines.push(`| ${a.label} | ${a.method} | ${a.name} | ${a.popoverOpened ? "YES" : "no"} | ${a.optionClicked ? "YES" : "no"} | \`${(a.triggerValue || "").replace(/\|/g, "/")}\` | ${a.error || ""} |`);
  }
  lines.push("");
  if (genderWinner) {
    const winner = {
      a: `await trigger.click({ force: true });\nawait page.waitForTimeout(400);\nawait page.locator('[role="option"]').filter({ hasText: /^\\s*Male\\s*$/i }).first().click();`,
      b: `await trigger.focus();\nawait page.keyboard.press('Enter');\nawait page.waitForTimeout(400);\nawait page.keyboard.press('ArrowDown');\nawait page.keyboard.press('Enter');`,
      c: `await trigger.evaluate((el) => el.click());\nawait page.waitForTimeout(400);\nawait page.locator('[role="option"]').filter({ hasText: /^\\s*Male\\s*$/i }).first().click();`,
      d: `await trigger.focus();\nawait page.keyboard.press(' ');\nawait page.waitForTimeout(400);\nawait page.keyboard.press('ArrowDown');\nawait page.keyboard.press('Enter');`,
      e: `await trigger.evaluate((el) => {\n  el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));\n  el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));\n  el.dispatchEvent(new MouseEvent('click', { bubbles: true }));\n});\nawait page.waitForTimeout(400);\nawait page.locator('[role="option"]').filter({ hasText: /^\\s*Male\\s*$/i }).first().click();`,
      f: `await trigger.press('Enter');\nawait page.waitForTimeout(400);\nawait page.locator('[role="option"]').filter({ hasText: /^\\s*Male\\s*$/i }).first().click();`,
      g: `const box = await trigger.boundingBox();\nawait page.mouse.click(box.x + box.width/2, box.y + box.height/2);\nawait page.waitForTimeout(400);\nawait page.locator('[role="option"]').filter({ hasText: /^\\s*Male\\s*$/i }).first().click();`,
      h: `await trigger.click({ force: true, position: { x: 5, y: 5 } });\nawait page.waitForTimeout(400);\nawait page.locator('[role="option"]').filter({ hasText: /^\\s*Male\\s*$/i }).first().click();`,
    };
    lines.push("## Winning Snippet (Gender)");
    lines.push("");
    lines.push("```javascript");
    lines.push(winner[genderWinner] || "(see attempt log)");
    lines.push("```");
    lines.push("");
  } else {
    lines.push("## Diagnosis");
    lines.push("");
    lines.push("No workaround cracked the Gender combobox. All 8 methods (a-h) failed.");
    lines.push("Possible causes:");
    lines.push("- Dialog overlay is intercepting pointer events even with `force: true`");
    lines.push("- Combobox trigger is not a `button[role=\"combobox\"]` — may be a custom element");
    lines.push("- Popover renders outside the dialog and `[role=\"listbox\"]` detection failed");
    lines.push("- Frontend bug in bei-tasks — trigger is disabled or not wired");
    lines.push("");
    lines.push("**Recommendation:** Pause Wave 0 and file a frontend issue against `bei-tasks`. Re-inspect the AddNewEmployeeDialog component and confirm the Radix Popover + Command wiring.");
    lines.push("");
  }
  lines.push("## Screenshots");
  lines.push("");
  lines.push(`- Dialog opened: \`${SHOT_OPEN}\``);
  if (genderWinner) lines.push(`- Gender selected: \`${SHOT_SELECTED}\``);
  if (branchWinner) lines.push(`- Branch selected: \`${SHOT_BRANCH}\``);
  lines.push("");

  fs.writeFileSync(REPORT, lines.join("\n"));
  log(`\nwrote ${REPORT}`);
  log(`gender winner: ${genderWinner || "NONE"}`);
  log(`branch winner: ${branchWinner || "NONE"}`);
}

run().catch((e) => { console.error(e); process.exit(1); });
