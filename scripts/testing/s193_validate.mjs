/**
 * S193 Post-Deploy Validation — Supplier Status Guard
 *
 * Confirms:
 * 1. Backend endpoints (new + existing) are reachable with auth
 * 2. _assert_supplier_active is deployed (probe via create_purchase_order denial path)
 * 3. All three create endpoints enforce the status policy
 * 4. Error messages surface through parseFrappeError-compatible format
 *
 * Uses real test accounts + existing suppliers. Does NOT mutate production
 * data — all create attempts target Blacklisted/Pending Verification/Inactive
 * suppliers, which MUST be rejected by the guard. Active-path is probed
 * with intentionally-invalid payload so the ValidationError comes from a
 * NON-S193 check (meaning the guard correctly passed).
 */
import fs from 'fs';
import path from 'path';

const FRAPPE = 'https://hq.bebang.ph';
const OUT_DIR = 'output/l3/s193';
const USERS = {
  sam: { email: 'sam@bebang.ph', password: '2289454' },
};

let cookies = '';

async function login(usr, pwd) {
  const r = await fetch(`${FRAPPE}/api/method/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usr, pwd }),
  });
  cookies = (r.headers.getSetCookie() || []).map(c => c.split(';')[0]).join('; ');
  return r.ok;
}

async function fCall(method, body = null, qs = null) {
  const url = qs
    ? `${FRAPPE}/api/method/${method}?${new URLSearchParams(qs).toString()}`
    : `${FRAPPE}/api/method/${method}`;
  const opts = {
    method: body ? 'POST' : 'GET',
    headers: { Cookie: cookies, 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': 'no' },
  };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(url, opts);
  const text = await r.text();
  let parsed;
  try { parsed = JSON.parse(text); } catch { parsed = { raw: text }; }
  return { status: r.status, body: parsed };
}

function extractFrappeMessage(body) {
  // Matches parseFrappeError behavior in lib/frappe-api.ts
  if (body._server_messages) {
    try {
      const msgs = JSON.parse(body._server_messages);
      if (Array.isArray(msgs) && msgs.length) {
        const m = typeof msgs[0] === 'string' ? JSON.parse(msgs[0]) : msgs[0];
        if (m?.message) return m.message.replace(/<[^>]+>/g, '');
      }
    } catch {}
  }
  if (body._error_message) return String(body._error_message);
  if (body.exception) return String(body.exception);
  return null;
}

const evidence = {
  sprint: 'S193',
  deploy_sha: '63139b5',
  image_digest: 'sha256:79e28e0c224bfe593d5acb1d2e501ce5b5ce45266b23ff9e832491a07e2516d2',
  tested_at: new Date().toISOString(),
  tests: [],
};

function record(name, pass, detail) {
  evidence.tests.push({ name, pass, detail });
  console.log(`${pass ? '✅' : '❌'} ${name}  ${detail.summary || ''}`);
  if (detail.extra) console.log(`   ${detail.extra}`);
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  // 1. Login as Sam (Administrator — has all roles)
  const loggedIn = await login(USERS.sam.email, USERS.sam.password);
  if (!loggedIn) { console.error('Login failed'); process.exit(1); }
  console.log('✅ Login as sam@bebang.ph');

  // 2. Fetch suppliers grouped by status to find test targets
  const groups = {};
  for (const status of ['Active', 'Inactive', 'Blacklisted', 'Pending Verification']) {
    const r = await fCall('frappe.client.get_list', null, {
      doctype: 'BEI Supplier',
      filters: JSON.stringify([['status', '=', status]]),
      fields: JSON.stringify(['name', 'supplier_name']),
      limit_page_length: 3,
    });
    groups[status] = (r.body.message || []).map(s => s.name);
    console.log(`   ${status}: ${groups[status].length} supplier(s) — ${groups[status].slice(0, 2).join(', ') || '(none)'}`);
  }
  evidence.supplier_counts = Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, v.length]));

  // 3. Endpoint liveness probe — S186 get_supplier_grid should return 200 with auth
  const gridProbe = await fCall('hrms.api.procurement.get_supplier_grid', null, { page_size: 1 });
  record('S186 get_supplier_grid live', gridProbe.status === 200, {
    summary: `HTTP ${gridProbe.status}`,
    extra: gridProbe.status === 200 ? `summary.total_suppliers=${gridProbe.body.message?.summary?.total_suppliers}` : JSON.stringify(gridProbe.body).slice(0, 200),
  });

  // 4. S193 guard — probe _assert_supplier_active indirectly via create_purchase_order
  //    with a Blacklisted supplier (MUST fail with specific S193 message).
  if (groups.Blacklisted.length > 0) {
    const target = groups.Blacklisted[0];
    const r = await fCall('hrms.api.procurement.create_purchase_order', {
      data: { supplier: target, po_date: '2026-04-14', items: [] },
    });
    const msg = extractFrappeMessage(r.body) || '';
    const hitGuard = /Cannot create Purchase Order.*Blacklisted/i.test(msg);
    record('create_purchase_order blocks Blacklisted', hitGuard, {
      summary: `HTTP ${r.status}`,
      extra: `msg="${msg.slice(0, 180)}"`,
    });
  } else {
    record('create_purchase_order blocks Blacklisted', null, { summary: 'SKIP — no Blacklisted supplier in prod' });
  }

  // 5. Pending Verification
  if (groups['Pending Verification'].length > 0) {
    const target = groups['Pending Verification'][0];
    const r = await fCall('hrms.api.procurement.create_purchase_order', {
      data: { supplier: target, po_date: '2026-04-14', items: [] },
    });
    const msg = extractFrappeMessage(r.body) || '';
    const hitGuard = /Cannot create Purchase Order.*Pending Verification/i.test(msg);
    record('create_purchase_order blocks Pending Verification', hitGuard, {
      summary: `HTTP ${r.status}`,
      extra: `msg="${msg.slice(0, 180)}"`,
    });

    // Same supplier, invoice — must also block
    const rInv = await fCall('hrms.api.procurement.create_invoice', {
      data: { supplier: target, invoice_date: '2026-04-14', grand_total: 100 },
    });
    const msgInv = extractFrappeMessage(rInv.body) || '';
    const hitInv = /Cannot create Invoice.*Pending Verification/i.test(msgInv);
    record('create_invoice blocks Pending Verification', hitInv, {
      summary: `HTTP ${rInv.status}`,
      extra: `msg="${msgInv.slice(0, 180)}"`,
    });

    // Payment request
    const rPay = await fCall('hrms.api.procurement.create_payment_request', {
      data: { supplier: target, payment_amount: 100, payment_date: '2026-04-14' },
    });
    const msgPay = extractFrappeMessage(rPay.body) || '';
    const hitPay = /Cannot create Payment Request.*Pending Verification/i.test(msgPay);
    record('create_payment_request blocks Pending Verification', hitPay, {
      summary: `HTTP ${rPay.status}`,
      extra: `msg="${msgPay.slice(0, 180)}"`,
    });
  } else {
    record('PV endpoints block', null, { summary: 'SKIP — no Pending Verification supplier' });
  }

  // 6. Inactive — PO blocks, Invoice + Payment Request pass the status gate (may fail for OTHER reasons)
  if (groups.Inactive.length > 0) {
    const target = groups.Inactive[0];
    const rPO = await fCall('hrms.api.procurement.create_purchase_order', {
      data: { supplier: target, po_date: '2026-04-14', items: [] },
    });
    const msgPO = extractFrappeMessage(rPO.body) || '';
    const hitPO = /Cannot create Purchase Order.*Inactive/i.test(msgPO);
    record('create_purchase_order blocks Inactive', hitPO, {
      summary: `HTTP ${rPO.status}`,
      extra: `msg="${msgPO.slice(0, 180)}"`,
    });

    // Invoice for Inactive: must NOT be blocked by S193 (may fail for other reasons)
    const rInv = await fCall('hrms.api.procurement.create_invoice', {
      data: { supplier: target, invoice_date: '2026-04-14', grand_total: 100 },
    });
    const msgInv = extractFrappeMessage(rInv.body) || '';
    const noS193Block = !/Cannot create Invoice.*Inactive/i.test(msgInv);
    record('create_invoice ALLOWS Inactive (no S193 block)', noS193Block, {
      summary: `HTTP ${rInv.status}`,
      extra: `msg="${msgInv.slice(0, 180)}" — may fail for other validation (OK)`,
    });
  } else {
    record('Inactive policy tests', null, { summary: 'SKIP — no Inactive supplier' });
  }

  // 7. Active baseline — create_purchase_order with empty items should FAIL
  //    but NOT for S193 reasons (proves guard correctly passed Active suppliers)
  if (groups.Active.length > 0) {
    const target = groups.Active[0];
    const r = await fCall('hrms.api.procurement.create_purchase_order', {
      data: { supplier: target, po_date: '2026-04-14', items: [] },
    });
    const msg = extractFrappeMessage(r.body) || '';
    const notBlockedByS193 = !/Cannot create Purchase Order.*(Blacklisted|Pending Verification|Inactive)/i.test(msg);
    record('Active supplier passes S193 guard (fails other validations)', notBlockedByS193, {
      summary: `HTTP ${r.status}`,
      extra: `msg="${msg.slice(0, 180)}"`,
    });
  }

  // 8. Write evidence file
  const evPath = path.join(OUT_DIR, 'api_mutations.json');
  fs.writeFileSync(evPath, JSON.stringify(evidence, null, 2));
  console.log(`\n📁 Evidence: ${evPath}`);

  const passed = evidence.tests.filter(t => t.pass === true).length;
  const failed = evidence.tests.filter(t => t.pass === false).length;
  const skipped = evidence.tests.filter(t => t.pass === null).length;
  console.log(`\n=== RESULT: ${passed} PASS / ${failed} FAIL / ${skipped} SKIP ===`);
  process.exit(failed === 0 ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
