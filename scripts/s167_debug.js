/**
 * S167 Debug — deep inspect create fund dialog + supervisor PCF page text.
 */
const { BASE, login, newBrowser } = require("./s167_lib");
const fs = require("fs");

(async () => {
  // 1. Dialog deep inspect as sam
  {
    const { browser, page } = await newBrowser();
    await login(page, "sam");
    await page.goto(`${BASE}/dashboard/accounting/pcf/admin`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: /create department fund/i }).first().click();
    await page.waitForTimeout(1500);
    // Dump ALL form controls inside the dialog
    const dlg = page.getByRole("dialog").first();
    const info = await dlg.evaluate((node) => {
      const pick = (sel) => Array.from(node.querySelectorAll(sel)).map(el => ({
        tag: el.tagName,
        type: el.getAttribute("type"),
        name: el.getAttribute("name"),
        id: el.id,
        role: el.getAttribute("role"),
        ariaLabel: el.getAttribute("aria-label"),
        ariaExpanded: el.getAttribute("aria-expanded"),
        dataState: el.getAttribute("data-state"),
        text: (el.innerText||"").slice(0,80),
        placeholder: el.getAttribute("placeholder"),
      }));
      return {
        buttons: pick("button"),
        inputs: pick("input"),
        selects: pick("select"),
        comboboxes: pick("[role='combobox']"),
        labels: Array.from(node.querySelectorAll("label")).map(l=>({for: l.htmlFor, text: (l.innerText||"").trim()})),
        all_ids: Array.from(node.querySelectorAll("[id]")).map(e=>({tag:e.tagName, id:e.id, text:(e.innerText||"").slice(0,40)})).slice(0,30),
      };
    });
    fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/debug_dialog.json", JSON.stringify(info, null, 2));
    console.log("Dialog labels:");
    for (const l of info.labels) console.log(`  for=${l.for} text='${l.text}'`);
    console.log("Dialog buttons:");
    for (const b of info.buttons) console.log(`  text='${b.text}' aria=${b.ariaLabel} role=${b.role} id=${b.id} type=${b.type}`);
    console.log("Dialog inputs:");
    for (const i of info.inputs) console.log(`  type=${i.type} name=${i.name} id=${i.id} aria=${i.ariaLabel} ph=${i.placeholder}`);
    console.log("Dialog comboboxes:", info.comboboxes);
    console.log("Dialog selects:", info.selects.length);

    // Now click the combobox and see what appears globally
    const cb = dlg.getByRole("combobox").first();
    await cb.click();
    await page.waitForTimeout(1200);
    // Look at page-wide option elements after click
    const opts = await page.evaluate(() => {
      const o = Array.from(document.querySelectorAll("[role='option'], [role='listbox'] *, [data-radix-select-item]"));
      return o.slice(0,40).map(e=>({tag:e.tagName, role:e.getAttribute("role"), text:(e.innerText||"").slice(0,60), dataValue:e.getAttribute("data-value")}));
    });
    console.log("Options after combobox click:", opts.length);
    opts.forEach(o=>console.log(" ", o));
    await page.screenshot({ path: "F:/Dropbox/Projects/BEI-ERP/output/l3/s167/screenshots/debug_dialog_combobox_open.png", fullPage: true });

    await browser.close();
  }

  // 2. Supervisor PCF page text
  {
    const { browser, page } = await newBrowser();
    await login(page, "supv");
    await page.goto(`${BASE}/dashboard/store-ops/pcf`, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForTimeout(3000);
    const text = await page.evaluate(() => document.body.innerText);
    fs.writeFileSync("F:/Dropbox/Projects/BEI-ERP/output/l3/s167/debug_supv_pcf.txt", text);
    console.log("\n--- test.supervisor store-ops/pcf (first 1500 chars) ---");
    console.log(text.slice(0, 1500));
    await page.screenshot({ path: "F:/Dropbox/Projects/BEI-ERP/output/l3/s167/screenshots/debug_supv_pcf.png", fullPage: true });
    await browser.close();
  }
})().catch(e => { console.error("FATAL", e); process.exit(1); });
