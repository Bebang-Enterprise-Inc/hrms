/**
 * S167 shared helpers — login, evidence recorders, screenshots.
 */
const { chromium } = require("F:/Dropbox/Projects/BEI-Tasks-S060-sales-dashboard-ui/node_modules/playwright");
const fs = require("fs");
const path = require("path");

const BASE = "https://my.bebang.ph";
const OUT = "F:/Dropbox/Projects/BEI-ERP/output/l3/s167";
const SHOTS = path.join(OUT, "screenshots");
fs.mkdirSync(SHOTS, { recursive: true });

const RECEIPT = "F:/Dropbox/Projects/BEI-ERP/output/l3/s167/test_receipt.png";
// Copy receipt to a stable path inside the repo (git-friendly)
if (!fs.existsSync(RECEIPT)) {
  try { fs.copyFileSync("/tmp/s167_test_receipt.png", RECEIPT); } catch {}
}

const ACCOUNTS = {
  sam:       { email: "sam@bebang.ph",             pw: "2289454" },
  staff:     { email: "test.staff@bebang.ph",      pw: "BeiTest2026!" },
  supv:      { email: "test.supervisor@bebang.ph", pw: "BeiTest2026!" },
  hr:        { email: "test.hr@bebang.ph",         pw: "BeiTest2026!" },
  warehouse: { email: "test.warehouse@bebang.ph",  pw: "BeiTest2026!" },
  commi:     { email: "test.commissary@bebang.ph", pw: "BeiTest2026!" },
  finance:   { email: "test.finance@bebang.ph",    pw: "BeiTest2026!" },
};

// Evidence collectors (append to files incrementally)
function loadJson(f) { try { return JSON.parse(fs.readFileSync(f,"utf8")); } catch { return []; } }
function saveJson(f, d) { fs.writeFileSync(f, JSON.stringify(d, null, 2)); }

const F_FORMS = path.join(OUT, "form_submissions.json");
const F_API   = path.join(OUT, "api_mutations.json");
const F_STATE = path.join(OUT, "state_verification.json");
const F_DEFECTS = path.join(OUT, "DEFECT_REGISTER.md");

function recordForm(entry) {
  const arr = loadJson(F_FORMS);
  arr.push({ ts: new Date().toISOString(), ...entry });
  saveJson(F_FORMS, arr);
}
function recordState(entry) {
  const arr = loadJson(F_STATE);
  arr.push({ ts: new Date().toISOString(), ...entry });
  saveJson(F_STATE, arr);
}
function recordDefect(scenario, err, hypothesis = "") {
  const line = `\n## ${scenario}\n- **time:** ${new Date().toISOString()}\n- **error:** ${err}\n- **hypothesis:** ${hypothesis}\n`;
  fs.appendFileSync(F_DEFECTS, line);
}

function attachNetwork(page, scenarioRef) {
  const apiFile = F_API;
  page.on("request", (req) => {
    const m = req.method();
    if (["POST","PUT","PATCH","DELETE"].includes(m)) {
      const u = req.url();
      if (!u.includes("/api/")) return;
      const arr = loadJson(apiFile);
      arr.push({
        phase: "request",
        scenario: scenarioRef.current,
        method: m,
        url: u,
        payload: (req.postData() || "").slice(0, 4000),
        ts: new Date().toISOString(),
      });
      saveJson(apiFile, arr);
    }
  });
  page.on("response", async (resp) => {
    const req = resp.request();
    const m = req.method();
    if (!["POST","PUT","PATCH","DELETE"].includes(m)) return;
    if (!req.url().includes("/api/")) return;
    let body = null;
    try {
      const ct = (resp.headers()["content-type"] || "").toLowerCase();
      if (ct.includes("json") || ct.includes("text")) body = (await resp.text()).slice(0, 4000);
    } catch {}
    const arr = loadJson(apiFile);
    arr.push({
      phase: "response",
      scenario: scenarioRef.current,
      method: m,
      url: req.url(),
      status: resp.status(),
      response_body: body,
      ts: new Date().toISOString(),
    });
    saveJson(apiFile, arr);
  });
  page.on("pageerror", (err) => console.log("PAGE ERROR:", err.message.slice(0, 200)));
}

async function login(page, who) {
  const a = ACCOUNTS[who];
  if (!a) throw new Error(`unknown account ${who}`);
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForTimeout(1500);
  if (page.url().includes("/dashboard")) return;
  // Some sessions may show a "continue" screen — but we use a fresh context
  await page.fill('input[type="email"], input[name="email"]', a.email);
  await page.fill('input[type="password"], input[name="password"]', a.pw);
  await page.click('button[type="submit"]');
  try { await page.waitForURL("**/dashboard**", { timeout: 30000 }); } catch {
    await page.waitForTimeout(3000);
  }
  if (!page.url().includes("/dashboard")) {
    throw new Error(`login failed for ${who} — still at ${page.url()}`);
  }
}

async function shot(page, name) {
  const p = path.join(SHOTS, `${name}.png`);
  try { await page.screenshot({ path: p, fullPage: true }); } catch {}
  return p;
}

async function newBrowser() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  return { browser, ctx, page };
}

module.exports = {
  BASE, OUT, SHOTS, RECEIPT, ACCOUNTS,
  login, shot, attachNetwork,
  recordForm, recordState, recordDefect,
  newBrowser,
};
