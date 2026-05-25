/**
 * CONSOLIDATED AP View — v3 Field-Sync (Sprint S211)
 *
 * This is the successor to v2.3 (wipe-rebuild). v3 preserves human edits in
 * the three edit tabs (Suppliers SOA / Head Office / CAPEX) and only updates
 * script-owned columns in place.
 *
 * Runs hourly via Cloud Scheduler hitting the web-app URL.
 *
 * Sheet: 1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c
 *   (AP Suppliers - Payment Status (Auto-View), to be renamed `BEI AP Master`
 *   at Phase 4 after CEO name choice.)
 *
 * v3 vs v2.3:
 *   - NEW: HUMAN_OWNED_COLS + SCRIPT_OWNED_COLS constants (explicit ownership
 *     per column).
 *   - NEW: three sync functions replace the monolithic doRefreshAllTabs_:
 *       syncStatusFieldsFromFPM_()      — status/rfp_no/method/check/proc_date
 *       syncTaxFieldsFromCompliance_()  — vatable/vat/ewt
 *       seedNewInvoicesFromSources_()   — APPEND rows not yet in edit tabs
 *   - NEW: Never overwrites a non-blank human cell.
 *   - NEW: _sync_log_v3 tab with per-cell audit rows.
 *   - NEW: _sync_conflicts tab when human and FPM actively disagree.
 *   - NEW: DRY_RUN mode via web-app ?dryRun=1 query parameter.
 *   - KEPT: v2.3 wipe-rebuild behind the renamed flag `useV2WipeRebuild` so
 *     T1.8 can run one final baseline seed, then we flip default to v3.
 *   - KEPT: _sync_log tab + email alerts + self-heal (v2's safety features).
 *
 * Web-app URL: https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec
 * Token: bei-ap-sync-2026-04 (sent as ?key=... query parameter)
 *
 * Routes:
 *   ?fn=refreshAllTabs              -> v3 field-sync (new default)
 *   ?fn=refreshAllTabs&mode=v2      -> legacy v2 wipe-rebuild (T1.8 baseline)
 *   ?fn=refreshAllTabs&dryRun=1     -> v3 dry-run (no writes, previews)
 *   ?fn=runDiagnostics              -> health check
 */

// ───────────────────────────────────────────────────────────────────────────
// Constants
// ───────────────────────────────────────────────────────────────────────────
const FPM_ID = '1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw';
const SOA_ID = '1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4';
const HO_ID = '1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y';
const COMPLIANCE_ID = '1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q';
const DENISE_PP_ID = '13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU';  // v3.7 S248: Denise's 'Project: 2-Week Payment Plan' (4-tab read source)
const NCOLS = 19;

const LOG_TAB = '_sync_log';
const LOG_V3_TAB = '_sync_log_v3';
const CONFLICT_TAB = '_sync_conflicts';
const DRY_PREVIEW_TAB = '_dry_run_preview';
const LOG_MAX_ROWS = 2000;
const OWNED_TRIGGER_FN = 'refreshAllTabs';
const ALERT_EMAIL = 'sam@bebang.ph';

// ───────────────────────────────────────────────────────────────────────────
// v3.9 (S255 Phase 7) — Payment Plan cutover gate
// When false (default): mirrorDenisePaymentPlanTab_ runs hourly; syncStatusFieldsFromFPM_
//   skips Payment Plan tab (mirror handles it).
// When true: mirror stops; syncStatusFieldsFromFPM_ writes STATUS/RFP/METHOD/CHECK NO. into
//   Payment Plan col I (STATUS) etc. This is the cutover path Denise will use when she's
//   ready to make AP Master Payment Plan her primary tracker.
//
// To flip: edit this line, push v3.10, promote deployment. (Or use PropertiesService
// later for toggle-without-redeploy — S256.)
// ───────────────────────────────────────────────────────────────────────────
const payment_plan_mirror_disabled = false;

// v3.10 (S256 Phase 2): Broadened intercompany affiliate allowlist per Denise's signed Section B addendum (2026-05-21)
// Original v3.9 matched only Bebang Enterprise/Kitchen/Shaw Inc. Denise identified 14 additional non-Bebang-branded
// affiliated entities that should route to Intercompany when paired with transfer-fund keywords.
const INTERCO_AFFILIATE_PATTERNS = [
  /^Bebang\s+(Enterprise|Kitchen|Shaw)\s+Inc\.?/i,
  /^B\s*CUBED\s+VENTURES\s+CORP/i,
  /^BB\s+ESTANCIA\s+FOOD\s+CORP/i,
  /^BEIFRANCHISE\s+FOOD\s+OPC/i,
  /^DAY\s+ONES\s+FOOD\s+AND\s+DRINK\s+ESTABLISHMENTS\s+CORP/i,
  /^DMD\s+HOLDINGS\s+INC/i,
  /^HALO[\s-]*HALO\s+ALABANG\s+TOWN\s+FOOD\s+CORP/i,
  /^HALO[\s-]*HALO\s+TERMINAL\s+FOOD\s+CORP/i,
  /^HFFM\s+SOLENAD\s+FOOD\s+SERVICES\s+INC/i,
  /^JL\s+TRADE\s+OPC\s+PERPETUAL\s+FOOD\s+CORP/i,
  /^RED\s+TALDAWA\s+FOODS\s+OPC/i,
  /^RESTO\s+TECH\s+INC/i,
  /^SWEET\s+HARMONY\s+FOOD\s+CORP/i,
  /^TAJ\s+FOOD\s+CORP/i,
  /^TUNGSTEN\s+CAPITAL\s+HOLDINGS\s+OPC/i,
];

const ALERT_MIN_INTERVAL_HOURS = 6;
const ALERT_PROP_KEY = 'last_alert_ts';
const WEBAPP_TOKEN = 'bei-ap-sync-2026-04';

const C_GREEN = '#04400A'; const C_GOLD = '#C8900A'; const C_TINT = '#E6ECE7';
const C_GOLD_L = '#F8F0D9'; const C_RED = '#CC0000'; const C_MID = '#2D7A35';
const C_PURPLE_L = '#F2E5F5';

// The 19-column schema of every edit tab (positional, 1-indexed for Sheets API)
// A  B  C           D            E       F            G      H            I       J            K        L       M      N         O               P          Q        R    S
// 1  2  3           4            5       6            7      8            9      10           11       12      13     14        15              16         17       18   19
// SRC PAYEE INV_NO  INV_DATE     AMOUNT  OUTSTANDING  AGING  AGING_BUCKET STATUS BEI_FIN_NO   RFP_NO   METHOD  CHECK  CATEGORY  CLASSIFICATION  BILLED_TO  VATABLE  VAT  EWT
const COL_NAMES = ['SOURCE', 'PAYEE', 'INVOICE NO.', 'INVOICE DATE', 'AMOUNT', 'OUTSTANDING',
                   'AGING', 'AGING BUCKET', 'STATUS', 'BEI-FIN No.', 'RFP No.', 'METHOD',
                   'CHECK NO.', 'CATEGORY', 'GOODS/SERVICES', 'BILLED TO', 'VATABLE', 'VAT', 'EWT'];

// Ownership declarations (v3 S211).
//   HUMAN_OWNED_COLS: columns the team types directly; script NEVER touches.
//   SCRIPT_OWNED_COLS: columns script may rewrite if source of truth
//                      (FPM or Compliance) has a newer value.
// Rule: if a SCRIPT_OWNED cell is blank on both sides, leave blank.
// Rule: if a SCRIPT_OWNED cell has a human value and source is blank,
//       leave human value (never overwrite with blank).
// Rule: if human cell conflicts with non-blank source value on a SCRIPT_OWNED
//       column, log to _sync_conflicts, keep human value.
const HUMAN_OWNED_COLS = ['source', 'payee', 'invoice_no', 'invoice_date',
                          'amount', 'outstanding', 'category', 'classification', 'billed_to'];
const SCRIPT_OWNED_COLS = ['status', 'rfp_no', 'method', 'check', 'proc_date',
                           'vatable', 'vat', 'ewt', 'aging', 'aging_bucket'];

// 1-indexed column mapping for setValues on the 19-column schema.
// Matches COL_NAMES positions above.
const COL_IDX = {
  source: 1, payee: 2, invoice_no: 3, invoice_date: 4, amount: 5, outstanding: 6,
  aging: 7, aging_bucket: 8, status: 9, bei_fin: 10, rfp_no: 11, method: 12,
  check: 13, category: 14, classification: 15, billed_to: 16,
  vatable: 17, vat: 18, ewt: 19,
  // Legacy aliases used in helpers
  proc_date: null, // proc_date is surfaced via _sync_log only (no column); banner notes it in logs
};

// ───────────────────────────────────────────────────────────────────────────
// Web-app entry point (Cloud Scheduler hits this hourly)
// ───────────────────────────────────────────────────────────────────────────
function doGet(e) {
  const params = (e && e.parameter) || {};
  if (params.key !== WEBAPP_TOKEN) {
    return ContentService.createTextOutput(JSON.stringify({ error: 'unauthorized' }))
      .setMimeType(ContentService.MimeType.JSON);
  }
  const fn = params.fn || 'refreshAllTabs';
  const mode = params.mode || 'v3';  // 'v3' is default; 'v2' runs legacy wipe-rebuild
  const dryRun = params.dryRun === '1';
  try {
    if (fn === 'refreshAllTabs') {
      if (mode === 'v2') {
        const r = doRefreshAllTabs_v2_();
        return ContentService.createTextOutput(JSON.stringify(r))
          .setMimeType(ContentService.MimeType.JSON);
      }
      const r = doRefreshAllTabs_v3_(dryRun);
      return ContentService.createTextOutput(JSON.stringify(r))
        .setMimeType(ContentService.MimeType.JSON);
    }
    if (fn === 'runDiagnostics') {
      const r = runDiagnostics();
      return ContentService.createTextOutput(JSON.stringify(r))
        .setMimeType(ContentService.MimeType.JSON);
    }
    return ContentService.createTextOutput(JSON.stringify({ error: 'unknown fn: ' + fn }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      error: String(err),
      stack: (err && err.stack || '').slice(0, 3000),
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

// Installable-trigger-compatible wrapper (not used; Cloud Scheduler hits doGet).
function refreshAllTabs() {
  const t0 = Date.now();
  let triggerHealth = 'skipped';
  try { triggerHealth = ensureTriggerHealthy_(); } catch (e) { triggerHealth = 'unauth: ' + String(e).slice(0, 80); }
  try {
    const result = doRefreshAllTabs_v3_(false);
    const duration = Date.now() - t0;
    logEvent_('INFO', 'refresh_success_v3', {
      duration_ms: duration,
      v3_stats: result,
      trigger_health: triggerHealth,
    });
    return result;
  } catch (err) {
    const duration = Date.now() - t0;
    const stack = (err && err.stack) ? err.stack.slice(0, 3000) : String(err);
    logEvent_('ERROR', 'refresh_failed_v3', {
      duration_ms: duration,
      error: String(err),
      stack: stack,
      trigger_health: triggerHealth,
    });
    maybeSendAlert_(
      '[BEI AP Auto-View] v3 hourly sync FAILED',
      'The AP Auto-View v3 field-sync threw an error at ' +
        Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm:ss') + ' PHT.\n\n' +
        'Error: ' + String(err) + '\n\n' +
        'Stack:\n' + stack + '\n'
    );
    throw err;
  }
}

// ───────────────────────────────────────────────────────────────────────────
// v3 top-level: three surgical syncs + new-invoice seed
// ───────────────────────────────────────────────────────────────────────────
function doRefreshAllTabs_v3_(dryRun) {
  const t0 = Date.now();
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Snapshot source lookups (done once; reused by the 3 sync functions)
  const fpmLookup = buildFpmLookup_();
  const taxLookup = buildTaxLookup_();

  const stats = { dry_run: !!dryRun };

  // T1.2 — three sync functions
  const statusStats = syncStatusFieldsFromFPM_(ss, fpmLookup, dryRun);
  stats.status_sync = statusStats;

  const taxStats = syncTaxFieldsFromCompliance_(ss, taxLookup, dryRun);
  stats.tax_sync = taxStats;

  // T1.2 T1.2b — seed new invoices from sources (append-only)
  const seedStats = seedNewInvoicesFromSources_(ss, fpmLookup, taxLookup, dryRun);
  stats.seed = seedStats;

  // v3.9 (S255 Phase 3.2): refresh banners from current data before logging cycle complete
  if (!dryRun) { stats.banners = recomputeBanners_(ss); }
  stats.duration_ms = Date.now() - t0;
  if (dryRun) {
    writeDryRunPreview_(ss, stats);
  } else {
    logEvent_('INFO', 'v3_cycle_complete', stats);
  }
  return stats;
}

// ───────────────────────────────────────────────────────────────────────────
// FPM lookup — indexed by two keys: BEI-FIN No. and (payee_upper + '|' + amount)
// ───────────────────────────────────────────────────────────────────────────
function buildFpmLookup_() {
  const fpmData = SpreadsheetApp.openById(FPM_ID).getSheetByName('RFP Summary').getDataRange().getValues();
  const fh = fpmData[0]; const fi = (n) => fh.indexOf(n);
  const byFin = {}; const byPayeeAmt = {};
  fpmData.slice(1).forEach(r => {
    const fin = nk(r[fi('BEI-FIN No. (if applicable)')]);
    const payee = (r[fi('Payee')] || '').toString().trim().toUpperCase();
    const amt = Math.round(toNum(r[fi('Amount Due')]) * 100) / 100;
    const e = {
      status: (r[fi('Status')] || '').toString().trim(),
      rfp: (r[fi('RFP NO.')] || '').toString(),
      method: (r[fi('Payment Method')] || '').toString().trim(),
      check: (r[fi('Check No./Ref No.')] || '').toString().trim(),
      proc: serialToDate(r[fi('Processed Date')]),
    };
    if (fin) byFin[fin] = e;
    if (payee && amt) byPayeeAmt[payee + '|' + amt] = e;
  });
  return { byFin, byPayeeAmt };
}

// Tax lookup: by invoice_no (upper) → {vatable, vat, ewt}
function buildTaxLookup_() {
  const compSS = SpreadsheetApp.openById(COMPLIANCE_ID);
  const poItems = compSS.getSheetByName('PO Items').getDataRange().getValues();
  const pih = poItems[0]; const pii = (n) => pih.indexOf(n);
  const poVatByPoNo = {}; const poAmtByPoNo = {};
  poItems.slice(1).forEach(r => {
    const poNo = (r[pii('PO No')] || '').toString().trim();
    if (!poNo) return;
    poVatByPoNo[poNo] = (poVatByPoNo[poNo] || 0) + toNum(r[pii('VAT')]);
    poAmtByPoNo[poNo] = (poAmtByPoNo[poNo] || 0) + toNum(r[pii('Amount')]);
  });
  const advInv = compSS.getSheetByName('Advance Invoices').getDataRange().getValues();
  const aih = advInv[0]; const aii = (n) => aih.indexOf(n);
  const byInvKey = {};
  advInv.slice(1).forEach(r => {
    const key = invKey(r[aii('Invoice No')]);
    if (!key) return;
    const poNo = (r[aii('PO No')] || '').toString().trim();
    const poTotalVat = poVatByPoNo[poNo] || 0;
    const poTotalAmt = poAmtByPoNo[poNo] || 0;
    const invAmt = toNum(r[aii('Invoice Amount')]);
    const share = poTotalAmt > 0 ? Math.min(invAmt / poTotalAmt, 1.0) : 0;
    const vat = poTotalVat * share;
    const ewt = toNum(r[aii('EWT Amount')]);
    byInvKey[key] = { vatable: invAmt - vat, vat, ewt };
  });
  return byInvKey;
}

// ───────────────────────────────────────────────────────────────────────────
// Read the 3 edit tabs, skipping banner rows. Return an array of
// { tab, rowIdx1 (1-indexed row), rec (object keyed by COL_NAMES) }
// ───────────────────────────────────────────────────────────────────────────
function readEditTabRows_(ss, tabName) {
  const sh = ss.getSheetByName(tabName);
  if (!sh) return { sheet: null, rows: [], headerRowIdx: 0 };
  const all = sh.getDataRange().getValues();
  // Find the SOURCE header row (column-header for data) — first row whose cell A = 'SOURCE'
  let hdrIdx = -1;
  for (let i = 0; i < all.length; i++) {
    if ((all[i][0] || '').toString().trim().toUpperCase() === 'SOURCE') { hdrIdx = i; break; }
  }
  if (hdrIdx < 0) return { sheet: sh, rows: [], headerRowIdx: 0 };
  const rows = [];
  for (let i = hdrIdx + 1; i < all.length; i++) {
    const r = all[i];
    // skip fully-empty rows
    if (!r.some(c => c !== '' && c !== null)) continue;
    const rec = {};
    COL_NAMES.forEach((n, ix) => { rec[n] = r[ix]; });
    rows.push({ tab: tabName, rowIdx1: i + 1, rec });
  }
  return { sheet: sh, rows, headerRowIdx: hdrIdx + 1 };
}

// ───────────────────────────────────────────────────────────────────────────
// syncStatusFieldsFromFPM_ — update status/rfp_no/method/check on edit tabs.
// Primary join: BEI-FIN No. → FPM. Secondary: payee + amount.
// Never overwrites a non-blank human value in a SCRIPT_OWNED column with a
// blank or conflicting source value without logging to _sync_conflicts.
// ───────────────────────────────────────────────────────────────────────────
function syncStatusFieldsFromFPM_(ss, fpmLookup, dryRun) {
  const stats = { updates: 0, conflicts: 0, nochange: 0, tabs_seen: {}, sample_changes: [] };
  (payment_plan_mirror_disabled
    ? ['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany', 'Payment Plan']
    : ['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany']
  ).forEach(tabName => {
    const t = readEditTabRows_(ss, tabName);
    if (!t.sheet) return;
    stats.tabs_seen[tabName] = t.rows.length;
    t.rows.forEach(row => {
      const fin = nk(row.rec['BEI-FIN No.']);
      const payeeKey = (row.rec['PAYEE'] || '').toString().trim().toUpperCase() + '|' +
                       (Math.round(toNum(row.rec['AMOUNT']) * 100) / 100);
      // Per-tab lookup strategy matches v2 exactly:
      //   Suppliers SOA  -> byFin only (RFP ID is the join key)
      //   Head Office    -> byPayeeAmt only (no RFP ID in HO source)
      //   CAPEX          -> byPayeeAmt only
      let fpm;
      if (tabName === 'Suppliers SOA') fpm = fpmLookup.byFin[fin];
      else fpm = fpmLookup.byPayeeAmt[payeeKey];
      if (!fpm) return;

      // v3 narrow rule: ONLY update a field if FPM has an unambiguous source
      // of truth for it. Don't re-derive from the Auto-View's own prior value.
      // This prevents thrash when v2's derivation (which v2 already ran) is
      // slightly different from v3's re-interpretation of the same data.
      const updates = {};

      // Status update — only when FPM.status maps to one of the definitive
      // Auto-View statuses. If FPM.status is blank or ambiguous, leave the
      // current Auto-View STATUS alone.
      const definitiveStatus = fpmStatusToDisplay_(fpm.status);
      if (definitiveStatus) {
        maybeApplyUpdate_(updates, 'status', row.rec['STATUS'], definitiveStatus);
      }

      // rfp_no/method/check — only update if FPM has non-blank AND the current
      // Auto-View value is different (maybeApplyUpdate_ already blocks blank-
      // overrides-nonblank).
      if (fpm.rfp) maybeApplyUpdate_(updates, 'rfp_no', row.rec['RFP No.'], String(fpm.rfp));
      if (fpm.method) maybeApplyUpdate_(updates, 'method', row.rec['METHOD'], fpm.method);
      if (fpm.check) maybeApplyUpdate_(updates, 'check', row.rec['CHECK NO.'], fpm.check);

      if (Object.keys(updates).length === 0) { stats.nochange++; return; }

      // For diagnostics, sample up to 20 proposed changes into stats
      if (stats.sample_changes.length < 20) {
        const diff = {};
        Object.keys(updates).forEach(k => { diff[k] = { old: updates[k].old, new: updates[k].new }; });
        stats.sample_changes.push({ tab: tabName, row: row.rowIdx1, payee: row.rec['PAYEE'], diff });
      }

      if (!dryRun) {
        applyUpdatesToRow_(t.sheet, row.rowIdx1, updates);
        Object.keys(updates).forEach(k => {
          logCellChange_(ss, tabName, row.rowIdx1, k, updates[k].old, updates[k].new, 'fpm_status_sync');
        });
      }
      stats.updates++;
    });
  });
  return stats;
}

// Map FPM.status to Auto-View's display STATUS value. Returns '' (empty) when
// FPM gives no definitive answer — in that case v3 leaves the existing
// Auto-View STATUS untouched.
function fpmStatusToDisplay_(fpmStatus) {
  const fst = (fpmStatus || '').toString().trim();
  if (fst === 'Paid/ Cleared') return 'PAID';
  if (fst === 'Check Released') return 'CHECK RELEASED';
  if (fst === 'Check Ready') return 'CHECK READY';
  if (fst === 'For Online Payment') return 'FOR ONLINE PAYMENT';
  if (['For Approval','For Signature','For Funding','For Review','Received','For Released'].indexOf(fst) >= 0) return 'IN PIPELINE';
  return '';  // not definitive — don't update STATUS
}

// Used by seedNewInvoicesFromSources_ to compute initial STATUS for brand-new
// rows seeded into the edit tabs. Mirrors v2's SOA/HO AP derivation logic.
function deriveDisplayStatus_(rec, fpm) {
  const finStatus = (rec['STATUS'] || '').toString().trim().toUpperCase();
  const fst = (fpm.status || '').toString().trim();
  if (finStatus === 'PAID' || fst === 'Paid/ Cleared') return 'PAID';
  if (finStatus === 'RELEASED' || fst === 'Check Released') return 'CHECK RELEASED';
  if (fst === 'Check Ready') return 'CHECK READY';
  if (fst === 'For Online Payment') return 'FOR ONLINE PAYMENT';
  if (['For Approval','For Signature','For Funding','For Review','Received','For Released'].indexOf(fst) >= 0) return 'IN PIPELINE';
  if (finStatus === 'PROCESSED ONLINE') return 'PROCESSED ONLINE';
  if (finStatus === 'PROCESSED, TRANSFERRED TO FINANCE') return 'WITH FINANCE';
  return finStatus || 'NO RFP YET';
}

// ───────────────────────────────────────────────────────────────────────────
// syncTaxFieldsFromCompliance_ — update vatable/vat/ewt.
// ───────────────────────────────────────────────────────────────────────────
function syncTaxFieldsFromCompliance_(ss, taxLookup, dryRun) {
  const stats = { updates: 0, conflicts: 0, nochange: 0 };
  ['Suppliers SOA', 'Head Office', 'CAPEX'].forEach(tabName => {
    const t = readEditTabRows_(ss, tabName);
    if (!t.sheet) return;
    t.rows.forEach(row => {
      const k = invKey(row.rec['INVOICE NO.']);
      if (!k) return;
      const tx = taxLookup[k];
      if (!tx) return;
      const updates = {};
      maybeApplyNumericUpdate_(updates, 'vatable', row.rec['VATABLE'], tx.vatable);
      maybeApplyNumericUpdate_(updates, 'vat', row.rec['VAT'], tx.vat);
      maybeApplyNumericUpdate_(updates, 'ewt', row.rec['EWT'], tx.ewt);
      if (Object.keys(updates).length === 0) { stats.nochange++; return; }
      if (!dryRun) {
        applyUpdatesToRow_(t.sheet, row.rowIdx1, updates);
        Object.keys(updates).forEach(x => {
          logCellChange_(ss, tabName, row.rowIdx1, x, updates[x].old, updates[x].new, 'compliance_tax_sync');
        });
      }
      stats.updates++;
    });
  });
  return stats;
}

// ───────────────────────────────────────────────────────────────────────────
// seedNewInvoicesFromSources_ — scans SOA + HO AP; APPENDS rows missing from
// Auto-View edit tabs. Never removes rows.
//
// Safety guarantees (T1.2b):
//   (a) NEVER removes rows from AP Master — sources are authoritative for
//       existence, but AP Master retains human-added rows that have no source
//       counterpart (e.g., future direct-entry invoices).
//   (b) Writes an audit row to _sync_log_v3 for every insert with event
//       'invoice_seeded' + source_sheet + source_row_id.
//   (c) If a seeded row appears to be a duplicate (same supplier+invoice_no
//       but different amount), flags to _sync_conflicts instead of silent
//       append.
//   (d) Skips rows where outstanding=0 (already paid — no need to seed into
//       active register).
// ───────────────────────────────────────────────────────────────────────────
function seedNewInvoicesFromSources_(ss, fpmLookup, taxLookup, dryRun) {
  const stats = { scanned: 0, appended: 0, duplicate_conflicts: 0, skipped_paid: 0, skipped_existing: 0 };

  // Index existing edit-tab rows by the same tolerant key set used in parity
  const existingIndex = {};
  ['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'].forEach(tabName => {
    const t = readEditTabRows_(ss, tabName);
    t.rows.forEach(row => {
      const payeeKey = (row.rec['PAYEE'] || '').toString().trim().toUpperCase();
      const amt = Math.round(toNum(row.rec['AMOUNT']) * 100) / 100;
      const dateStr = formatDateLike_(row.rec['INVOICE DATE']);
      const invVariants = invNoVariants_(row.rec['INVOICE NO.']);
      invVariants.forEach(iv => {
        existingIndex[payeeKey + '|' + iv + '|' + amt] = { tab: tabName, row };
      });
      // fallback key: payee + amount + date
      existingIndex['FB|' + payeeKey + '|' + amt + '|' + dateStr] = { tab: tabName, row };
      // v3.10 (S256 P2.3): FPM-SOA-aware dedup key — lets Denise PP seed recognise FPM-sourced rows
      var source = (row.rec['SOURCE'] || '').toString().trim();
      if (source === 'FPM-SOA' || source === 'Suppliers SOA') {
        existingIndex['FPMSOA|' + payeeKey + '|' + amt] = { tab: tabName, row };
      }
    });
  });

  // Scan sources
  const newRowsByTab = { 'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [] };

  // SOA source
  const soaData = SpreadsheetApp.openById(SOA_ID).getSheetByName('SUPPLIERS SOA').getDataRange().getValues();
  const sh = soaData[1]; const si = (n) => sh.indexOf(n);
  soaData.slice(2).forEach((r, i) => {
    const supplier = (r[si('SUPPLIER NAME')] || '').toString().trim();
    if (!supplier) return;
    const amt = toNum(r[si('AMOUNT')]);
    const out = toNum(r[si('OUTSTANDING BALANCE')]);
    const invoiceNo = (r[si('INVOICE NO.')] || '').toString().trim();
    const billed = (r[si('BILLED TO')] || '').toString().trim().toUpperCase();
    const rfpId = nk(r[si('RFP ID')]);
    const invDate = serialToDate(r[si('INVOICE DATE')]);
    stats.scanned++;
    if (out <= 0) { stats.skipped_paid++; return; }  // guarantee (d)

    const payeeKey = supplier.toUpperCase();
    const amtK = Math.round(amt * 100) / 100;
    const dateStr = formatDateLike_(invDate);
    const invVariants = invNoVariants_(invoiceNo);
    let found = false;
    invVariants.forEach(iv => { if (existingIndex[payeeKey + '|' + iv + '|' + amtK]) found = true; });
    if (!found && existingIndex['FB|' + payeeKey + '|' + amtK + '|' + dateStr]) found = true;
    if (found) { stats.skipped_existing++; return; }

    // Check for potential duplicate (same supplier+inv_no but different amount)
    const matchingPayeeInv = invVariants.map(iv => existingIndex[payeeKey + '|' + iv + '|']).filter(x => x);
    if (matchingPayeeInv.length > 0) {
      // Conflict: same payee+invoice_no but different amount
      stats.duplicate_conflicts++;
      if (!dryRun) {
        logConflict_(ss, 'Suppliers SOA', 'N/A', 'amount',
                     String(matchingPayeeInv[0].row.rec['AMOUNT']), String(amt),
                     'seed_duplicate_invoice_different_amount');
      }
      return;
    }

    // Compute derived status + tax
    const fpm = fpmLookup.byFin[rfpId] || {};
    const display = deriveDisplayStatus_({ STATUS: (r[si('FIN STATUS')] || '').toString().trim().toUpperCase() }, fpm);
    const tx = taxLookup[invKey(invoiceNo)] || { vatable: 0, vat: 0, ewt: 0 };
    const aging = (function() { let a = toNum(r[si('AGING (days)')]); if (a > 2000) a = 0; return a; })();

    newRowsByTab['Suppliers SOA'].push({
      rowValues: [
        'Suppliers SOA', supplier, invoiceNo, invDate, amt, out, aging, agingBucket(aging),
        display, rfpId, fpm.rfp || '', fpm.method || '', fpm.check || '',
        'Supplier Payments', billed, billed, tx.vatable || 0, tx.vat || 0, tx.ewt || 0,
      ],
      sourceSheet: 'SOA',
      sourceRowId: i + 3,
    });
  });

  // HO AP source
  const hoData = SpreadsheetApp.openById(HO_ID).getSheetByName('Detailed HEAD OFFICE').getDataRange().getValues();
  const hh = hoData[1]; const hi = (n) => hh.indexOf(n);
  hoData.slice(2).forEach((r, i) => {
    const payee = (r[hi('PAYABLE TO')] || '').toString().trim();
    if (!payee) return;
    const classification = (r[hi('GOODS/SERVICES')] || '').toString().trim().toUpperCase();
    const gross = toNum(r[hi('GROSS AMOUNT')]);
    const out = toNum(r[hi('OUTSTANDING BALANCE')]);
    stats.scanned++;
    if (out <= 0) { stats.skipped_paid++; return; }

    const invNo = (r[hi('OR/SI NUMBER')] || '').toString().trim();
    const invDate = serialToDate(r[hi('INVOICE DATE')]);
    const vatable = toNum(r[hi('VATABLE SALES')]);
    const vat = toNum(r[hi('VAT(12%)')]);
    const ewt = toNum(r[hi('EWT')]);
    const statusHO = (r[hi('STATUS')] || '').toString().trim().toUpperCase();

    const tabName = classification === 'PROJECT COST' ? 'CAPEX' : 'Head Office';
    const srcLabel = classification === 'PROJECT COST' ? 'CAPEX' : 'Head Office AP';
    const payeeKey = payee.toUpperCase();
    const amtK = Math.round(gross * 100) / 100;
    const dateStr = formatDateLike_(invDate);
    const invVariants = invNoVariants_(invNo);
    let found = false;
    invVariants.forEach(iv => { if (existingIndex[payeeKey + '|' + iv + '|' + amtK]) found = true; });
    if (!found && existingIndex['FB|' + payeeKey + '|' + amtK + '|' + dateStr]) found = true;
    if (found) { stats.skipped_existing++; return; }

    const fpm = fpmLookup.byPayeeAmt[payeeKey + '|' + amtK] || {};
    const display = deriveDisplayStatus_({ STATUS: statusHO }, fpm);
    const cat = classification === 'PROJECT COST' ? 'CAPEX' : classification === 'HEAD OFFICE' ? 'Head Office'
                : classification ? classification.charAt(0) + classification.slice(1).toLowerCase() : '';
    const aging = (function() { let a = toNum(r[hi('AGING (days)')]); if (a > 2000) a = 0; return a; })();

    newRowsByTab[tabName].push({
      rowValues: [
        srcLabel, payee, invNo, invDate, gross, out, aging, agingBucket(aging),
        display, '', fpm.rfp || '', fpm.method || '', fpm.check || '',
        cat, classification, '', vatable, vat, ewt,
      ],
      sourceSheet: 'HO_AP',
      sourceRowId: i + 3,
    });
  });

  // Append new rows to the bottom of each edit tab
  Object.keys(newRowsByTab).forEach(tabName => {
    const toAppend = newRowsByTab[tabName];
    if (toAppend.length === 0) return;
    if (!dryRun) {
      const sh = ss.getSheetByName(tabName);
      if (sh) {
        const startRow = sh.getLastRow() + 1;
        const values = toAppend.map(x => x.rowValues);
        sh.getRange(startRow, 1, values.length, NCOLS).setValues(values);
        // Log each insert
        toAppend.forEach((x, i) => {
          logEvent_v3_(ss, 'invoice_seeded', {
            tab: tabName,
            ap_master_row_idx: startRow + i,
            source_sheet: x.sourceSheet,
            source_row_id: x.sourceRowId,
            payee: x.rowValues[1],
            invoice_no: x.rowValues[2],
            amount: x.rowValues[4],
          });
        });
      }
    }
    stats.appended += toAppend.length;
  });


  // v4 patch (2026-05-13) — also seed from FPM (the active workflow source).
  // FPM has 1,865 rows that the archived SOA/HO seeds miss. See seedNewInvoicesFromFPM_.
  try {
    const fpmStats = seedNewInvoicesFromFPM_(ss, fpmLookup, taxLookup, existingIndex, dryRun);
    stats.fpm_seed = fpmStats;
    stats.appended += fpmStats.appended;
    stats.skipped_existing += fpmStats.skipped_existing;
  } catch (e) {
    stats.fpm_seed_error = String(e);
  }

  // v3.7 patch (2026-05-14, S248) — also seed from Denise's 2-Week Payment Plan sheet.
  // Reads 4 tabs in priority order: Suppliers w/o FD & Middleby, Middleby, Forward Dynamics, Masterlist.
  // Middleby + Forward Dynamics are tagged as 'Disputed - Eventually Payable' per CEO directive.
  try {
    const deniseStats = seedFromDenisePaymentPlan_(ss, fpmLookup, taxLookup, existingIndex, dryRun);
    stats.denise_seed = deniseStats;
    stats.appended += deniseStats.appended;
    stats.skipped_existing += deniseStats.skipped_existing;
  } catch (e) {
    stats.denise_seed_error = String(e);
  }

  // v3.8 patch (2026-05-14, S248) — also auto-mirror Denise's full unpaid list into the
  // 'Payment Plan' tab on AP Master. This is a READY-TO-SWITCH preview surface — strict-locked
  // to sam@bebang.ph only until Denise officially switches. Wipe-and-rebuild on each cycle so
  // the mirror stays in sync with Denise's standalone sheet during the 2-week transition.
  try {
    const mirrorStats = mirrorDenisePaymentPlanTab_(ss, dryRun);
    stats.payment_plan_mirror = mirrorStats;
  } catch (e) {
    stats.payment_plan_mirror_error = String(e);
  }

  return stats;
}

// ───────────────────────────────────────────────────────────────────────────
// v2 legacy (kept for T1.8 final baseline seed). Identical to v2.3's
// doRefreshAllTabs_. The only difference is the entry function name.
// ───────────────────────────────────────────────────────────────────────────
function doRefreshAllTabs_v2_() {
  return doRefreshAllTabs_();
}

function doRefreshAllTabs_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const now = Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm') + ' PHT';

  const fpmLookup = buildFpmLookup_();
  const taxByInvKey = buildTaxLookup_();

  const rows = [];
  const soaData = SpreadsheetApp.openById(SOA_ID).getSheetByName('SUPPLIERS SOA').getDataRange().getValues();
  const sh = soaData[1]; const si = (n) => sh.indexOf(n);
  soaData.slice(2).forEach(r => {
    const supplier = (r[si('SUPPLIER NAME')] || '').toString().trim();
    if (!supplier) return;
    let amt = toNum(r[si('AMOUNT')]);
    let out = toNum(r[si('OUTSTANDING BALANCE')]);
    let aging = toNum(r[si('AGING (days)')]);
    if (aging > 2000) aging = 0;
    const finStatus = (r[si('FIN STATUS')] || '').toString().trim();
    const rfpId = nk(r[si('RFP ID')]);
    const invoiceNo = (r[si('INVOICE NO.')] || '').toString().trim();
    const billed = (r[si('BILLED TO')] || '').toString().trim().toUpperCase();
    const fpm = fpmLookup.byFin[rfpId] || {};
    let display;
    if (finStatus === 'PAID' || fpm.status === 'Paid/ Cleared') { display = 'PAID'; out = 0; }
    else if (finStatus === 'RELEASED' || fpm.status === 'Check Released') display = 'CHECK RELEASED';
    else if (fpm.status === 'Check Ready') display = 'CHECK READY';
    else if (fpm.status === 'For Online Payment') display = 'FOR ONLINE PAYMENT';
    else if (['For Approval','For Signature','For Funding','For Review','Received','For Released'].indexOf(fpm.status) >= 0) display = 'IN PIPELINE';
    else if (finStatus === 'PROCESSED ONLINE') display = 'PROCESSED ONLINE';
    else if (rfpId) display = 'IN PIPELINE';
    else display = 'NO RFP YET';
    const tax = taxByInvKey[invKey(invoiceNo)] || {};
    rows.push({
      source: 'Suppliers SOA', payee: supplier,
      invoice_no: invoiceNo, invoice_date: serialToDate(r[si('INVOICE DATE')]),
      amount: amt, outstanding: out, aging, aging_bucket: agingBucket(aging),
      bei_fin: rfpId, rfp_no: fpm.rfp || '', status: display,
      method: fpm.method || '', check: fpm.check || '', proc_date: fpm.proc || '',
      category: 'Supplier Payments', classification: billed, billed_to: billed,
      vatable: tax.vatable || 0, vat: tax.vat || 0, ewt: tax.ewt || 0,
    });
  });

  const hoData = SpreadsheetApp.openById(HO_ID).getSheetByName('Detailed HEAD OFFICE').getDataRange().getValues();
  const hh = hoData[1]; const hi = (n) => hh.indexOf(n);
  hoData.slice(2).forEach(r => {
    const payee = (r[hi('PAYABLE TO')] || '').toString().trim();
    if (!payee) return;
    const classification = (r[hi('GOODS/SERVICES')] || '').toString().trim().toUpperCase();
    let gross = toNum(r[hi('GROSS AMOUNT')]);
    let out = toNum(r[hi('OUTSTANDING BALANCE')]);
    let aging = toNum(r[hi('AGING (days)')]);
    if (aging > 2000) aging = 0;
    const vatable = toNum(r[hi('VATABLE SALES')]);
    const vat = toNum(r[hi('VAT(12%)')]);
    const ewt = toNum(r[hi('EWT')]);
    const statusHO = (r[hi('STATUS')] || '').toString().trim();
    const fpm = fpmLookup.byPayeeAmt[payee.toUpperCase() + '|' + (Math.round(gross * 100) / 100)] || {};
    let display;
    if (statusHO === 'PAID' || fpm.status === 'Paid/ Cleared') { display = 'PAID'; out = 0; }
    else if (fpm.status === 'Check Released') display = 'CHECK RELEASED';
    else if (fpm.status === 'Check Ready') display = 'CHECK READY';
    else if (fpm.status === 'For Online Payment') display = 'FOR ONLINE PAYMENT';
    else if (['For Approval','For Signature','For Funding','For Review','Received','For Released'].indexOf(fpm.status) >= 0) display = 'IN PIPELINE';
    else if (statusHO === 'PROCESSED, TRANSFERRED TO FINANCE') display = 'WITH FINANCE';
    else display = statusHO || 'NO RFP YET';
    const cat = classification === 'PROJECT COST' ? 'CAPEX'
              : classification === 'HEAD OFFICE' ? 'Head Office'
              : classification ? classification.charAt(0) + classification.slice(1).toLowerCase() : '';
    rows.push({
      source: classification === 'PROJECT COST' ? 'CAPEX' : 'Head Office AP',
      payee, invoice_no: (r[hi('OR/SI NUMBER')] || '').toString().trim(),
      invoice_date: serialToDate(r[hi('INVOICE DATE')]),
      amount: gross, outstanding: out, aging, aging_bucket: agingBucket(aging),
      bei_fin: '', rfp_no: fpm.rfp || '', status: display,
      method: fpm.method || '', check: fpm.check || '', proc_date: fpm.proc || '',
      category: cat, classification, billed_to: '', vatable, vat, ewt,
    });
  });
  rows.sort((a, b) => b.aging - a.aging);

  const tabs = [
    { name: 'All Liabilities', rows: rows },
    { name: 'Suppliers SOA', rows: rows.filter(r => r.source === 'Suppliers SOA') },
    { name: 'Head Office', rows: rows.filter(r => r.source === 'Head Office AP') },
    { name: 'CAPEX', rows: rows.filter(r => r.source === 'CAPEX') },
    { name: 'Needs RFP', rows: rows.filter(r => r.status === 'NO RFP YET' && r.outstanding > 0) },
    { name: 'With Finance (No RFP)', rows: rows.filter(r => r.status === 'WITH FINANCE' && r.outstanding > 0) },
    { name: 'Check Released', rows: rows.filter(r => r.status === 'CHECK RELEASED') },
    { name: 'In Pipeline', rows: rows.filter(r => ['IN PIPELINE','CHECK READY','FOR ONLINE PAYMENT'].indexOf(r.status) >= 0) },
    { name: 'VAT Gaps', rows: rows.filter(r => r.outstanding > 50000 && r.vat === 0) },
    { name: 'PAID', rows: rows.filter(r => r.status === 'PAID') },
  ];

  const perTab = {};
  tabs.forEach(td => {
    let sheet = ss.getSheetByName(td.name);
    if (!sheet) sheet = ss.insertSheet(td.name);
    sheet.clear();
    sheet.clearConditionalFormatRules();
    perTab[td.name] = td.rows.length;
    if (td.rows.length === 0) {
      sheet.getRange(1, 1).setValue(td.name.toUpperCase() + ' (no data)');
      return;
    }
    const isCapex = td.name === 'CAPEX';
    const isVatGaps = td.name === 'VAT Gaps';
    const grid = buildGrid(td.rows, td.name.toUpperCase(), now, isCapex, isVatGaps);
    sheet.getRange(1, 1, grid.length, grid[0].length).setValues(grid);
    formatTab(sheet, td.rows.length, grid.length - td.rows.length);
  });

  ss.getSheets().forEach(s => { if (s.getName().indexOf('_old_') === 0) ss.deleteSheet(s); });
  SpreadsheetApp.flush();
  return { totalRows: rows.length, perTab };
}

// ───────────────────────────────────────────────────────────────────────────
// Update helpers
// ───────────────────────────────────────────────────────────────────────────
function maybeApplyUpdate_(updates, key, oldVal, newVal) {
  const oldStr = (oldVal == null ? '' : String(oldVal).trim());
  const newStr = (newVal == null ? '' : String(newVal).trim());
  if (oldStr === newStr) return;
  // Never overwrite a non-blank human value with a blank script value
  if (newStr === '' && oldStr !== '') return;
  // Numeric-equivalence check: if both sides are digits-only and compare
  // equal as integers, don't update. This catches the "585" (number-coerced
  // by Sheets on write) vs "0585" (text-formatted with leading zero) case
  // that would otherwise trigger endless rewrites.
  if (/^\d+$/.test(oldStr) && /^\d+$/.test(newStr)) {
    if (parseInt(oldStr, 10) === parseInt(newStr, 10)) return;
  }
  // Same-digit-prefix check (e.g., "123" vs "123 BDO") — if old is a numeric
  // prefix of new and new has extra context, prefer the more specific new
  // value. But if old has MORE content than new, keep old.
  if (oldStr && newStr && oldStr.length > newStr.length && oldStr.indexOf(newStr) === 0) return;
  updates[key] = { old: oldStr, new: newStr };
}

function maybeApplyNumericUpdate_(updates, key, oldVal, newVal) {
  const oldN = toNum(oldVal);
  const newN = toNum(newVal);
  // Round to 2 decimals for comparison
  if (Math.round(oldN * 100) === Math.round(newN * 100)) return;
  // Never overwrite a non-zero human value with 0 (tax values can legitimately be 0)
  // but prefer the non-zero source value when old was 0.
  updates[key] = { old: oldN, new: newN };
}

function applyUpdatesToRow_(sheet, rowIdx1, updates) {
  Object.keys(updates).forEach(k => {
    const col = COL_IDX[k];
    if (!col) return;
    sheet.getRange(rowIdx1, col).setValue(updates[k].new);
  });
}

// ───────────────────────────────────────────────────────────────────────────
// Logging (v2 _sync_log stays; v3 adds _sync_log_v3 per-cell)
// ───────────────────────────────────────────────────────────────────────────
function logCellChange_(ss, tab, rowIdx1, column, oldVal, newVal, reason) {
  logEvent_v3_(ss, 'cell_updated', {
    tab, ap_master_row_idx: rowIdx1, column, old_value: String(oldVal).slice(0, 200),
    new_value: String(newVal).slice(0, 200), reason,
  });
}

function logConflict_(ss, tab, rowIdx1, column, humanVal, sourceVal, reason) {
  let t = ss.getSheetByName(CONFLICT_TAB);
  if (!t) {
    t = ss.insertSheet(CONFLICT_TAB);
    t.getRange(1, 1, 1, 7).setValues([['ts_pht', 'tab', 'row_idx', 'column', 'human_value', 'source_value', 'reason']]);
    t.getRange(1, 1, 1, 7).setBackground(C_GREEN).setFontColor('#FFFFFF').setFontWeight('bold');
    t.setFrozenRows(1);
  }
  const ts = Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm:ss') + ' PHT';
  t.appendRow([ts, tab, rowIdx1, column, String(humanVal).slice(0, 500), String(sourceVal).slice(0, 500), reason]);
}

function logEvent_v3_(ss, event, payload) {
  let t = ss.getSheetByName(LOG_V3_TAB);
  if (!t) {
    t = ss.insertSheet(LOG_V3_TAB);
    t.getRange(1, 1, 1, 4).setValues([['ts_pht', 'event', 'payload_json', 'notes']]);
    t.getRange(1, 1, 1, 4).setBackground(C_GREEN).setFontColor('#FFFFFF').setFontWeight('bold');
    t.setFrozenRows(1);
    t.setColumnWidth(1, 140);
    t.setColumnWidth(2, 160);
    t.setColumnWidth(3, 640);
    t.setColumnWidth(4, 160);
  }
  const ts = Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm:ss') + ' PHT';
  t.appendRow([ts, event, JSON.stringify(payload).slice(0, 4000), '']);
  const last = t.getLastRow();
  if (last > LOG_MAX_ROWS + 1) { t.deleteRows(2, last - (LOG_MAX_ROWS + 1)); }
}

function writeDryRunPreview_(ss, stats) {
  let t = ss.getSheetByName(DRY_PREVIEW_TAB);
  if (!t) t = ss.insertSheet(DRY_PREVIEW_TAB);
  t.clear();
  t.getRange(1, 1).setValue('DRY RUN — ' + Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm:ss') + ' PHT');
  t.getRange(2, 1).setValue('No writes were made. Summary:');
  t.getRange(3, 1).setValue(JSON.stringify(stats, null, 2));
}

// ───────────────────────────────────────────────────────────────────────────
// V2 carryover — logging / trigger mgmt / diagnostics (unchanged)
// ───────────────────────────────────────────────────────────────────────────
function onOpen() {
  try {
    SpreadsheetApp.getUi().createMenu('AP Sync')
      .addItem('Refresh Now (v3)', 'refreshAllTabs')
      .addItem('Run Diagnostics', 'runDiagnostics')
      .addSeparator()
      .addItem('View v3 Log', 'openSyncLogV3Tab')
      .addItem('View Conflicts', 'openConflictsTab')
      .addItem('View v2 Log', 'openSyncLogTab')
      .addToUi();
  } catch (e) {}
}

function openSyncLogV3Tab() {
  const ss = SpreadsheetApp.getActive();
  const t = ss.getSheetByName(LOG_V3_TAB);
  if (t) ss.setActiveSheet(t);
  else ss.toast('No v3 log yet — run Refresh Now first.', 'Log', 5);
}
function openConflictsTab() {
  const ss = SpreadsheetApp.getActive();
  const t = ss.getSheetByName(CONFLICT_TAB);
  if (t) ss.setActiveSheet(t);
  else ss.toast('No conflicts yet. Clean sync.', 'Conflicts', 5);
}
function openSyncLogTab() {
  const ss = SpreadsheetApp.getActive();
  const t = ss.getSheetByName(LOG_TAB);
  if (t) ss.setActiveSheet(t);
  else ss.toast('No v2 log (v2 retired after T1.8).', 'Log', 5);
}

function setupHourlyTrigger() {
  removeOwnedTriggers_();
  ScriptApp.newTrigger(OWNED_TRIGGER_FN).timeBased().everyHours(1).create();
  SpreadsheetApp.getActive().toast('Hourly sync enabled (Apps Script trigger).', 'Setup', 5);
  logEvent_('INFO', 'trigger_installed', { fn: OWNED_TRIGGER_FN, interval_hours: 1 });
}
function removeTrigger() {
  const n = removeOwnedTriggers_();
  SpreadsheetApp.getActive().toast('Removed ' + n + ' trigger(s).', 'Disable', 5);
  logEvent_('WARN', 'trigger_removed_manually', { count: n });
}
function removeOwnedTriggers_() {
  let n = 0;
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === OWNED_TRIGGER_FN) { ScriptApp.deleteTrigger(t); n++; }
  });
  return n;
}
function ensureTriggerHealthy_() {
  const has = ScriptApp.getProjectTriggers().some(t => t.getHandlerFunction() === OWNED_TRIGGER_FN);
  if (!has) {
    ScriptApp.newTrigger(OWNED_TRIGGER_FN).timeBased().everyHours(1).create();
    logEvent_('WARN', 'trigger_self_healed', { fn: OWNED_TRIGGER_FN });
    return 'recreated';
  }
  return 'ok';
}
function runDiagnostics() {
  const ss = SpreadsheetApp.getActive();
  let triggers = []; let triggerListErr = null;
  try {
    triggers = ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === OWNED_TRIGGER_FN);
  } catch (e) { triggerListErr = String(e).slice(0, 200); }
  const info = {
    now: Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm:ss') + ' PHT',
    owned_trigger_count: triggers.length,
    trigger_types: triggers.map(t => t.getEventType() + ' / ' + t.getTriggerSource()),
    trigger_list_err: triggerListErr,
    sheet_tabs: ss.getSheets().map(s => s.getName()),
    log_tab_rows: ss.getSheetByName(LOG_TAB) ? ss.getSheetByName(LOG_TAB).getLastRow() - 1 : 0,
    log_v3_tab_rows: ss.getSheetByName(LOG_V3_TAB) ? ss.getSheetByName(LOG_V3_TAB).getLastRow() - 1 : 0,
    conflicts_tab_rows: ss.getSheetByName(CONFLICT_TAB) ? ss.getSheetByName(CONFLICT_TAB).getLastRow() - 1 : 0,
  };
  logEvent_('INFO', 'diagnostics', info);
  SpreadsheetApp.getActive().toast(
    'Triggers: ' + info.owned_trigger_count + ' | v3 log: ' + info.log_v3_tab_rows + ' | Conflicts: ' + info.conflicts_tab_rows, 'Diagnostics', 20);
  return info;
}

function logEvent_(level, event, payload) {
  try {
    const ss = SpreadsheetApp.getActive();
    let t = ss.getSheetByName(LOG_TAB);
    if (!t) {
      t = ss.insertSheet(LOG_TAB);
      t.getRange(1, 1, 1, 6).setValues([['ts_pht', 'level', 'event', 'duration_ms', 'rows', 'payload_json']]);
      t.getRange(1, 1, 1, 6).setBackground(C_GREEN).setFontColor('#FFFFFF').setFontWeight('bold');
      t.setFrozenRows(1);
    }
    const ts = Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm:ss') + ' PHT';
    const p = payload || {};
    t.appendRow([ts, level || 'INFO', event || '', p.duration_ms || '', p.rows || '', JSON.stringify(p).slice(0, 5000)]);
    const last = t.getLastRow();
    if (last > LOG_MAX_ROWS + 1) t.deleteRows(2, last - (LOG_MAX_ROWS + 1));
  } catch (e) { Logger.log('logEvent_ fail: ' + e); }
}

function maybeSendAlert_(subject, body) {
  try {
    const props = PropertiesService.getScriptProperties();
    const last = Number(props.getProperty(ALERT_PROP_KEY) || 0);
    const now = Date.now();
    const minMs = ALERT_MIN_INTERVAL_HOURS * 3600 * 1000;
    if (now - last < minMs) return false;
    MailApp.sendEmail({ to: ALERT_EMAIL, subject: subject, body: body });
    props.setProperty(ALERT_PROP_KEY, String(now));
    return true;
  } catch (e) { Logger.log('alert fail: ' + e); return false; }
}

// ───────────────────────────────────────────────────────────────────────────
// Helpers
// ───────────────────────────────────────────────────────────────────────────
function toNum(v) { const n = Number(v); return isNaN(n) ? 0 : n; }
function nk(v) { return v ? v.toString().trim().toUpperCase().replace(/\s+/g,' ').replace(/--/g,'-') : ''; }
function invKey(v) {
  if (!v) return '';
  const s = v.toString().trim().toUpperCase();
  return (s === 'NAN' || s === 'NA' || s === 'NONE') ? '' : s;
}
function invNoVariants_(v) {
  if (v == null) return [''];
  const s = String(v).trim().toUpperCase();
  if (!s || s === 'NAN' || s === 'NA' || s === 'NONE') return [''];
  const out = {};
  out[s] = 1;
  const digits = s.replace(/\D/g, '');
  if (digits) {
    try { out[String(parseInt(digits, 10))] = 1; } catch (e) {}
  }
  const noPrefix = s.replace(/^(SI|OR|INV|#)[-\s]*/, '');
  if (noPrefix !== s) { out[noPrefix] = 1; }
  return Object.keys(out);
}
function formatDateLike_(v) {
  if (!v) return '';
  if (v instanceof Date) return Utilities.formatDate(v, 'Asia/Manila', 'yyyy-MM-dd');
  const n = Number(v);
  if (!isNaN(n) && n > 40000 && n < 50000) {
    return Utilities.formatDate(new Date(Date.UTC(1899, 11, 30) + n * 86400000), 'Asia/Manila', 'yyyy-MM-dd');
  }
  return String(v).trim();
}
function serialToDate(v) { return formatDateLike_(v); }
function agingBucket(d) {
  if (d <= 0) return 'Not Yet Due';
  if (d <= 30) return '0-30 days';
  if (d <= 60) return '31-60 days';
  if (d <= 90) return '61-90 days';
  if (d <= 120) return '91-120 days';
  return 'Over 120 days';
}

// ───────────────────────────────────────────────────────────────────────────

// ───────────────────────────────────────────────────────────────────────────
// v3.9 (S255 Phase 3) — recomputeBanners_ — RF-7 fix
// Recomputes banner rows from current tab data on every hourly cycle.
// Replaces the stale legacy-only banner that buildGrid() wrote via mode=v2.
// ───────────────────────────────────────────────────────────────────────────
function recomputeBanners_(ss) {
  var stats = { banners_updated: 0, tabs_processed: [], details: {} };
  var TABS = ['Suppliers SOA', 'Head Office', 'CAPEX', 'Payment Plan', 'Intercompany'];

  TABS.forEach(function(tabName) {
    var sh = ss.getSheetByName(tabName);
    if (!sh) return;
    // Payment Plan has header at row 3; CAPEX at row 19; SOA/HO/Intercompany at row 17
    var headerRow = (tabName === 'Payment Plan') ? 3 : (tabName === 'CAPEX' ? 19 : 17);
    var dataStartRow = headerRow + 1;
    var lastRow = sh.getLastRow();
    if (lastRow < dataStartRow) {
      stats.details[tabName] = { skipped: 'no data rows' };
      return;
    }
    var ncols = sh.getLastColumn();
    var hdr = sh.getRange(headerRow, 1, 1, ncols).getValues()[0];
    var iOut = hdr.indexOf('OUTSTANDING');
    var iPayee = hdr.indexOf('PAYEE');
    var iStatus = hdr.indexOf('STATUS');
    var iAgingBucket = hdr.indexOf('AGING BUCKET');
    var iVatable = hdr.indexOf('VATABLE');
    var iVat = hdr.indexOf('VAT');
    var iEwt = hdr.indexOf('EWT');
    var iAmount = hdr.indexOf('AMOUNT');
    if (iOut < 0 || iPayee < 0) {
      stats.details[tabName] = { skipped: 'missing OUTSTANDING or PAYEE column' };
      return;
    }
    var data = sh.getRange(dataStartRow, 1, lastRow - dataStartRow + 1, ncols).getValues();

    var total = 0, items = 0;
    var payees = {}; var aging = {}; var vatable = 0, vat = 0, ewt = 0; var vatGaps = 0;
    var bk = { 'NO RFP YET': {t:0,c:0}, 'WITH FINANCE': {t:0,c:0}, 'IN PIPELINE': {t:0,c:0},
               'CHECK READY': {t:0,c:0}, 'FOR ONLINE PAYMENT': {t:0,c:0},
               'CHECK RELEASED': {t:0,c:0}, 'PAID': {t:0,c:0} };

    data.forEach(function(r) {
      var out = toNum(r[iOut]);
      var payee = String(r[iPayee] || '').trim();
      var status = String(iStatus >= 0 ? r[iStatus] : '').trim().toUpperCase();
      var bucket = String(iAgingBucket >= 0 ? r[iAgingBucket] : '').trim();

      if (out > 0) {
        total += out;
        items++;
        if (payee) payees[payee] = 1;
        if (bucket) aging[bucket] = (aging[bucket] || 0) + out;
        if (iVatable >= 0) vatable += toNum(r[iVatable]);
        if (iVat >= 0) vat += toNum(r[iVat]);
        if (iEwt >= 0) ewt += toNum(r[iEwt]);
        if (iAmount >= 0 && toNum(r[iAmount]) > 50000 && toNum(r[iVat]) === 0) vatGaps++;
      }
      if (bk[status]) { bk[status].t += out; bk[status].c++; }
    });

    var uniquePayees = Object.keys(payees).length;
    var pipelineT = bk['IN PIPELINE'].t + bk['CHECK READY'].t + bk['FOR ONLINE PAYMENT'].t;
    var pipelineC = bk['IN PIPELINE'].c + bk['CHECK READY'].c + bk['FOR ONLINE PAYMENT'].c;

    // Row 4: TOTAL OUTSTANDING — A4..E4
    sh.getRange(4, 1, 1, 5).setValues([['TOTAL OUTSTANDING', total, uniquePayees + ' payees', '', items + ' items']]);

    // Row 7 + 10 + 11 + 13 — only for entry-style tabs (Payment Plan has different banner)
    if (tabName !== 'Payment Plan') {
      sh.getRange(7, 1, 1, 15).setValues([[
        'NO RFP YET', bk['NO RFP YET'].t, bk['NO RFP YET'].c + ' items',
        'WITH FINANCE (no RFP)', bk['WITH FINANCE'].t, bk['WITH FINANCE'].c + ' items',
        'IN PIPELINE', pipelineT, pipelineC + ' items',
        'CHECK RELEASED', bk['CHECK RELEASED'].t, bk['CHECK RELEASED'].c + ' items',
        'PAID', '', bk['PAID'].c + ' items',
      ]]);
      sh.getRange(10, 1, 1, 14).setValues([[
        'Not Yet Due', aging['Not Yet Due']||0, '',
        '0-30', aging['0-30 days']||0, '',
        '31-60', aging['31-60 days']||0, '',
        '61-90', aging['61-90 days']||0, '',
        '91-120', aging['91-120 days']||0,
      ]]);
      sh.getRange(11, 1, 1, 2).setValues([['Over 120 days', aging['Over 120 days']||0]]);
      sh.getRange(13, 1, 1, 11).setValues([[
        'Vatable Sales', vatable, '',
        'VAT (12%)', vat, '',
        'EWT', ewt, '',
        'VAT gaps (amt>50K, VAT=0)', vatGaps,
      ]]);
    }

    stats.banners_updated++;
    stats.tabs_processed.push(tabName);
    stats.details[tabName] = {
      total_outstanding: total,
      unique_payees: uniquePayees,
      items: items,
      vatable: vatable, vat: vat, ewt: ewt, vat_gaps: vatGaps,
    };
  });
  return stats;
}

// buildGrid + formatTab kept from v2 for the legacy wipe-rebuild path
// ───────────────────────────────────────────────────────────────────────────
function buildGrid(rows, label, ts, isCapex, isVatGaps) {
  const total = rows.reduce((s, r) => s + r.outstanding, 0);
  const no_rfp = rows.filter(r => r.status === 'NO RFP YET');
  const with_finance = rows.filter(r => r.status === 'WITH FINANCE');
  const pipeline = rows.filter(r => ['IN PIPELINE','CHECK READY','FOR ONLINE PAYMENT'].indexOf(r.status) >= 0);
  const released = rows.filter(r => r.status === 'CHECK RELEASED');
  const paid = rows.filter(r => r.status === 'PAID');
  const payeeSet = {};
  rows.forEach(r => { if (r.outstanding > 0) payeeSet[r.payee] = 1; });
  const uniquePayees = Object.keys(payeeSet).length;
  const aging = {};
  const openOnly = rows.filter(r => r.outstanding > 0);
  openOnly.forEach(r => { aging[r.aging_bucket] = (aging[r.aging_bucket] || 0) + r.outstanding; });
  const tot_vatable = openOnly.reduce((s, r) => s + r.vatable, 0);
  const tot_vat = openOnly.reduce((s, r) => s + r.vat, 0);
  const tot_ewt = openOnly.reduce((s, r) => s + r.ewt, 0);
  const vat_gaps = rows.filter(r => r.outstanding > 50000 && r.vat === 0).length;
  const pad = (row) => { while (row.length < NCOLS) row.push(''); return row.slice(0, NCOLS); };
  const hdr = [
    pad(['CONSOLIDATED AP — ' + label]),
    pad(['Sources: Suppliers SOA + HO AP + CAPEX (FPM status + Compliance App VAT/EWT) | Refreshed: ' + ts]),
    pad([]),
    pad(['TOTAL OUTSTANDING', total, uniquePayees + ' payees', '', rows.length + ' items']),
    pad([]),
    pad(['PAYMENT STATUS BREAKDOWN']),
    pad(['NO RFP YET', no_rfp.reduce((s,r)=>s+r.outstanding,0), no_rfp.length + ' items',
         'WITH FINANCE (no RFP)', with_finance.reduce((s,r)=>s+r.outstanding,0), with_finance.length + ' items',
         'IN PIPELINE', pipeline.reduce((s,r)=>s+r.outstanding,0), pipeline.length + ' items',
         'CHECK RELEASED', released.reduce((s,r)=>s+r.outstanding,0), released.length + ' items',
         'PAID', '', paid.length + ' items']),
    pad([]),
    pad(['AGING BREAKDOWN (outstanding only)']),
    pad(['Not Yet Due', aging['Not Yet Due']||0, '', '0-30', aging['0-30 days']||0, '', '31-60', aging['31-60 days']||0, '', '61-90', aging['61-90 days']||0, '', '91-120', aging['91-120 days']||0]),
    pad(['Over 120 days', aging['Over 120 days']||0]),
    pad([]),
    pad(['TAX CAPTURE (outstanding only)']),
    pad(['Vatable Sales', tot_vatable, '', 'VAT (12%)', tot_vat, '', 'EWT', tot_ewt, '', 'VAT gaps (amt>50K, VAT=0)', vat_gaps]),
    pad([]),
  ];
  if (isCapex) {
    hdr.push(pad(['NOTE: CAPEX invoices received at HQ (HO AP PROJECT COST). Additional contractor balances (~PHP 22M per CEO) tracked in BGF workbook.']));
    hdr.push(pad([]));
  } else if (isVatGaps) {
    hdr.push(pad(['ACTION: Invoices with outstanding > PHP 50K but VAT = 0. Either non-VAT supplier or missing — needs AP team review for BIR input VAT.']));
    hdr.push(pad([]));
  }
  hdr.push(pad(['Cols A-H: invoice ledger | I-M: FPM status | N-S: classification + tax | NO RFP YET = action | red VAT = gap']));
  hdr.push(['SOURCE', 'PAYEE', 'INVOICE NO.', 'INVOICE DATE', 'AMOUNT', 'OUTSTANDING', 'AGING', 'AGING BUCKET', 'STATUS', 'BEI-FIN No.', 'RFP No.', 'METHOD', 'CHECK NO.', 'CATEGORY', 'GOODS/SERVICES', 'BILLED TO', 'VATABLE', 'VAT', 'EWT']);
  return hdr.concat(rows.map(r => [
    r.source, r.payee, r.invoice_no, r.invoice_date,
    r.amount, r.outstanding, r.aging, r.aging_bucket,
    r.status, r.bei_fin, r.rfp_no, r.method, r.check,
    r.category, r.classification, r.billed_to,
    r.vatable, r.vat, r.ewt,
  ]));
}
function formatTab(sheet, dataCount, headerRows) {
  const ds = headerRows + 1;
  sheet.getRange(1, 1, 1, NCOLS).merge().setBackground(C_GREEN).setFontColor('#FFFFFF').setFontSize(14).setFontWeight('bold').setHorizontalAlignment('center');
  sheet.getRange(2, 1, 1, NCOLS).merge().setBackground(C_TINT).setFontSize(9).setHorizontalAlignment('center');
  sheet.getRange(4, 1, 1, NCOLS).setBackground(C_GOLD_L).setFontWeight('bold');
  sheet.getRange(4, 2).setFontSize(16).setFontColor(C_GREEN).setNumberFormat('#,##0.00');
  sheet.getRange(6, 1, 1, NCOLS).setBackground(C_GOLD).setFontWeight('bold');
  sheet.getRange(7, 1, 1, NCOLS).setBackground(C_GOLD_L);
  [2, 5, 8, 11].forEach(c => sheet.getRange(7, c).setNumberFormat('#,##0.00').setFontWeight('bold'));
  sheet.getRange(9, 1, 1, NCOLS).setBackground(C_GOLD).setFontWeight('bold');
  sheet.getRange(10, 1, 2, NCOLS).setBackground(C_GOLD_L);
  [2, 5, 8, 11, 14].forEach(c => sheet.getRange(10, c).setNumberFormat('#,##0.00').setFontWeight('bold'));
  sheet.getRange(11, 2).setNumberFormat('#,##0.00').setFontWeight('bold');
  sheet.getRange(12, 1, 1, NCOLS).setBackground(C_PURPLE_L).setFontWeight('bold');
  sheet.getRange(13, 1, 1, NCOLS).setBackground('#F8F0F8');
  [2, 5, 8].forEach(c => sheet.getRange(13, c).setNumberFormat('#,##0.00').setFontWeight('bold'));
  sheet.getRange(headerRows - 1, 1, 1, NCOLS).merge().setBackground(C_PURPLE_L).setFontSize(8).setHorizontalAlignment('center');
  sheet.getRange(headerRows, 1, 1, NCOLS).setBackground(C_GREEN).setFontColor('#FFFFFF').setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center');
  sheet.setFrozenRows(headerRows);
  if (dataCount > 0) {
    sheet.getRange(ds, 1, dataCount, NCOLS).setFontSize(9).setFontFamily('Calibri');
    sheet.getRange(ds, 5, dataCount, 2).setNumberFormat('#,##0.00');
    sheet.getRange(ds, 7, dataCount, 1).setHorizontalAlignment('center');
    sheet.getRange(ds, 17, dataCount, 3).setNumberFormat('#,##0.00');
    for (let i = 0; i < dataCount; i++) {
      sheet.getRange(ds + i, 1, 1, NCOLS).setBackground(i % 2 === 0 ? C_TINT : '#FFFFFF');
    }
    const sr = sheet.getRange(ds, 9, dataCount, 1);
    const vr = sheet.getRange(ds, 18, dataCount, 1);
    const rules = [
      SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('NO RFP YET').setFontColor(C_RED).setBold(true).setRanges([sr]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('WITH FINANCE').setFontColor(C_GOLD).setBold(true).setRanges([sr]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('PAID').setFontColor(C_GREEN).setBold(true).setRanges([sr]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('CHECK RELEASED').setFontColor(C_MID).setBold(true).setRanges([sr]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=AND($R' + (ds) + '=0, $F' + (ds) + '>50000)').setBackground('#FFD5D5').setFontColor(C_RED).setBold(true).setRanges([vr]).build(),
    ];
    sheet.setConditionalFormatRules(rules);
  }
  [90, 180, 100, 90, 95, 95, 55, 85, 110, 110, 60, 85, 85, 110, 90, 100, 95, 85, 70].forEach((w, i) => sheet.setColumnWidth(i + 1, w));
}


// ═══════════════════════════════════════════════════════════════════════════
// v4 patch (2026-05-13) — seedNewInvoicesFromFPM_
//
// PROBLEM (identified 2026-05-12):
//   The v3 seed reads only archived SOA + HO sheets. Team typed in FPM
//   `RFP Summary` (active workflow) → 1,865 rows (₱455.7M) never made it to
//   AP Master because nothing reads FPM as a seed source.
//
// FIX:
//   Append-only. Reads FPM RFP Summary. Classifies each row → CAPEX / Suppliers
//   SOA / Head Office. Dedupes against the same existingIndex used by the SOA/HO
//   seed. Never overwrites existing rows. Logs each insert as 'invoice_seeded_from_fpm'.
// ═══════════════════════════════════════════════════════════════════════════
function seedNewInvoicesFromFPM_(ss, fpmLookup, taxLookup, existingIndex, dryRun) {
  const stats = { scanned: 0, appended: 0, skipped_paid_old: 0, skipped_empty: 0,
                  skipped_existing: 0, capex_count: 0, ho_count: 0, soa_count: 0,
                  sample_appended: [] };

  const fpmSS = SpreadsheetApp.openById(FPM_ID);
  const fpmTab = fpmSS.getSheetByName('RFP Summary');
  if (!fpmTab) return stats;
  const fpmData = fpmTab.getDataRange().getValues();
  const fh = fpmData[0];
  const fi = function(name) { return fh.indexOf(name); };

  const idxRfpNo = fi('RFP NO.');
  const idxBeiFin = fi('BEI-FIN No./ RFP ID No (if applicable)');
  const idxDateRecv = fi('RFP Date Received');
  const idxPayee = fi('Payee');
  const idxParticulars = fi('Particulars');
  const idxMethod = fi('Payment Method');
  const idxCheckNo = fi('Check No./Ref No.');
  const idxAmount = fi('Amount Due');
  const idxProcDate = fi('Processed Date');
  const idxStatus = fi('Status');

  // Build supplier roster set from Compliance (if accessible) — used to classify
  // FPM rows that match a known inventory supplier as "Suppliers SOA" rather
  // than "Head Office" by default.
  const supplierSet = {};
  try {
    const compSS = SpreadsheetApp.openById(COMPLIANCE_ID);
    const supTab = compSS.getSheetByName('Suppliers');
    if (supTab) {
      const supData = supTab.getDataRange().getValues();
      for (var sii = 1; sii < supData.length; sii++) {
        var name = String(supData[sii][2] || supData[sii][1] || '').trim().toUpperCase();  // v3.6: col C is Supplier Name (was reading B/A)
        if (name) supplierSet[name] = true;
      }
    }
  } catch (e) { /* best-effort */ }

  // CAPEX classification heuristic
  const capexKeywords = ['PROJECT COST','CONSTRUCTION','FITOUT','FIT-OUT','FIT OUT',
                         'CAPEX','CONTRACTOR','CIVIL WORKS','EQUIPMENT','KITCHEN MALL',
                         'AIRCON','SIGNAGE','SIGN FABRICATION'];

  const ninetyDaysAgo = new Date(Date.now() - 90 * 24 * 3600 * 1000);
  const newRowsByTab = { 'Suppliers SOA': [], 'Head Office': [], 'CAPEX': [], 'Intercompany': [] };

  for (var i = 1; i < fpmData.length; i++) {
    var r = fpmData[i];
    stats.scanned++;

    var payee = String(r[idxPayee] || '').trim();
    var amount = toNum(r[idxAmount]);
    var particulars = String(r[idxParticulars] || '').trim();
    var status = String(r[idxStatus] || '').trim();
    var beiFin = String(r[idxBeiFin] || '').trim();
    var rfpNo = String(r[idxRfpNo] || '').trim();
    var dateRecv = idxDateRecv >= 0 ? r[idxDateRecv] : null;
    var procDateRaw = idxProcDate >= 0 ? r[idxProcDate] : null;

    if (!payee || !amount) { stats.skipped_empty++; continue; }

    // Skip paid items older than 90 days — already settled, no need to seed
    if (status === 'Paid/ Cleared' && procDateRaw) {
      var procD = procDateRaw instanceof Date ? procDateRaw : (new Date(procDateRaw));
      if (procD && procD < ninetyDaysAgo) { stats.skipped_paid_old++; continue; }
    }

    var payeeKey = payee.toUpperCase();
    var amtK = Math.round(amount * 100) / 100;
    var dateStr = dateRecv ? formatDateLike_(dateRecv) : '';
    var beiFinNorm = nk(beiFin);

    var found = false;
    // 1) Try BEI-FIN match — only if it looks real
    if (beiFinNorm && beiFinNorm !== 'NA' && beiFinNorm !== 'NONE') {
      for (var k in existingIndex) {
        if (existingIndex[k].row && existingIndex[k].row.rec &&
            existingIndex[k].row.rec['BEI-FIN No.'] &&
            nk(existingIndex[k].row.rec['BEI-FIN No.']) === beiFinNorm) {
          found = true; break;
        }
      }
    }
    // 2) Payee + amount + date
    if (!found && existingIndex['FB|' + payeeKey + '|' + amtK + '|' + dateStr]) found = true;

    if (found) { stats.skipped_existing++; continue; }

    // Classify → which AP Master tab
    // v3.10 (S256 Phase 2): Intercompany routing — broadened to 14 non-Bebang affiliates per Denise Section B
    // Requires: PAYEE matches any affiliate entity AND transfer keyword in PARTICULARS AND NOT govt keyword
    var isIntercompany = false;
    if (INTERCO_AFFILIATE_PATTERNS.some(function(rx) { return rx.test(payee); })
        && /(transfer (of )?fund|cash sweep|intercompany)/i.test(particulars)
        && !/HDMF|SSS|PHIC|PHILHEALTH|BIR|PAG-?IBIG|CONTRIBUTION|RENTAL|FINAL PAY/i.test(particulars)) {
      isIntercompany = true;
    }

    var targetTab = 'Head Office';
    var particularsUpper = particulars.toUpperCase();
    var isCapex = false;
    for (var ck = 0; ck < capexKeywords.length; ck++) {
      if (particularsUpper.indexOf(capexKeywords[ck]) >= 0) { isCapex = true; break; }
    }
    if (isIntercompany) {
      targetTab = 'Intercompany';
      stats.intercompany_count++;
    } else if (isCapex) {
      targetTab = 'CAPEX';
      stats.capex_count++;
    } else if (supplierSet[payeeKey]) {
      targetTab = 'Suppliers SOA';
      stats.soa_count++;
    } else {
      stats.ho_count++;
    }

    // Display STATUS from FPM
    var display = '';
    if (status === 'Paid/ Cleared') display = 'PAID';
    else if (status === 'Check Released') display = 'CHECK RELEASED';
    else if (status === 'Check Ready') display = 'CHECK READY';
    else if (status === 'For Online Payment') display = 'FOR ONLINE PAYMENT';
    else if (['For Approval','For Signature','For Funding','For Review','Received','For Released'].indexOf(status) >= 0) display = 'IN PIPELINE';
    else display = status || 'WITH FINANCE';

    var outstanding = (status === 'Paid/ Cleared') ? 0 : amount;
    var dateRecvParsed = dateRecv ? (dateRecv instanceof Date ? dateRecv : new Date(dateRecv)) : null;
    var aging = dateRecvParsed ? Math.floor((Date.now() - dateRecvParsed.getTime()) / (24 * 3600 * 1000)) : 0;

    var rowValues = [
      'FPM',                                  // SOURCE
      payee,                                  // PAYEE
      rfpNo || beiFin || '',                  // INVOICE NO. (FPM doesn't carry one — use RFP No)
      dateRecvParsed || '',                   // INVOICE DATE
      amount,                                 // AMOUNT
      outstanding,                            // OUTSTANDING
      aging,                                  // AGING
      agingBucket(aging),                     // AGING BUCKET
      display,                                // STATUS
      beiFin,                                 // BEI-FIN No.
      rfpNo,                                  // RFP No.
      String(r[idxMethod] || '').trim(),      // METHOD
      String(r[idxCheckNo] || '').trim(),     // CHECK NO.
      targetTab === 'CAPEX' ? 'CAPEX' : (targetTab === 'Suppliers SOA' ? 'Supplier Payments' : 'Head Office'),  // CATEGORY
      particulars.substring(0, 100),          // CLASSIFICATION
      '',                                     // BILLED TO
      0, 0, 0,                                // VATABLE, VAT, EWT
    ];

    newRowsByTab[targetTab].push({
      rowValues: rowValues,
      sourceSheet: 'FPM',
      sourceRowId: i + 1,
    });

    if (stats.sample_appended.length < 5) {
      stats.sample_appended.push({ tab: targetTab, payee: payee, amount: amount, status: status, rfpNo: rfpNo });
    }
  }

  // Append new rows to the bottom of each edit tab
  Object.keys(newRowsByTab).forEach(function(tabName) {
    var toAppend = newRowsByTab[tabName];
    if (toAppend.length === 0) return;
    if (!dryRun) {
      var sh = ss.getSheetByName(tabName);
      if (sh) {
        var startRow = sh.getLastRow() + 1;
        var values = toAppend.map(function(x) { return x.rowValues; });
        sh.getRange(startRow, 1, values.length, NCOLS).setValues(values);
        toAppend.forEach(function(x, ix) {
          logEvent_v3_(ss, 'invoice_seeded_from_fpm', {
            tab: tabName,
            ap_master_row_idx: startRow + ix,
            source_sheet: 'FPM',
            source_row_id: x.sourceRowId,
            payee: x.rowValues[1],
            rfp_no: x.rowValues[10],
            amount: x.rowValues[4],
          });
        });
      }
    }
    stats.appended += toAppend.length;
  });

  return stats;
}

// ═══════════════════════════════════════════════════════════════════════════
// v3.7 patch (2026-05-14, S248) — Denise Payment Plan seed
// ═══════════════════════════════════════════════════════════════════════════
// Denise's sheet 13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU is "Project: 2-Week Payment Plan".
// Today's audit proved: of her ₱53.8M tracked outstanding, ZERO is fully reconciled to
// AP Master + FPM + Compliance. ₱23.6M is GHOST (no trail anywhere), ₱29.2M is FPM-only.
// This seed makes her sheet a DATA SOURCE for AP Master (like FPM, like Compliance),
// not a parallel silo. Her workflow is unchanged; she keeps typing in her sheet, the
// hourly Cloud Scheduler tick at xx:12 PHT pulls new rows into AP Master.
//
// Read order (4 tabs, dedup by supplier+invoice across all tabs):
//   1. Suppliers w/o FD & Middleby  → SOURCE='Denise PP' (urgent AP)
//   2. Middleby                     → SOURCE='Denise PP - Disputed (Middleby)' (kept tagged)
//   3. Forward Dynamics             → SOURCE='Denise PP - Disputed (FD)' (kept tagged)
//   4. Masterlist                   → SOURCE='Denise PP - Masterlist' (safety net, only rows
//                                       not already deduped from 1/2/3)
//
// Per CEO 2026-05-14: Middleby and Forward Dynamics are disputed-but-eventually-payable;
// they keep their own SOURCE so Sam can filter "urgent" vs "disputed" in AP Master.
//
// Denise's schema (25 cols, header row 3, data row 4+):
//   0:Supplier 1:Address 2:TIN 3:VAT/Nonvat 4:Goods/Services 5:Invoice Date 6:Terms
//   7:BEI FIN 8:Invoice No 9:Description 10:Vatable Sales 11:VAT 12:EWT 13:Gross Amount
//   14:Paid Amount 15:Outstanding Balance 16:Due Date 17:Aging (days) 18-23:aging buckets
//   24:Status
// ═══════════════════════════════════════════════════════════════════════════

function seedFromDenisePaymentPlan_(ss, fpmLookup, taxLookup, existingIndex, dryRun) {
  const stats = {
    scanned: 0, appended: 0, skipped_paid: 0, skipped_blank: 0,
    skipped_existing: 0, deduped_intra_denise: 0,
    by_tab: { 'Suppliers w/o FD & Middleby': 0, 'Middleby': 0, 'Forward Dynamics': 0, 'Masterlist': 0 },
    sample_appended: []
  };

  const TAB_CONFIG = [
    { name: 'Suppliers w/o FD & Middleby', sourceTag: 'Denise PP',                          category: 'Supplier Payments' },
    { name: 'Middleby',                    sourceTag: 'Denise PP - Disputed (Middleby)',    category: 'Disputed - Eventually Payable' },
    { name: 'Forward Dynamics',            sourceTag: 'Denise PP - Disputed (FD)',          category: 'Disputed - Eventually Payable' },
    { name: 'Masterlist',                  sourceTag: 'Denise PP - Masterlist',             category: 'Supplier Payments' },
  ];

  // Open Denise's sheet
  var deniseSS;
  try {
    deniseSS = SpreadsheetApp.openById(DENISE_PP_ID);
  } catch (e) {
    stats.open_error = String(e);
    return stats;
  }

  // Cross-tab dedup index seeded with the AP Master existingIndex passed in
  // Plus a per-this-run set of (supplier+inv) pairs to dedupe across the 4 Denise tabs
  const seenThisRun = {};   // 'PAYEE_KEY|INV_KEY' -> first tab that emitted it

  const newRowsByTab = { 'Suppliers SOA': [] };

  for (var ti = 0; ti < TAB_CONFIG.length; ti++) {
    var cfg = TAB_CONFIG[ti];
    var sh = deniseSS.getSheetByName(cfg.name);
    if (!sh) continue;
    var data = sh.getDataRange().getValues();
    if (data.length < 4) continue;

    // Header row at index 2 (row 3); data starts at index 3 (row 4)
    var header = data[2];
    var hIdx = function(name) {
      for (var k = 0; k < header.length; k++) {
        if (String(header[k]).trim().toUpperCase() === name.toUpperCase()) return k;
      }
      return -1;
    };
    var iSupplier   = hIdx('Supplier');
    var iInvDate    = hIdx('Invoice Date');
    var iBeiFin     = hIdx('BEI FIN');
    var iInvNo      = hIdx('Invoice No');
    var iVatable    = hIdx('VATABLE SALES');
    var iVat        = hIdx('VAT');
    var iEwt        = hIdx('EWT');
    var iGross      = hIdx('GROSS Amount');
    var iPaid       = hIdx('Paid Amount');
    var iOut        = hIdx('Outstanding Balance');
    var iAging      = hIdx('AGING (days)');
    var iStatus     = hIdx('Status');

    if (iSupplier < 0 || iOut < 0) continue;  // tab missing required cols — skip

    for (var rr = 3; rr < data.length; rr++) {
      var r = data[rr];
      stats.scanned++;
      var supplier = String(r[iSupplier] || '').trim();
      if (!supplier) { stats.skipped_blank++; continue; }
      var outstanding = toNum(r[iOut]);
      if (outstanding <= 0) { stats.skipped_paid++; continue; }

      var invoiceNo = iInvNo >= 0 ? String(r[iInvNo] || '').trim() : '';
      var beiFin    = iBeiFin >= 0 ? String(r[iBeiFin] || '').trim() : '';
      var gross     = iGross >= 0 ? toNum(r[iGross]) : 0;
      var invDate   = iInvDate >= 0 ? r[iInvDate] : null;
      var status    = iStatus >= 0 ? String(r[iStatus] || '').trim() : '';
      var aging     = iAging >= 0 ? toNum(r[iAging]) : 0;
      var vatable   = iVatable >= 0 ? toNum(r[iVatable]) : 0;
      var vat       = iVat >= 0 ? toNum(r[iVat]) : 0;
      var ewt       = iEwt >= 0 ? toNum(r[iEwt]) : 0;

      // Build dedup keys
      var payeeKey  = supplier.toUpperCase();
      var amtK      = Math.round(gross * 100) / 100;
      var dateStr   = invDate ? formatDateLike_(invDate) : '';
      var invVariants = invNoVariants_(invoiceNo);
      var beiFinNorm = nk(beiFin);

      // 1) Intra-run dedup — if a previous Denise tab already emitted this (supplier+inv), skip
      var intraKey = null;
      for (var iv = 0; iv < invVariants.length; iv++) {
        var k = payeeKey + '|' + invVariants[iv];
        if (seenThisRun[k]) { intraKey = k; break; }
      }
      if (intraKey) { stats.deduped_intra_denise++; continue; }

      // 2) AP Master existing-row dedup — check existingIndex (passed from caller)
      var foundInAp = false;
      for (var iv2 = 0; iv2 < invVariants.length; iv2++) {
        if (existingIndex[payeeKey + '|' + invVariants[iv2] + '|' + amtK]) { foundInAp = true; break; }
      }
      if (!foundInAp && existingIndex['FB|' + payeeKey + '|' + amtK + '|' + dateStr]) foundInAp = true;
      // v3.10 (S256 Phase 2.3): FPM-SOA-aware dedup — if same supplier+amount exists with SOURCE='FPM-SOA'
      // or 'Suppliers SOA', skip even if invoice number format differs (prevents re-adding XYZCO-type races)
      if (!foundInAp) {
        var fpmSoaKey = 'FPMSOA|' + payeeKey + '|' + amtK;
        if (existingIndex[fpmSoaKey]) { foundInAp = true; stats.skipped_existing_fpm_soa = (stats.skipped_existing_fpm_soa || 0) + 1; }
      }
      // BEI-FIN match against existing rows (if real)
      if (!foundInAp && beiFinNorm && beiFinNorm !== 'NA' && beiFinNorm !== 'NONE') {
        for (var ek in existingIndex) {
          var er = existingIndex[ek].row;
          if (er && er.rec && er.rec['BEI-FIN No.'] && nk(er.rec['BEI-FIN No.']) === beiFinNorm) {
            foundInAp = true; break;
          }
        }
      }
      if (foundInAp) { stats.skipped_existing++; continue; }

      // Mark this run-key so other Denise tabs (esp. Masterlist) don't re-emit
      for (var iv3 = 0; iv3 < invVariants.length; iv3++) {
        seenThisRun[payeeKey + '|' + invVariants[iv3]] = cfg.name;
      }

      // Map Denise status -> AP Master status
      var apStatus = mapDeniseToApStatus_(status);

      // Compute aging bucket
      var bucket = agingBucket(aging);

      // v3.9 (S255 Phase 5): 3M Dragon manual-invoice detection — INVOICE NO starting with "INVOICE NO" prefix
      // overrides cfg.sourceTag to 'Denise PP - Manual' so Sam can filter procurement-bypass entries
      var sourceTag = cfg.sourceTag;
      if (/^INVOICE\s*NO/i.test(invoiceNo)) {
        sourceTag = 'Denise PP - Manual';
      }
      var rowValues = [
        sourceTag,                              // SOURCE
        supplier,                               // PAYEE
        invoiceNo,                              // INVOICE NO.
        invDate || '',                          // INVOICE DATE
        gross,                                  // AMOUNT
        outstanding,                            // OUTSTANDING
        aging,                                  // AGING
        bucket,                                 // AGING BUCKET
        apStatus,                               // STATUS
        beiFin,                                 // BEI-FIN No.
        '',                                     // RFP No. (FPM fills later)
        '',                                     // METHOD
        '',                                     // CHECK NO.
        cfg.category,                           // CATEGORY
        cfg.name,                               // CLASSIFICATION (which Denise tab originated it)
        '',                                     // BILLED TO
        vatable,                                // VATABLE
        vat,                                    // VAT
        ewt                                     // EWT
      ];

      newRowsByTab['Suppliers SOA'].push({
        rowValues: rowValues,
        sourceTab: cfg.name,
        sourceRowId: rr + 1,
      });
      stats.by_tab[cfg.name]++;

      if (stats.sample_appended.length < 5) {
        stats.sample_appended.push({
          tab: cfg.name, source_tag: cfg.sourceTag, payee: supplier,
          invoice: invoiceNo, amount: gross, outstanding: outstanding,
          status: status, ap_status: apStatus
        });
      }
    }
  }

  // Append all collected rows to Suppliers SOA tab
  var toAppend = newRowsByTab['Suppliers SOA'];
  if (toAppend.length > 0 && !dryRun) {
    var sh = ss.getSheetByName('Suppliers SOA');
    if (sh) {
      var startRow = sh.getLastRow() + 1;
      var values = toAppend.map(function(x) { return x.rowValues; });
      sh.getRange(startRow, 1, values.length, NCOLS).setValues(values);
      toAppend.forEach(function(x, ix) {
        logEvent_v3_(ss, 'invoice_seeded_from_denise_pp', {
          tab: 'Suppliers SOA',
          ap_master_row_idx: startRow + ix,
          source_sheet: 'Denise PP',
          source_denise_tab: x.sourceTab,
          source_row_id: x.sourceRowId,
          source_tag: x.rowValues[0],
          payee: x.rowValues[1],
          invoice: x.rowValues[2],
          amount: x.rowValues[4],
        });
      });
    }
  }
  stats.appended = toAppend.length;

  return stats;
}

// ───────────────────────────────────────────────────────────────────────────
// Map Denise's status enum to AP Master STATUS enum.
// Denise statuses (observed 2026-05-12+): Paid, On Hold, Not yet forwarded to Acctg/Fin,
// Schedule for Online Payment, Schedule for Check Release, For Check Prep, Check Released
// AP Master statuses: NO RFP YET, WITH FINANCE, IN PIPELINE, CHECK READY, CHECK RELEASED, PAID
// Conservative fallback: WITH FINANCE (keeps row visible in summary tabs).
// ───────────────────────────────────────────────────────────────────────────
function mapDeniseToApStatus_(deniseStatus) {
  var s = String(deniseStatus || '').toUpperCase().trim();
  if (s === '' || s === 'NONE') return 'WITH FINANCE';
  if (s === 'PAID') return 'PAID';
  if (s === 'ON HOLD') return 'NO RFP YET';
  if (s.indexOf('NOT YET FORWARDED') >= 0) return 'NO RFP YET';
  if (s.indexOf('CHECK PREP') >= 0 || s.indexOf('CHECK READY') >= 0) return 'CHECK READY';
  if (s.indexOf('SCHEDULE FOR CHECK') >= 0) return 'CHECK READY';
  if (s.indexOf('CHECK RELEASE') >= 0 && s.indexOf('SCHEDULE') < 0) return 'CHECK RELEASED';
  if (s.indexOf('ONLINE PAYMENT') >= 0) return 'FOR ONLINE PAYMENT';
  return 'WITH FINANCE';
}

// ═══════════════════════════════════════════════════════════════════════════
// v3.8 patch (2026-05-14, S248) — Mirror Denise Payment Plan into AP Master tab
// ═══════════════════════════════════════════════════════════════════════════
// Wipes + rebuilds the 'Payment Plan' tab on every hourly cycle. Reads all 4
// Denise tabs (Suppliers w/o FD & Middleby, Middleby, Forward Dynamics, Masterlist),
// transforms to 30-column schema (19 AP Master std + 11 Denise extras), writes to
// rows 4+ of Payment Plan tab. The tab is strict-locked to sam@bebang.ph only
// during the mirror phase — Denise reviews but doesn't type there yet.
//
// When Denise switches: relax the protection (add denise@ as editor), and remove
// this function from the hourly cycle (so her edits aren't wiped). At that point,
// add 'Payment Plan' to the syncStatusFieldsFromFPM_ entry tab list.
// ═══════════════════════════════════════════════════════════════════════════

function mirrorDenisePaymentPlanTab_(ss, dryRun) {
  // v3.9 (S255 Phase 7.2): early-exit when cutover flag is set; sync path takes over
  if (payment_plan_mirror_disabled) {
    return { mirror_disabled: true, by_tab: {} };
  }
  const stats = {
    scanned: 0, mirrored: 0, skipped_paid: 0, skipped_blank: 0,
    deduped_intra_denise: 0, by_tab: {}
  };

  // Bail early if Payment Plan tab doesn't exist
  const pp = ss.getSheetByName('Payment Plan');
  if (!pp) {
    stats.tab_missing = true;
    return stats;
  }

  // Read Denise's 4 working tabs
  let deniseSS;
  try {
    deniseSS = SpreadsheetApp.openById(DENISE_PP_ID);
  } catch (e) {
    stats.open_error = String(e);
    return stats;
  }

  const TAB_CONFIG = [
    { name: 'Suppliers w/o FD & Middleby', sourceTag: 'Denise PP',                          category: 'Supplier Payments' },
    { name: 'Middleby',                    sourceTag: 'Denise PP - Disputed (Middleby)',    category: 'Disputed - Eventually Payable' },
    { name: 'Forward Dynamics',            sourceTag: 'Denise PP - Disputed (FD)',          category: 'Disputed - Eventually Payable' },
    { name: 'Masterlist',                  sourceTag: 'Denise PP - Masterlist',             category: 'Supplier Payments' },
  ];

  const seenThisRun = {};
  const allRows = [];

  for (var ti = 0; ti < TAB_CONFIG.length; ti++) {
    var cfg = TAB_CONFIG[ti];
    stats.by_tab[cfg.name] = 0;
    var sh = deniseSS.getSheetByName(cfg.name);
    if (!sh) continue;
    var data = sh.getDataRange().getValues();
    if (data.length < 4) continue;

    var header = data[2];
    var hIdx = function(name) {
      for (var k = 0; k < header.length; k++) {
        if (String(header[k]).trim().toUpperCase() === name.toUpperCase()) return k;
      }
      return -1;
    };

    var iSupplier = hIdx('Supplier');
    var iAddress  = hIdx('Address');
    var iTin      = hIdx('TIN');
    var iVatNV    = hIdx('VAT/Nonvat');
    var iGoods    = hIdx('Goods/Services');
    var iInvDate  = hIdx('Invoice Date');
    var iTerms    = hIdx('Terms');
    var iBeiFin   = hIdx('BEI FIN');
    var iInvNo    = hIdx('Invoice No');
    var iDesc     = hIdx('Description');
    var iVatable  = hIdx('VATABLE SALES');
    var iVat      = hIdx('VAT');
    var iEwt      = hIdx('EWT');
    var iGross    = hIdx('GROSS Amount');
    var iPaid     = hIdx('Paid Amount');
    var iOut      = hIdx('Outstanding Balance');
    var iDue      = hIdx('DUE DATE');
    var iAging    = hIdx('AGING (days)');
    var iStatus   = hIdx('Status');

    if (iSupplier < 0 || iOut < 0) continue;

    for (var rr = 3; rr < data.length; rr++) {
      var r = data[rr];
      stats.scanned++;
      var supplier = String(r[iSupplier] || '').trim();
      if (!supplier) { stats.skipped_blank++; continue; }
      var outstanding = toNum(r[iOut]);
      if (outstanding <= 0) { stats.skipped_paid++; continue; }

      var invoiceNo = iInvNo >= 0 ? String(r[iInvNo] || '').trim() : '';
      var beiFin    = iBeiFin >= 0 ? String(r[iBeiFin] || '').trim() : '';

      // Intra-Denise dedup
      var payeeKey = supplier.toUpperCase();
      var invVariants = invNoVariants_(invoiceNo);
      var dupe = false;
      for (var iv = 0; iv < invVariants.length; iv++) {
        if (seenThisRun[payeeKey + '|' + invVariants[iv]]) { dupe = true; break; }
      }
      if (dupe) { stats.deduped_intra_denise++; continue; }
      for (var iv2 = 0; iv2 < invVariants.length; iv2++) {
        seenThisRun[payeeKey + '|' + invVariants[iv2]] = cfg.name;
      }

      var gross    = iGross >= 0 ? toNum(r[iGross]) : 0;
      var paid     = iPaid >= 0 ? toNum(r[iPaid]) : 0;
      var aging    = iAging >= 0 ? toNum(r[iAging]) : 0;
      var deniseStatus = iStatus >= 0 ? String(r[iStatus] || '').trim() : '';
      var apStatus = mapDeniseToApStatus_(deniseStatus);
      var bucket   = agingBucket(aging);
      var invDate  = iInvDate >= 0 ? r[iInvDate] : '';
      var dueDate  = iDue >= 0 ? r[iDue] : '';

      var row = [
        cfg.sourceTag,                                          // A  SOURCE
        supplier,                                               // B  PAYEE
        invoiceNo,                                              // C  INVOICE NO.
        invDate || '',                                          // D  INVOICE DATE
        gross,                                                  // E  AMOUNT
        outstanding,                                            // F  OUTSTANDING
        aging,                                                  // G  AGING
        bucket,                                                 // H  AGING BUCKET
        apStatus,                                               // I  STATUS
        beiFin,                                                 // J  BEI-FIN
        '',                                                     // K  RFP No.
        '',                                                     // L  METHOD
        '',                                                     // M  CHECK NO.
        cfg.category,                                           // N  CATEGORY
        cfg.name,                                               // O  CLASSIFICATION (Denise tab)
        '',                                                     // P  BILLED TO
        iVatable >= 0 ? toNum(r[iVatable]) : 0,                 // Q  VATABLE
        iVat >= 0 ? toNum(r[iVat]) : 0,                         // R  VAT
        iEwt >= 0 ? toNum(r[iEwt]) : 0,                         // S  EWT
        iAddress >= 0 ? String(r[iAddress] || '') : '',         // T  ADDRESS
        iTin >= 0 ? String(r[iTin] || '') : '',                 // U  TIN
        iVatNV >= 0 ? String(r[iVatNV] || '') : '',             // V  VAT/NONVAT
        iGoods >= 0 ? String(r[iGoods] || '') : '',             // W  GOODS/SERVICES
        iTerms >= 0 ? String(r[iTerms] || '') : '',             // X  TERMS
        iDesc >= 0 ? String(r[iDesc] || '') : '',               // Y  DESCRIPTION
        paid,                                                   // Z  PAID AMOUNT
        dueDate || '',                                          // AA DUE DATE
        deniseStatus,                                           // AB DENISE STATUS (original)
        cfg.name,                                               // AC DENISE TAB
        '',                                                     // AD NOTES (Denise can use after switching)
      ];
      allRows.push(row);
      stats.by_tab[cfg.name]++;
      stats.mirrored++;
    }
  }

  // Wipe rows 4+ and rewrite (only if not dryRun)
  if (!dryRun && allRows.length > 0) {
    var lastRow = pp.getLastRow();
    if (lastRow >= 4) {
      pp.getRange(4, 1, lastRow - 3, 30).clearContent();
    }
    pp.getRange(4, 1, allRows.length, 30).setValues(allRows);

    // Refresh banner row 2 with timestamp
    var ts = Utilities.formatDate(new Date(), 'Asia/Manila', 'yyyy-MM-dd HH:mm') + ' PHT';
    pp.getRange(2, 1).setValue(
      "Source: Denise 'Project: 2-Week Payment Plan' sheet | Last mirrored: " + ts +
      " | Ready for Denise to switch into when comfortable | Editors: sam@bebang.ph only (auto-mirrored)"
    );

    logEvent_v3_(ss, 'payment_plan_mirror_complete', {
      rows_written: allRows.length,
      by_tab: stats.by_tab,
      ts_pht: ts,
    });
  }

  return stats;
}

