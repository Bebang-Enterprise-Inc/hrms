/**
 * S210 Master Handler — BEI Receipt-Based Payment Infrastructure
 *
 * Bound/standalone Apps Script that orchestrates data flow from per-3PL
 * Google Sheets (A=3MD, B=Pinnacle, D=Shaw transitional) into the BEI-internal
 * master (Sheet C). Fires on edit and on time-based cron.
 *
 * Owner: commissary.team@bebang.ph
 * Source of truth: hrms repo `scripts/google_apps/s210_master_handler.gs`
 * Runtime deployment: Apps Script project created by
 *   `output/s210/phase3_deploy_apps_script.py`
 *
 * After deployment, a human editor must open the Apps Script editor once and
 * run `setup()` to install installable triggers. This is a one-time action.
 *
 * Triggers installed by setup():
 *   1. SPREADSHEET_EDIT on SHEET_A  -> handleNewReceipt_3MD
 *   2. SPREADSHEET_EDIT on SHEET_B  -> handleNewReceipt_Pinnacle
 *   3. Hourly time-based             -> ageVarianceQueue
 *   4. Daily 06:00 PHT time-based    -> refreshMasters  (Phase 5 body, trigger installed here)
 *
 * Phase 4 will add onFormSubmit trigger for the Supplier SI Upload form.
 * Phase 5 will flesh out refreshMasters() and sendCeoDailyEmail() + install its 07:00 trigger.
 */

// ========================================================================
// Configuration
// ========================================================================

const SHEET_A = '1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU';  // BEI 3MD Receiving Log 2026
const SHEET_B = '10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw';  // BEI Pinnacle Receiving Log 2026
const SHEET_C = '1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0';  // BEI Receiving Master 2026
const SHEET_D = '1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As';  // BEI Shaw Transitional Receiving

// Google Chat spaces (service account is member of both)
const SCM_SPACE = 'spaces/AAQArCi8zjE';
const PROCUREMENT_NOTIF_SPACE = 'spaces/AAQAYAYwPPk';

// Sheet A/B/D Receipts tab column indexes (0-indexed) — 16 cols post-Phase 7
// (CEO directive 2026-04-20 PM: 3PLs will not paste image/drive links in a
// spreadsheet. Photos were removed from the 3PL receiving sheets. SI PDFs
// flow through the separate supplier SI upload form.)
// Header row: Timestamp, 3PL, RR Number, PO Number, Supplier, Material Code,
//             Material Description, Qty Received, UoM, SI Number,
//             Trucker's Name, Plate Number, Production Date,
//             Expiration Date, Received By, Notes
const COL_TIMESTAMP = 0;
const COL_3PL = 1;
const COL_RR = 2;
const COL_PO = 3;
const COL_SUPPLIER = 4;
const COL_MATERIAL_CODE = 5;
const COL_MATERIAL_DESC = 6;
const COL_QTY = 7;
const COL_UOM = 8;
const COL_SI_NUM = 9;
const COL_TRUCKER = 10;
const COL_PLATE = 11;
const COL_PROD_DATE = 12;
const COL_EXP_DATE = 13;
const COL_RECEIVED_BY = 14;
const COL_NOTES = 15;

// Sheet C 02_All_Receipts_Consolidated — 22 cols
// A=Timestamp, B=Source_Sheet, C=3PL, D=RR, E=PO, F=Supplier, G=Mat Code,
// H=Mat Desc, I=Qty, J=UoM, K=SI#, L=SI Photo, M=Del Photo, N=Trucker,
// O=Plate, P=Prod Date, Q=Exp Date, R=Recv By, S=Notes, T=SI_Matched,
// U=SI_Upload_Link, V=SI_Match_Timestamp
const CONS_COL_SI_MATCHED = 19;  // 0-indexed col T
const CONS_COL_SI_UPLOAD_LINK = 20;  // col U
const CONS_COL_SI_MATCH_TS = 21;  // col V

// Stale DR threshold (hours)
const STALE_DR_HOURS = 72;

// ========================================================================
// Validation
// ========================================================================

/**
 * validateReceipt — checks PO open, supplier matches PO, material on PO,
 * qty <= balance, SI# present, SI photo present.
 *
 * Returns { ok: boolean, errors: string[], poInfo: object|null }
 */
function validateReceipt(rowData) {
  const errors = [];
  const poNumber = String(rowData[COL_PO] || '').trim();
  const supplier = String(rowData[COL_SUPPLIER] || '').trim();
  const materialCode = String(rowData[COL_MATERIAL_CODE] || '').trim();
  const qty = parseFloat(rowData[COL_QTY]);
  const siNumber = String(rowData[COL_SI_NUM] || '').trim();

  if (!poNumber) errors.push('PO Number missing');
  if (!supplier) errors.push('Supplier missing');
  if (!materialCode) errors.push('Material Code missing');
  if (!(qty > 0)) errors.push('Qty must be > 0');
  if (!siNumber) errors.push('SI Number missing');
  // SI photo check removed post-Phase 7 — photos flow via supplier SI upload form.

  // Cross-check PO against Open POs master
  let poInfo = null;
  if (poNumber) {
    const masterSs = SpreadsheetApp.openById(SHEET_C);
    const openPoSheet = masterSs.getSheetByName('08_Full_Open_POs');
    const poData = openPoSheet.getDataRange().getValues();
    // Headers: PO Number, PO Date, Supplier Code, Supplier Name, Destination 3PL,
    //          Total Amount, Balance, Delivery Needed By, Status
    for (let i = 1; i < poData.length; i++) {
      if (String(poData[i][0]).trim() === poNumber) {
        poInfo = {
          poNumber: poData[i][0],
          supplierCode: poData[i][2],
          supplierName: poData[i][3],
          destination: poData[i][4],
          totalAmount: poData[i][5],
          balance: parseFloat(poData[i][6]) || 0,
          status: poData[i][8],
        };
        break;
      }
    }
    if (!poInfo) {
      errors.push('PO not found in Open POs master');
    } else {
      if (supplier && poInfo.supplierName && supplier.toLowerCase() !== String(poInfo.supplierName).toLowerCase()) {
        errors.push('Supplier (' + supplier + ') does not match PO supplier (' + poInfo.supplierName + ')');
      }
      if (poInfo.balance > 0 && qty > poInfo.balance) {
        errors.push('Qty ' + qty + ' exceeds PO balance ' + poInfo.balance);
      }
    }
  }

  return { ok: errors.length === 0, errors: errors, poInfo: poInfo };
}

// ========================================================================
// Handlers — onEdit + polling
// ========================================================================

/**
 * Shared handler — reads new rows from a source sheet's Receipts tab since
 * last run, writes each into Sheet C consolidated + (validated → Pending GR)
 * or (invalid → Variance Queue), and posts Chat notifications.
 */
function _handleNewReceipts(sourceSheetId, sourceLabel) {
  const props = PropertiesService.getScriptProperties();
  const lastSeenKey = 'last_processed_' + sourceSheetId;
  const lastSeenIso = props.getProperty(lastSeenKey) || '2000-01-01T00:00:00.000Z';
  const lastSeen = new Date(lastSeenIso).getTime();

  const ss = SpreadsheetApp.openById(sourceSheetId);
  const receiptsTab = ss.getSheetByName('Receipts');
  if (!receiptsTab) return;
  const data = receiptsTab.getDataRange().getValues();
  if (data.length < 2) return;

  const masterSs = SpreadsheetApp.openById(SHEET_C);
  const consolidated = masterSs.getSheetByName('02_All_Receipts_Consolidated');
  const pending = masterSs.getSheetByName('06_Pending_GR');
  const variance = masterSs.getSheetByName('05_Variance_Queue');
  const auditLog = masterSs.getSheetByName('09_Audit_Log');

  let latestMs = lastSeen;
  let processed = 0;
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const tsRaw = row[COL_TIMESTAMP];
    if (!tsRaw) continue;
    const rowMs = new Date(tsRaw).getTime();
    if (isNaN(rowMs) || rowMs <= lastSeen) continue;

    const validation = validateReceipt(row);

    // Write to consolidated regardless — we want all receipts visible.
    // Consolidated schema retains SI Photo + Delivery Photo cols but they
    // are always empty post-Phase 7; SI PDF link flows via handleSiUpload.
    const consolidatedRow = [
      row[COL_TIMESTAMP], sourceLabel, row[COL_3PL] || sourceLabel, row[COL_RR],
      row[COL_PO], row[COL_SUPPLIER], row[COL_MATERIAL_CODE], row[COL_MATERIAL_DESC],
      row[COL_QTY], row[COL_UOM], row[COL_SI_NUM],
      '',  // SI Photo placeholder (3PL no longer captures)
      '',  // Delivery Photo placeholder
      row[COL_TRUCKER], row[COL_PLATE],
      row[COL_PROD_DATE], row[COL_EXP_DATE], row[COL_RECEIVED_BY], row[COL_NOTES],
      false,  // SI_Matched
      '',     // SI_Upload_Link
      '',     // SI_Match_Timestamp
    ];
    consolidated.appendRow(consolidatedRow);

    if (validation.ok) {
      pending.appendRow([
        row[COL_TIMESTAMP], row[COL_RR], sourceLabel, row[COL_PO],
        row[COL_SUPPLIER], row[COL_MATERIAL_CODE], row[COL_MATERIAL_DESC],
        row[COL_QTY], row[COL_UOM], row[COL_SI_NUM],
        '',        // SI PDF Link (filled by handleSiUpload)
        'PENDING', // Status
        false,     // Picked_Up_By_AppSheet
      ]);
      _logAudit(auditLog, 'receipt_edit', sourceLabel, i + 1, 'Pending_GR_written', 'OK', '');
      postChatNotification({
        source: sourceLabel,
        po: row[COL_PO],
        supplier: row[COL_SUPPLIER],
        material: row[COL_MATERIAL_DESC] || row[COL_MATERIAL_CODE],
        qty: row[COL_QTY],
        uom: row[COL_UOM],
        siNumber: row[COL_SI_NUM],
      });
    } else {
      variance.appendRow([
        row[COL_TIMESTAMP], row[COL_RR], validation.errors.join('; '),
        sourceLabel, row[COL_PO], row[COL_SUPPLIER], row[COL_MATERIAL_CODE],
        row[COL_QTY], 0, 'No SI match yet', 'Ian', 'OPEN', '',
      ]);
      _logAudit(auditLog, 'receipt_edit', sourceLabel, i + 1, 'Variance_written',
                'FAIL', validation.errors.join('; '));
    }

    if (rowMs > latestMs) latestMs = rowMs;
    processed++;
  }

  if (processed > 0) {
    props.setProperty(lastSeenKey, new Date(latestMs).toISOString());
  }
}

function handleNewReceipt_3MD() { _handleNewReceipts(SHEET_A, '3MD'); }
function handleNewReceipt_Pinnacle() { _handleNewReceipts(SHEET_B, 'Pinnacle'); }
function handleNewReceipt_Shaw() { _handleNewReceipts(SHEET_D, 'Shaw'); }

// ========================================================================
// Chat notifications
// ========================================================================

/**
 * postChatNotification — posts a formatted card to SCM + Procurement
 * Notifications spaces via the Chat REST API.
 */
function postChatNotification(receipt) {
  const text = [
    '📦 *New receipt — ' + receipt.source + '*',
    'PO: `' + (receipt.po || 'N/A') + '`',
    'Supplier: ' + (receipt.supplier || 'N/A'),
    'Material: ' + (receipt.material || 'N/A'),
    'Qty: ' + (receipt.qty || '?') + ' ' + (receipt.uom || ''),
    'SI#: ' + (receipt.siNumber || '(none yet)'),
  ].join('\n');

  const payload = { text: text };
  const spaces = [SCM_SPACE, PROCUREMENT_NOTIF_SPACE];
  for (const space of spaces) {
    try {
      const url = 'https://chat.googleapis.com/v1/' + space + '/messages';
      const resp = UrlFetchApp.fetch(url, {
        method: 'post',
        contentType: 'application/json',
        payload: JSON.stringify(payload),
        headers: { 'Authorization': 'Bearer ' + ScriptApp.getOAuthToken() },
        muteHttpExceptions: true,
      });
      if (resp.getResponseCode() >= 400) {
        console.error('Chat post failed for ' + space + ': ' + resp.getContentText());
      }
    } catch (e) {
      console.error('Chat post exception for ' + space + ': ' + e);
    }
  }
}

// ========================================================================
// Aging — hourly cron
// ========================================================================

/**
 * ageVarianceQueue — hourly cron. Moves DRs in 02_All_Receipts_Consolidated
 * that are older than STALE_DR_HOURS with SI_Matched=FALSE into
 * 05_Variance_Queue (idempotent; uses a column to mark already-aged rows).
 */
function ageVarianceQueue() {
  const masterSs = SpreadsheetApp.openById(SHEET_C);
  const consolidated = masterSs.getSheetByName('02_All_Receipts_Consolidated');
  const variance = masterSs.getSheetByName('05_Variance_Queue');
  const auditLog = masterSs.getSheetByName('09_Audit_Log');

  const data = consolidated.getDataRange().getValues();
  if (data.length < 2) {
    _logAudit(auditLog, 'ageVarianceQueue', 'cron', 0, 'No_data', 'OK', 'consolidated empty');
    return;
  }

  // Build set of RR numbers already in variance queue to avoid duplicates
  const varianceData = variance.getDataRange().getValues();
  const existingRR = new Set();
  for (let i = 1; i < varianceData.length; i++) {
    if (varianceData[i][1]) existingRR.add(String(varianceData[i][1]));
  }

  const now = new Date().getTime();
  const thresholdMs = STALE_DR_HOURS * 3600 * 1000;
  let moved = 0;
  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const tsRaw = row[0];
    if (!tsRaw) continue;
    const ts = new Date(tsRaw).getTime();
    if (isNaN(ts)) continue;
    const siMatched = row[CONS_COL_SI_MATCHED];
    const rr = String(row[3] || '');
    if ((now - ts) > thresholdMs && !siMatched && !existingRR.has(rr)) {
      variance.appendRow([
        new Date(), rr, 'Stale DR — no SI after ' + STALE_DR_HOURS + 'h',
        row[1],        // Source_Sheet
        row[4],        // PO Number
        row[5],        // Supplier
        row[6],        // Material Code
        row[8],        // Qty
        Math.round((now - ts) / 3600000),
        'No SI',
        'Ian',
        'OPEN',
        '',
      ]);
      moved++;
    }
  }
  _logAudit(auditLog, 'ageVarianceQueue', 'cron', 0,
            'Moved_' + moved + '_stale_DRs', 'OK',
            'threshold=' + STALE_DR_HOURS + 'h');
}

// ========================================================================
// Phase 5 — Daily master refresh + CEO daily email
// ========================================================================

// Procurement AppSheet source sheet (read-only, owned by sam@bebang.ph)
const PROCUREMENT_APPSHEET_ID = '1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q';

/**
 * refreshMasters — daily 06:00 cron. Pulls Suppliers + Purchase Order tabs
 * from Procurement AppSheet and rebuilds Sheet C 07_Full_Suppliers_Master +
 * 08_Full_Open_POs. Also regenerates Sheet A Suppliers_Visible +
 * Open_POs_3MD_Only, and Sheet B Suppliers_Visible + Open_POs_Pinnacle_Only,
 * by destination filter.
 *
 * Replace-in-place semantics: clears data rows (row 2 onwards), writes fresh.
 */
function refreshMasters() {
  const masterSs = SpreadsheetApp.openById(SHEET_C);
  const auditLog = masterSs.getSheetByName('09_Audit_Log');

  let suppliersWritten = 0;
  let openPosWritten = 0;
  let errors = [];

  try {
    // Pull Suppliers
    const srcSs = SpreadsheetApp.openById(PROCUREMENT_APPSHEET_ID);
    const suppliersTab = srcSs.getSheetByName('Suppliers');
    if (!suppliersTab) throw new Error('Procurement AppSheet missing Suppliers tab');
    const supData = suppliersTab.getDataRange().getValues();
    if (supData.length < 2) throw new Error('Suppliers tab empty');

    // Map source columns to our master schema
    const supHeaders = supData[0];
    const supCol = function(name) {
      const idx = supHeaders.indexOf(name);
      return idx;
    };
    const supIdx = {
      code: supCol('Supplier Code'),
      name: supCol('Supplier Name'),
      contactNo: supCol('Contact No'),
      contactPerson: supCol('Contact Person'),
      email: supCol('Email ID'),
      address: supCol('Address'),
      bankName: supCol('Bank Name'),
      bankAccName: supCol('Bank Account Name'),
      bankAccNo: supCol('Bank Account No'),
      vatReg: supCol('VAT Registered'),
      tin: supCol('TIN'),
      ewt: supCol('EWT Rate'),
      payTerms: supCol('Payment Terms'),
      tier: supCol('Tier'),
    };
    const safe = function(row, i) {
      return (i >= 0 && i < row.length) ? row[i] : '';
    };
    const suppliersRows = [];
    for (let i = 1; i < supData.length; i++) {
      const r = supData[i];
      if (!safe(r, supIdx.name)) continue;
      suppliersRows.push([
        safe(r, supIdx.code), safe(r, supIdx.name), safe(r, supIdx.contactNo),
        safe(r, supIdx.contactPerson), safe(r, supIdx.email), safe(r, supIdx.address),
        safe(r, supIdx.bankName), safe(r, supIdx.bankAccName), safe(r, supIdx.bankAccNo),
        safe(r, supIdx.vatReg), safe(r, supIdx.tin), safe(r, supIdx.ewt),
        safe(r, supIdx.payTerms), safe(r, supIdx.tier),
      ]);
    }

    const supMaster = masterSs.getSheetByName('07_Full_Suppliers_Master');
    const lastRow = supMaster.getLastRow();
    if (lastRow > 1) {
      supMaster.getRange(2, 1, lastRow - 1, 14).clearContent();
    }
    if (suppliersRows.length > 0) {
      supMaster.getRange(2, 1, suppliersRows.length, 14).setValues(suppliersRows);
    }
    suppliersWritten = suppliersRows.length;

    // Pull Purchase Order
    const poTab = srcSs.getSheetByName('Purchase Order');
    if (!poTab) throw new Error('Procurement AppSheet missing Purchase Order tab');
    const poData = poTab.getDataRange().getValues();
    const poHeaders = poData[0];
    const poCol = function() {
      for (let i = 0; i < arguments.length; i++) {
        const idx = poHeaders.indexOf(arguments[i]);
        if (idx >= 0) return idx;
      }
      return -1;
    };
    const poIdx = {
      poNum: poCol('PO Number', 'PO No', 'PO#'),
      poDate: poCol('PO Date', 'Date', 'Timestamp'),
      supCode: poCol('Supplier Code'),
      supName: poCol('Supplier Name', 'Supplier'),
      dest: poCol('Destination 3PL', 'Destination', 'Delivery to', 'Deliver To', 'Delivery Location'),
      total: poCol('Total Amount', 'Grand Total', 'Total'),
      balance: poCol('Balance', 'Outstanding Balance'),
      delivNeed: poCol('Delivery Needed By', 'Delivery Date', 'Required Date', 'Date Required'),
      status: poCol('Status', 'PO Status', 'Approval'),
    };
    const poRows = [];
    for (let i = 1; i < poData.length; i++) {
      const r = poData[i];
      if (!safe(r, poIdx.poNum)) continue;
      const status = String(safe(r, poIdx.status)).trim().toLowerCase();
      if (['closed', 'cancelled', 'canceled', 'rejected', 'void'].indexOf(status) >= 0) continue;
      poRows.push([
        safe(r, poIdx.poNum), safe(r, poIdx.poDate), safe(r, poIdx.supCode),
        safe(r, poIdx.supName), safe(r, poIdx.dest), safe(r, poIdx.total),
        safe(r, poIdx.balance), safe(r, poIdx.delivNeed), safe(r, poIdx.status),
      ]);
    }

    const poMaster = masterSs.getSheetByName('08_Full_Open_POs');
    const poLast = poMaster.getLastRow();
    if (poLast > 1) {
      poMaster.getRange(2, 1, poLast - 1, 9).clearContent();
    }
    if (poRows.length > 0) {
      poMaster.getRange(2, 1, poRows.length, 9).setValues(poRows);
    }
    openPosWritten = poRows.length;

    // Regenerate Sheet A / B per-destination tabs
    _refreshPerSheetFilteredTabs(masterSs, supMaster, poMaster);
  } catch (e) {
    errors.push(String(e));
  }

  const outcome = errors.length === 0 ? 'OK' : 'PARTIAL';
  _logAudit(auditLog, 'refreshMasters', 'cron', 0,
            'Refreshed_' + suppliersWritten + '_suppliers_' + openPosWritten + '_POs',
            outcome, errors.join('; '));
}

function _refreshPerSheetFilteredTabs(masterSs, supMaster, poMaster) {
  // Pull current master data
  const supData = supMaster.getDataRange().getValues();
  const poData = poMaster.getDataRange().getValues();

  // Suppliers visible to 3PLs (subset): code, name, tin, contact_person, contact_no
  const supVisible = [];
  for (let i = 1; i < supData.length; i++) {
    const r = supData[i];
    if (!r[1]) continue;
    supVisible.push([r[0], r[1], r[10], r[3], r[2]]);
  }

  const sheetA = SpreadsheetApp.openById(SHEET_A);
  const sheetB = SpreadsheetApp.openById(SHEET_B);

  // Sheet A / B: Suppliers_Visible tab (same list for both)
  for (const ss of [sheetA, sheetB]) {
    const tab = ss.getSheetByName('Suppliers_Visible');
    if (!tab) continue;
    const last = tab.getLastRow();
    if (last > 1) {
      tab.getRange(2, 1, last - 1, 5).clearContent();
    }
    if (supVisible.length > 0) {
      tab.getRange(2, 1, supVisible.length, 5).setValues(supVisible);
    }
  }

  // Sheet A: Open_POs_3MD_Only (filter destination contains 3MD)
  _writeFilteredPOs(sheetA, 'Open_POs_3MD_Only', poData, '3MD');
  _writeFilteredPOs(sheetB, 'Open_POs_Pinnacle_Only', poData, 'Pinnacle');
}

function _writeFilteredPOs(ss, tabName, poData, destFilter) {
  const tab = ss.getSheetByName(tabName);
  if (!tab) return;
  const matchFilter = String(destFilter).toLowerCase();
  const filtered = [];
  for (let i = 1; i < poData.length; i++) {
    const r = poData[i];
    const dest = String(r[4] || '').toLowerCase();
    if (dest.indexOf(matchFilter) >= 0) {
      // PO Number, Supplier Code, Supplier Name, Destination 3PL, Total, Balance, PO Date, Delivery Needed By
      filtered.push([r[0], r[2], r[3], r[4], r[5], r[6], r[1], r[7]]);
    }
  }
  const last = tab.getLastRow();
  if (last > 1) {
    tab.getRange(2, 1, last - 1, 8).clearContent();
  }
  if (filtered.length > 0) {
    tab.getRange(2, 1, filtered.length, 8).setValues(filtered);
  }
}

/**
 * sendCeoDailyEmail — daily 07:00 PHT cron. Pulls yesterday's KPIs from
 * Sheet C 01_Dashboard and sends a summary email to sam@bebang.ph and
 * ian@bebang.ph.
 *
 * Recipients (hard-coded per plan 5.1):
 *   - sam@bebang.ph
 *   - ian@bebang.ph
 */
function sendCeoDailyEmail() {
  const masterSs = SpreadsheetApp.openById(SHEET_C);
  const auditLog = masterSs.getSheetByName('09_Audit_Log');

  try {
    const dash = masterSs.getSheetByName('01_Dashboard');
    const values = dash.getRange('A1:B15').getValues();

    // Build label/value map
    const kpis = {};
    for (let i = 0; i < values.length; i++) {
      const label = String(values[i][0] || '').trim();
      const val = values[i][1];
      if (label) kpis[label] = val;
    }

    const yesterday = new Date(new Date().getTime() - 24 * 3600 * 1000);
    const ymd = Utilities.formatDate(yesterday, 'Asia/Manila', 'yyyy-MM-dd');

    const subject = '[BEI Receiving] Daily KPI digest — ' + ymd;
    const bodyLines = [
      'BEI Receiving Infrastructure — Daily KPI Digest',
      'Snapshot: ' + new Date().toLocaleString('en-PH', { timeZone: 'Asia/Manila' }),
      '',
      "Today's receipts:",
      '  • 3MD:      ' + (kpis["Today's receipts — 3MD"] || 0),
      '  • Pinnacle: ' + (kpis["Today's receipts — Pinnacle"] || 0),
      '  • Shaw:     ' + (kpis["Today's receipts — Shaw (transitional)"] || 0),
      '',
      'Quality:',
      '  • SI match rate: ' + _pct(kpis['SI match rate (today\'s receipts)']),
      '  • Stale DR count (>72h): ' + (kpis['Stale DR count (>72h, no SI match)'] || 0),
      '',
      'Queues:',
      '  • Pending GR depth: ' + (kpis['Pending GR depth'] || 0),
      '  • Orphan SI count: ' + (kpis['Orphan SI count (Match Queue)'] || 0),
      '',
      'Masters:',
      '  • Suppliers: ' + (kpis['Full Suppliers Master — rows'] || 0),
      '  • Open POs:  ' + (kpis['Full Open POs — rows'] || 0),
      '',
      'Events:',
      '  • Audit log today: ' + (kpis['Audit log events today'] || 0),
      '',
      'Dashboard: https://docs.google.com/spreadsheets/d/' + SHEET_C + '/edit#gid=0',
      '',
      '— BEI Receiving Master handler (automated)',
    ];

    GmailApp.sendEmail(
      'sam@bebang.ph, ian@bebang.ph',
      subject,
      bodyLines.join('\n'),
      { name: 'BEI Receiving Bot' }
    );

    _logAudit(auditLog, 'sendCeoDailyEmail', 'cron', 0,
              'Digest_sent', 'OK', 'to sam@bebang.ph, ian@bebang.ph');
  } catch (e) {
    _logAudit(auditLog, 'sendCeoDailyEmail', 'cron', 0,
              'Digest_failed', 'FAIL', String(e));
  }
}

function _pct(x) {
  const n = Number(x);
  if (isNaN(n)) return '0%';
  return Math.round(n * 100) + '%';
}

// ========================================================================
// Phase 4 — Supplier SI Upload + matching
// ========================================================================

// SI Upload Form field question IDs (captured by phase4_create_si_upload_form.py)
const SI_FORM_ITEM_IDS = {
  supplierName: '3a0fe354',
  poNumber: '52a3ede1',
  siNumber: '29b75eda',
  siDate: '7b642217',
  amount: '5631c342',
  siPdfLink: '2088304f',
  notes: '4ba080ae',
};

/**
 * handleSiUpload — onFormSubmit trigger for the BEI Supplier SI Upload form.
 *
 * Reads the latest form response (event param `e.namedValues` or `e.values`),
 * writes a row into Sheet C 03_Supplier_SI_Uploads, and attempts to match
 * against 02_All_Receipts_Consolidated by (PO#, SI#). On clean match, tags
 * the DR row with SI_Matched=TRUE + drive link + match timestamp. On no match,
 * writes the upload into 04_Match_Queue for manual resolution.
 */
function handleSiUpload(e) {
  const masterSs = SpreadsheetApp.openById(SHEET_C);
  const siUploads = masterSs.getSheetByName('03_Supplier_SI_Uploads');
  const consolidated = masterSs.getSheetByName('02_All_Receipts_Consolidated');
  const matchQueue = masterSs.getSheetByName('04_Match_Queue');
  const auditLog = masterSs.getSheetByName('09_Audit_Log');

  // e.namedValues is keyed by form item title; e.values is array in item order
  // Form items (in order): Supplier Name, PO Number, SI Number, SI Date,
  //                        Amount (PHP), SI PDF Drive Link, Notes
  let supplierName = '', poNumber = '', siNumber = '', siDate = '';
  let amount = '', siPdfLink = '', notes = '';

  if (e && e.namedValues) {
    const nv = e.namedValues;
    const first = function(key) {
      const v = nv[key];
      return v && v.length ? v[0] : '';
    };
    supplierName = first('Supplier Name');
    poNumber = first('PO Number');
    siNumber = first('SI Number');
    siDate = first('SI Date');
    amount = first('Amount (PHP)');
    siPdfLink = first('SI PDF Drive Link') || first('SI PDF');
    notes = first('Notes');
  } else if (e && e.values) {
    // Fallback: positional (index 0 is Timestamp from form)
    supplierName = e.values[1] || '';
    poNumber = e.values[2] || '';
    siNumber = e.values[3] || '';
    siDate = e.values[4] || '';
    amount = e.values[5] || '';
    siPdfLink = e.values[6] || '';
    notes = e.values[7] || '';
  }

  const timestamp = new Date();

  // Attempt match by (PO#, SI#) — normalize whitespace + case
  const normPo = String(poNumber).trim().toUpperCase();
  const normSi = String(siNumber).trim().toUpperCase();

  let matchedRow = -1;
  let matchedRRNumber = '';
  if (normPo && normSi) {
    const data = consolidated.getDataRange().getValues();
    // col indexes (0-based in data): 3=RR, 4=PO, 10=SI Number
    for (let i = 1; i < data.length; i++) {
      const rowPo = String(data[i][4] || '').trim().toUpperCase();
      const rowSi = String(data[i][10] || '').trim().toUpperCase();
      if (rowPo === normPo && rowSi === normSi) {
        matchedRow = i + 1;  // 1-based for setValue
        matchedRRNumber = data[i][3];
        break;
      }
    }
  }

  const matchStatus = matchedRow > 0 ? 'MATCHED' : 'ORPHAN';

  // Write into 03_Supplier_SI_Uploads
  siUploads.appendRow([
    timestamp, supplierName, poNumber, siNumber, siDate,
    amount, siPdfLink, notes, matchStatus, matchedRRNumber,
    matchedRow > 0 ? timestamp : '',
  ]);

  if (matchedRow > 0) {
    // Tag the matched DR row in consolidated:
    // col T = SI_Matched (20), col U = SI_Upload_Link (21), col V = SI_Match_Timestamp (22)
    consolidated.getRange(matchedRow, 20).setValue(true);
    consolidated.getRange(matchedRow, 21).setValue(siPdfLink);
    consolidated.getRange(matchedRow, 22).setValue(timestamp);

    // Also tag Pending GR row if present
    const pending = masterSs.getSheetByName('06_Pending_GR');
    const pendingData = pending.getDataRange().getValues();
    for (let i = 1; i < pendingData.length; i++) {
      const rowPo = String(pendingData[i][3] || '').trim().toUpperCase();
      const rowSi = String(pendingData[i][9] || '').trim().toUpperCase();
      if (rowPo === normPo && rowSi === normSi) {
        // Update SI PDF Link (col 11 = K, 1-based index 11)
        pending.getRange(i + 1, 11).setValue(siPdfLink);
        pending.getRange(i + 1, 12).setValue('READY');
        break;
      }
    }

    _logAudit(auditLog, 'handleSiUpload', supplierName, matchedRow,
              'SI_matched_to_RR_' + matchedRRNumber, 'OK',
              'PO=' + poNumber + ' SI=' + siNumber);
  } else {
    // Orphan: write to 04_Match_Queue for manual resolution
    matchQueue.appendRow([
      timestamp, 'Orphan SI — no matching DR found',
      supplierName, poNumber, siNumber, siDate, amount, siPdfLink,
      'Ian', 'OPEN', '',
    ]);
    _logAudit(auditLog, 'handleSiUpload', supplierName, 0,
              'Orphan_SI_to_Match_Queue', 'WARN',
              'PO=' + poNumber + ' SI=' + siNumber + ' — no DR match');
  }
}

/**
 * generateSupplierUrls — pulls Tier A supplier list from
 * 07_Full_Suppliers_Master, builds pre-filled URLs for the SI Upload form,
 * and writes them to 07's Tier A URL column (future extension) OR returns
 * them as a batch for export.
 *
 * NOTE: Python script `phase4_create_si_upload_form.py` already generates the
 * canonical SUPPLIER_URLS.csv. This Apps Script function exists for
 * on-demand regeneration inside the script runtime (e.g., when Tier
 * classification changes). It uses the form's internal entry ID for
 * Supplier Name pre-fill.
 */
function generateSupplierUrls() {
  const FORM_BASE = 'https://docs.google.com/forms/d/e/1FAIpQLSdsifYasH8h8_iBGkbsZyhssSmRQX-zXzvxeNVSfwhA2yPvTw/viewform';
  const SUPPLIER_ENTRY_ID = SI_FORM_ITEM_IDS.supplierName;
  const masterSs = SpreadsheetApp.openById(SHEET_C);
  const suppliers = masterSs.getSheetByName('07_Full_Suppliers_Master');
  const data = suppliers.getDataRange().getValues();
  const urls = [];
  for (let i = 1; i < data.length; i++) {
    const name = data[i][1];
    const tier = String(data[i][13] || '').trim().toUpperCase();
    if (!name) continue;
    if (tier === 'B' || tier === 'TIER B' || tier === 'C' || tier === 'TIER C') continue;
    const url = FORM_BASE
      + '?usp=pp_url&entry.' + SUPPLIER_ENTRY_ID + '='
      + encodeURIComponent(name);
    urls.push({ supplier: name, url: url });
  }
  console.log('Generated ' + urls.length + ' supplier URLs');
  return urls;
}

// ========================================================================
// Audit logging helper
// ========================================================================

function _logAudit(sheet, trigger, source, row, action, outcome, details) {
  try {
    sheet.appendRow([new Date(), trigger, source, row, action, outcome, details || '']);
  } catch (e) {
    console.error('_logAudit failed: ' + e);
  }
}

// ========================================================================
// Setup — install installable triggers (run ONCE by a human editor)
// ========================================================================

/**
 * setup — run this ONCE from the Apps Script editor after first deployment.
 * Idempotent: deletes any existing s210 triggers before reinstalling.
 */
function setup() {
  // Delete any existing triggers managed by this project to keep clean state
  const existing = ScriptApp.getProjectTriggers();
  const managed = new Set([
    'handleNewReceipt_3MD',
    'handleNewReceipt_Pinnacle',
    'handleNewReceipt_Shaw',
    'ageVarianceQueue',
    'refreshMasters',
    'sendCeoDailyEmail',
    'handleSiUpload',
  ]);
  for (const t of existing) {
    if (managed.has(t.getHandlerFunction())) {
      ScriptApp.deleteTrigger(t);
    }
  }

  // 1. onEdit on Sheet A (3MD)
  ScriptApp.newTrigger('handleNewReceipt_3MD')
    .forSpreadsheet(SHEET_A).onEdit().create();

  // 2. onEdit on Sheet B (Pinnacle)
  ScriptApp.newTrigger('handleNewReceipt_Pinnacle')
    .forSpreadsheet(SHEET_B).onEdit().create();

  // 3. onEdit on Sheet D (Shaw transitional)
  ScriptApp.newTrigger('handleNewReceipt_Shaw')
    .forSpreadsheet(SHEET_D).onEdit().create();

  // 4. Hourly cron — ageVarianceQueue
  ScriptApp.newTrigger('ageVarianceQueue')
    .timeBased().everyHours(1).create();

  // 5. Daily 06:00 PHT — refreshMasters (body added Phase 5)
  ScriptApp.newTrigger('refreshMasters')
    .timeBased().atHour(6).everyDays(1)
    .inTimezone('Asia/Manila').create();

  // 6. Daily 07:00 PHT — sendCeoDailyEmail (body added Phase 5)
  ScriptApp.newTrigger('sendCeoDailyEmail')
    .timeBased().atHour(7).everyDays(1)
    .inTimezone('Asia/Manila').create();

  // 7. onFormSubmit — handleSiUpload (SI_UPLOAD_FORM_ID from SHEET_IDS.json)
  // Note: installable onFormSubmit must be attached to the form. In the
  // editor, open the SI Upload form, choose "Script editor" and add the
  // handleSiUpload function with an onFormSubmit installable trigger. For
  // a standalone script, we use Form ID programmatically:
  const SI_UPLOAD_FORM_ID = '1DsT-IdDpW_p3XfpSevkyCZ7S-YVu3EWEK3SxD1lJ940';
  try {
    const form = FormApp.openById(SI_UPLOAD_FORM_ID);
    ScriptApp.newTrigger('handleSiUpload')
      .forForm(form).onFormSubmit().create();
  } catch (err) {
    console.error('Failed to install onFormSubmit trigger: ' + err);
  }

  console.log('setup complete: 7 triggers installed');

  // Audit log entry to confirm setup ran
  const masterSs = SpreadsheetApp.openById(SHEET_C);
  const auditLog = masterSs.getSheetByName('09_Audit_Log');
  _logAudit(auditLog, 'setup', 'manual', 0, 'Triggers_installed', 'OK',
            '6 triggers: 3 onEdit + 3 timeBased');
}

/**
 * listTriggers — diagnostic helper; prints all installed triggers with their
 * handler functions and event types.
 */
function listTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  const out = triggers.map(function(t) {
    return {
      handler: t.getHandlerFunction(),
      eventType: String(t.getEventType()),
      triggerSource: String(t.getTriggerSource()),
      id: t.getUniqueId(),
    };
  });
  console.log(JSON.stringify(out, null, 2));
  return out;
}
