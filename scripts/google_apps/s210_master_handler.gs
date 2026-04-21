/**
 * S210 Master Handler — BEI Receipt-Based Payment Infrastructure
 *
 * Phase 8 (2026-04-20 PM): converted to web-app + Cloud Scheduler pattern.
 * No Apps Script triggers needed — Cloud Scheduler pings the web-app URL on
 * cron. This eliminates the manual setup() click that was required for
 * ScriptApp.newTrigger() OAuth consent (a limitation of service-account DWD).
 *
 * Source of truth: hrms repo `scripts/google_apps/s210_master_handler.gs`
 * Deployed via:  output/s210/phase8_cloud_scheduler.py
 *
 * doGet(e) is the single entry point. Cloud Scheduler jobs hit:
 *   https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec?key=<TOKEN>&fn=<NAME>
 *
 * Supported fn values:
 *   - pollAll           (every 1 min)    polls Sheets A/B/D Receipts + form responses
 *   - ageVarianceQueue  (hourly)         stale DR > 72h into Variance Queue
 *   - refreshMasters    (daily 06:00 PHT) pulls Procurement AppSheet -> 07/08 masters
 *   - sendCeoDailyEmail (daily 07:00 PHT) KPI digest email to sam+ian
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

// Shared token for web-app access. URL obscurity is primary defense
// (deployment ID is 57+ chars of random base64url); this token is a
// secondary factor. Matching token is stored in Cloud Scheduler job URLs.
const SHARED_TOKEN = 's210-b3i-a8F2kQ9mZv7RpYxLnCdT4wE6hG1jN5uH0sK3';

// SI Upload form ID (Phase 7 form with native file upload)
const SI_UPLOAD_FORM_ID = '1gyijOzmjXJHlyil7wraQ8xjmPMu0q1eoqUcjwHXogPg';

// ========================================================================
// doGet — web-app entry point (Cloud Scheduler target)
// ========================================================================

function doGet(e) {
  const params = (e && e.parameter) || {};
  const token = String(params.key || '');
  const fn = String(params.fn || '');

  const respond = function(body) {
    return ContentService.createTextOutput(JSON.stringify(body))
      .setMimeType(ContentService.MimeType.JSON);
  };

  if (token !== SHARED_TOKEN) {
    return respond({ ok: false, error: 'unauthorized' });
  }

  const started = new Date();
  try {
    let result;
    switch (fn) {
      case 'pollAll':           result = pollAll();           break;
      case 'pollReceipts':      result = pollReceipts();      break;
      case 'pollFormResponses': result = pollFormResponses(); break;
      case 'ageVarianceQueue':  result = ageVarianceQueue();  break;
      case 'refreshMasters':    result = refreshMasters();    break;
      case 'sendCeoDailyEmail': result = sendCeoDailyEmail(); break;
      case 'ping':              result = { pong: true };      break;
      default:
        return respond({ ok: false, error: 'unknown_fn: ' + fn });
    }
    const elapsed = new Date().getTime() - started.getTime();
    return respond({ ok: true, fn: fn, elapsed_ms: elapsed, result: result || null });
  } catch (err) {
    return respond({ ok: false, fn: fn, error: String(err) });
  }
}

// ========================================================================
// Scheduler-targeted poll functions
// ========================================================================

function pollAll() {
  const receipts = pollReceipts();
  const formResp = pollFormResponses();
  return { receipts: receipts, form: formResp };
}

function pollReceipts() {
  const out = {};
  try { _handleNewReceipts(SHEET_A, '3MD'); out.a = 'ok'; } catch (e) { out.a = String(e); }
  try { _handleNewReceipts(SHEET_B, 'Pinnacle'); out.b = 'ok'; } catch (e) { out.b = String(e); }
  try { _handleNewReceipts(SHEET_D, 'Shaw'); out.d = 'ok'; } catch (e) { out.d = String(e); }
  return out;
}

function pollFormResponses() {
  const props = PropertiesService.getScriptProperties();
  const lastSeenKey = 'form_last_processed_' + SI_UPLOAD_FORM_ID;
  const lastSeenIso = props.getProperty(lastSeenKey) || '2000-01-01T00:00:00.000Z';
  const lastSeen = new Date(lastSeenIso).getTime();

  let form;
  try {
    form = FormApp.openById(SI_UPLOAD_FORM_ID);
  } catch (e) {
    return { processed: 0, error: String(e) };
  }

  const responses = form.getResponses();
  let latestMs = lastSeen;
  let processed = 0;
  for (const response of responses) {
    const ts = response.getTimestamp().getTime();
    if (isNaN(ts) || ts <= lastSeen) continue;

    const namedValues = {};
    for (const ir of response.getItemResponses()) {
      const title = ir.getItem().getTitle();
      let value = ir.getResponse();
      if (Array.isArray(value)) {
        if (value.length > 0 && typeof value[0] === 'string') {
          value = 'https://drive.google.com/file/d/' + value[0] + '/view';
        } else {
          value = String(value[0] || '');
        }
      }
      namedValues[title] = [value];
    }
    try {
      handleSiUpload({ namedValues: namedValues, timestamp: response.getTimestamp() });
    } catch (e) {
      console.error('handleSiUpload failed: ' + e);
    }

    if (ts > latestMs) latestMs = ts;
    processed++;
  }

  if (processed > 0) {
    props.setProperty(lastSeenKey, new Date(latestMs).toISOString());
  }
  return { processed: processed };
}

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

  // Cross-check PO against Open POs master using fuzzy _normalizePo
  // so PO-2026-1234 / 2026-1234 / 20261234 all match the same row.
  let poInfo = null;
  if (poNumber) {
    const normPoLookup = _normalizePo(poNumber);
    const masterSs = SpreadsheetApp.openById(SHEET_C);
    const openPoSheet = masterSs.getSheetByName('08_Full_Open_POs');
    const poData = openPoSheet.getDataRange().getValues();
    // Headers: PO Number, PO Date, Supplier Code, Supplier Name, Destination 3PL,
    //          Total Amount, Balance, Delivery Needed By, Status
    for (let i = 1; i < poData.length; i++) {
      if (_normalizePo(poData[i][0]) === normPoLookup) {
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
 *
 * Multi-line delivery support (Phase 10): header fields (RR#, PO#, Supplier,
 * SI#, Trucker, Plate, Received By) auto-inherit from the most recent prior
 * row with a non-blank value in each column. This lets the 3PL type header
 * fields once for the first line of a delivery and leave them blank on
 * subsequent lines (just Material Code + Qty + UoM + dates). Per-line fields
 * (Material, Qty, UoM, Production/Expiration Date, Notes) are NEVER inherited.
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
    const rawRow = data[i];
    const tsRaw = rawRow[COL_TIMESTAMP];
    if (!tsRaw) continue;
    const rowMs = new Date(tsRaw).getTime();
    if (isNaN(rowMs) || rowMs <= lastSeen) continue;

    // Phase 10: inherit blank header fields from the most recent prior row
    // that has them populated. Lets 3PL type shared fields once per delivery.
    const row = _fillInheritedHeaders(data, i);
    const inherited = [];
    const HEADER_COLS = [COL_RR, COL_PO, COL_SUPPLIER, COL_SI_NUM,
                         COL_TRUCKER, COL_PLATE, COL_RECEIVED_BY];
    for (const c of HEADER_COLS) {
      if (!_isBlank(rawRow[c]) && _isBlank(row[c])) continue;
      if (_isBlank(rawRow[c]) && !_isBlank(row[c])) inherited.push(c);
    }

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
      _logAudit(auditLog, 'receipt_edit', sourceLabel, i + 1, 'Pending_GR_written', 'OK',
                inherited.length ? 'inherited_cols=' + inherited.join(',') : '');
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

/**
 * _isBlank — treats '', null, undefined, whitespace-only strings as blank.
 */
function _isBlank(v) {
  if (v === null || v === undefined) return true;
  return String(v).trim() === '';
}

/**
 * _normalizeId — normalize a PO or SI identifier for fuzzy comparison.
 * Strips all non-alphanumeric characters (dashes, spaces, slashes, dots,
 * underscores), uppercases. Optionally strips a leading prefix like "PO"
 * or "SI" so `PO-2026-1234` == `2026-1234` == `20261234` == `po2026/1234`.
 *
 * Rationale: suppliers and 3PL staff type PO / SI identifiers in many
 * formats. Rather than policing input, we normalize both sides the same
 * way before comparing.
 *
 * @param {string} s       raw identifier
 * @param {string} prefix  optional prefix to strip if present (e.g. 'PO')
 * @return {string}        canonical form for comparison
 */
function _normalizeId(s, prefix) {
  let norm = String(s || '').replace(/[^A-Z0-9]/gi, '').toUpperCase();
  if (prefix) {
    const p = String(prefix).toUpperCase();
    if (norm.indexOf(p) === 0) {
      const rest = norm.substring(p.length);
      // Only strip the prefix if what's left is still non-empty (defends
      // against bogus input like just "PO").
      if (rest) norm = rest;
    }
  }
  return norm;
}

function _normalizePo(s) { return _normalizeId(s, 'PO'); }
function _normalizeSi(s) { return _normalizeId(s, 'SI'); }

/**
 * _fillInheritedHeaders — returns a copy of data[rowIdx] with blank header
 * fields populated from the most recent prior row that has them. Per-line
 * fields are NEVER inherited.
 *
 * Inherited header columns: RR#, PO#, Supplier, SI#, Trucker, Plate, Received By.
 * Per-line (never inherited): Material Code/Desc, Qty, UoM, Production Date,
 * Expiration Date, Notes, Timestamp, 3PL.
 */
function _fillInheritedHeaders(data, rowIdx) {
  const HEADER_COLS = [COL_RR, COL_PO, COL_SUPPLIER, COL_SI_NUM,
                       COL_TRUCKER, COL_PLATE, COL_RECEIVED_BY];
  const row = data[rowIdx].slice();  // shallow copy
  for (const col of HEADER_COLS) {
    if (!_isBlank(row[col])) continue;
    for (let j = rowIdx - 1; j >= 1; j--) {
      if (!_isBlank(data[j][col])) {
        row[col] = data[j][col];
        break;
      }
    }
  }
  return row;
}

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

  // S215 Phase 1: pull Procurement `Item List` -> Sheet C `10_Full_Materials_Master`
  let materialsWritten = 0;
  try {
    materialsWritten = _refreshMaterialsMaster_(masterSs);
  } catch (e) {
    errors.push('materials: ' + String(e));
  }

  // S215 Phase 2: pull Procurement `PO Items` joined with Purchase Order.Ship To
  //   -> Sheet C `11_Full_PO_Lines` + per-3PL filtered tabs on A/B/D
  let poLinesWritten = 0;
  try {
    poLinesWritten = _refreshPoLinesAndPer3plTabs_(masterSs);
  } catch (e) {
    errors.push('po_lines: ' + String(e));
  }

  // S215 Phase 3: push latest material codes to the SI Upload form dropdown.
  // Keeps the supplier-facing dropdown in sync with Item List without manual work.
  let materialCodesPushed = 0;
  try {
    materialCodesPushed = _refreshFormMaterialCodes_(masterSs);
  } catch (e) {
    errors.push('form_material_codes: ' + String(e));
  }

  const outcome = errors.length === 0 ? 'OK' : 'PARTIAL';
  _logAudit(auditLog, 'refreshMasters', 'cron', 0,
            'Refreshed_' + suppliersWritten + '_suppliers_' + openPosWritten + '_POs_' +
              materialsWritten + '_materials_' + poLinesWritten + '_po_lines_' +
              materialCodesPushed + '_mat_codes',
            outcome, errors.join('; '));
}

/**
 * S215 Phase 3: push deduped Material Codes from `10_Full_Materials_Master`
 * to the SI Upload form dropdown. Keeps supplier-facing choices in sync.
 * Uses FormApp (Apps Script native — executes as deployer sam@bebang.ph).
 * Returns number of options pushed.
 */
function _refreshFormMaterialCodes_(masterSs) {
  const matMaster = masterSs.getSheetByName('10_Full_Materials_Master');
  if (!matMaster) return 0;
  const last = matMaster.getLastRow();
  if (last < 2) return 0;
  const codes = matMaster.getRange(2, 2, last - 1, 1).getValues()
    .map(function(r) { return String(r[0] || '').trim(); })
    .filter(function(c) { return c.length > 0; });
  const unique = [];
  const seen = {};
  for (let i = 0; i < codes.length; i++) {
    if (!seen[codes[i]]) { seen[codes[i]] = true; unique.push(codes[i]); }
  }
  unique.sort();

  const form = FormApp.openById(SI_UPLOAD_FORM_ID);
  const items = form.getItems();
  let target = null;
  for (let i = 0; i < items.length; i++) {
    if (items[i].getTitle() === 'Material Code') { target = items[i]; break; }
  }
  if (!target) return 0;

  // Material Code is a DROP_DOWN choice question — native Apps Script gives asListItem()
  target.asListItem().setChoiceValues(unique);
  return unique.length;
}

/**
 * S215 Phase 1: pull Procurement AppSheet `Item List` -> Sheet C `10_Full_Materials_Master`.
 * Returns number of rows written.
 *
 * Source cols (11): Timestamp, Item Code, Item Name, UOM, Unit Price (Vat Inc),
 *                   Unit Price (Vat ex), VAT, REMARKS, Category, Packaging size, Added By
 */
function _refreshMaterialsMaster_(masterSs) {
  const srcSs = SpreadsheetApp.openById(PROCUREMENT_APPSHEET_ID);
  const src = srcSs.getSheetByName('Item List');
  if (!src) throw new Error('Item List tab missing in Procurement AppSheet');
  const data = src.getDataRange().getValues();
  if (data.length < 2) return 0;

  // Snap to canonical 11-column shape (A..K of source). Other cols ignored.
  const rows = [];
  for (let i = 1; i < data.length; i++) {
    const r = data[i];
    if (!r[1]) continue;  // skip empty Item Code rows
    rows.push([
      r[0] || '',  // Timestamp
      r[1] || '',  // Item Code
      r[2] || '',  // Item Name
      r[3] || '',  // UOM
      r[4] || '',  // Unit Price (Vat Inc)
      r[5] || '',  // Unit Price (Vat ex)
      r[6] || '',  // VAT
      r[7] || '',  // REMARKS
      r[8] || '',  // Category
      r[9] || '',  // Packaging size
      r[10] || '', // Added By
    ]);
  }

  const tab = masterSs.getSheetByName('10_Full_Materials_Master');
  if (!tab) throw new Error('10_Full_Materials_Master tab not created yet');
  const last = tab.getLastRow();
  if (last > 1) tab.getRange(2, 1, last - 1, 11).clearContent();
  if (rows.length > 0) tab.getRange(2, 1, rows.length, 11).setValues(rows);
  return rows.length;
}

/**
 * S215 Phase 2: pull Procurement AppSheet `PO Items` (A..O), join with
 * `Purchase Order`.Ship To (col K) on PO No, and write:
 *   - Sheet C `11_Full_PO_Lines` (all lines + joined Ship To as col P)
 *   - Sheet A `PO_Lines_3MD_Only`
 *   - Sheet B `PO_Lines_Pinnacle_Only`
 *   - Sheet D `PO_Lines_Shaw_Only`
 * Per-3PL tabs use case-insensitive substring match on Ship To.
 * Returns total rows written to master tab.
 */
function _refreshPoLinesAndPer3plTabs_(masterSs) {
  const srcSs = SpreadsheetApp.openById(PROCUREMENT_APPSHEET_ID);
  const itemsTab = srcSs.getSheetByName('PO Items');
  if (!itemsTab) throw new Error('PO Items tab missing');
  const poTab = srcSs.getSheetByName('Purchase Order');
  if (!poTab) throw new Error('Purchase Order tab missing');

  // Build PO No -> Ship To map from Purchase Order tab
  const poData = poTab.getDataRange().getValues();
  const poHeaders = poData[0];
  const poNoIdx = poHeaders.indexOf('PO No');
  const shipToIdx = poHeaders.indexOf('Ship To');
  if (poNoIdx < 0 || shipToIdx < 0) {
    throw new Error('Purchase Order headers missing PO No or Ship To');
  }
  const shipToMap = {};
  for (let i = 1; i < poData.length; i++) {
    const poNum = String(poData[i][poNoIdx] || '').trim();
    if (!poNum) continue;
    shipToMap[poNum] = String(poData[i][shipToIdx] || '').trim();
  }

  // Read PO Items (A..O = 15 cols); build joined rows (16 cols incl Ship To)
  const itemsData = itemsTab.getDataRange().getValues();
  const joinedRows = [];
  for (let i = 1; i < itemsData.length; i++) {
    const r = itemsData[i];
    const poNum = String(r[2] || '').trim();  // col C = PO No
    if (!poNum) continue;
    const shipTo = shipToMap[poNum] || '';
    joinedRows.push([
      r[0] || '',  // A Timestamp
      r[1] || '',  // B PR No
      r[2] || '',  // C PO No
      r[3] || '',  // D Uniqueid
      r[4] || '',  // E Item No
      r[5] || '',  // F Item Code
      r[6] || '',  // G Item Name
      r[7] || '',  // H Packaging size
      r[8] || '',  // I Qty
      r[9] || '',  // J UOM
      r[10] || '', // K Unit Cost
      r[11] || '', // L VAT
      r[12] || '', // M Amount
      r[13] || '', // N Delivery Schedule
      r[14] || '', // O Added By
      shipTo,      // P Ship To (joined)
    ]);
  }

  // Write to Sheet C 11_Full_PO_Lines
  const masterTab = masterSs.getSheetByName('11_Full_PO_Lines');
  if (!masterTab) throw new Error('11_Full_PO_Lines tab not created yet');
  const last = masterTab.getLastRow();
  if (last > 1) masterTab.getRange(2, 1, last - 1, 16).clearContent();
  if (joinedRows.length > 0) masterTab.getRange(2, 1, joinedRows.length, 16).setValues(joinedRows);

  // Write per-3PL filtered tabs
  const cases = [
    { ssid: SHEET_A, tabName: 'PO_Lines_3MD_Only', filter: '3MD' },
    { ssid: SHEET_B, tabName: 'PO_Lines_Pinnacle_Only', filter: 'PINNACLE' },
    { ssid: SHEET_D, tabName: 'PO_Lines_Shaw_Only', filter: 'SHAW' },
  ];
  for (const c of cases) {
    const ss = SpreadsheetApp.openById(c.ssid);
    const tab = ss.getSheetByName(c.tabName);
    if (!tab) continue;  // tab must be pre-created (idempotent helper does that)
    const match = c.filter.toUpperCase();
    const filtered = joinedRows.filter(function (row) {
      const st = String(row[15] || '').toUpperCase();
      return st && st.indexOf(match) >= 0;
    });
    const tabLast = tab.getLastRow();
    if (tabLast > 1) tab.getRange(2, 1, tabLast - 1, 16).clearContent();
    if (filtered.length > 0) tab.getRange(2, 1, filtered.length, 16).setValues(filtered);
  }

  return joinedRows.length;
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
 * Sheet C 01_Dashboard and sends a summary email to sam@bebang.ph only.
 * (Was sam+ian until 2026-04-21; Ian runs ops from the dashboard directly,
 * doesn't need the CEO-level digest.)
 *
 * Recipients:
 *   - sam@bebang.ph
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
      'sam@bebang.ph',
      subject,
      bodyLines.join('\n'),
      { name: 'BEI Receiving Bot' }
    );

    _logAudit(auditLog, 'sendCeoDailyEmail', 'cron', 0,
              'Digest_sent', 'OK', 'to sam@bebang.ph');
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

  // e.namedValues is keyed by form item title; e.values is array in item order.
  // Form items post-S215-Phase-3 (Material Code dropdown added at position 3):
  //   Warehouse, PO Number, SI Number, Material Code, Upload SI Copy, SI Date,
  //   Amount (PHP), Notes
  let warehouse = '', poNumber = '', siNumber = '', materialCode = '';
  let siDate = '', amount = '', siPdfLink = '', notes = '';

  if (e && e.namedValues) {
    const nv = e.namedValues;
    const first = function(key) {
      const v = nv[key];
      return v && v.length ? v[0] : '';
    };
    warehouse = first('Warehouse');
    poNumber = first('PO Number');
    siNumber = first('SI Number');
    materialCode = first('Material Code');
    siDate = first('SI Date');
    amount = first('Amount (PHP)');
    siPdfLink = first('Upload SI Copy') || first('SI PDF') || first('SI PDF Drive Link');
    notes = first('Notes');
  } else if (e && e.values) {
    // Fallback: positional (index 0 is Timestamp from form)
    warehouse = e.values[1] || '';
    poNumber = e.values[2] || '';
    siNumber = e.values[3] || '';
    materialCode = e.values[4] || '';
    siPdfLink = e.values[5] || '';
    siDate = e.values[6] || '';
    amount = e.values[7] || '';
    notes = e.values[8] || '';
  }

  // S215 Phase 3 (P3-T2): validate Material Code against 10_Full_Materials_Master.
  // Non-blocking — accepts the upload but logs mismatch to audit so Cayla can
  // chase the supplier if they're using an unlisted code.
  let materialCodeStatus = 'NOT_PROVIDED';
  if (materialCode) {
    const matMaster = masterSs.getSheetByName('10_Full_Materials_Master');
    if (matMaster) {
      const matData = matMaster.getRange(2, 2, Math.max(0, matMaster.getLastRow() - 1), 1).getValues();
      const normMat = String(materialCode).trim().toUpperCase();
      let found = false;
      for (let i = 0; i < matData.length; i++) {
        if (String(matData[i][0] || '').trim().toUpperCase() === normMat) {
          found = true;
          break;
        }
      }
      materialCodeStatus = found ? 'MATCHED' : 'UNLISTED';
      if (!found) {
        _logAudit(auditLog, 'SI_UPLOAD_MATERIAL_CODE_MISMATCH', materialCode, 0,
                  'po=' + poNumber + '_si=' + siNumber + '_code=' + materialCode,
                  'WARN', 'Material Code not found in 10_Full_Materials_Master — accepted anyway');
      }
    }
  }

  // Phase 14: derive Supplier Name from PO via Sheet C 08_Full_Open_POs lookup.
  // Never trust / don't expose a supplier-facing list; supplier types only
  // what's on their own PO + SI.
  let supplierName = '';
  let supplierLookupStatus = 'NO_LOOKUP';
  if (poNumber) {
    const normPoForLookup = String(poNumber).trim().toUpperCase();
    const openPoSheet = masterSs.getSheetByName('08_Full_Open_POs');
    const openPoData = openPoSheet.getDataRange().getValues();
    // headers: PO Number, PO Date, Supplier Code, Supplier Name, Destination 3PL,
    //          Total Amount, Balance, Delivery Needed By, Status
    for (let i = 1; i < openPoData.length; i++) {
      const rowPo = String(openPoData[i][0] || '').trim().toUpperCase();
      if (rowPo === normPoForLookup) {
        supplierName = String(openPoData[i][3] || '').trim();
        supplierLookupStatus = 'FOUND_IN_OPEN_POS';
        break;
      }
    }
    if (!supplierName) {
      supplierName = 'UNKNOWN — PO not in Open POs master';
      supplierLookupStatus = 'PO_NOT_FOUND';
    }
  } else {
    supplierName = 'UNKNOWN — no PO provided';
    supplierLookupStatus = 'NO_PO';
  }

  const timestamp = new Date();

  // Attempt match by (PO#, SI#) — normalize whitespace + case.
  // Phase 10: match ALL consolidated rows with the same (PO#, SI#), not just
  // the first. Multi-line deliveries create N consolidated rows sharing the
  // PO#/SI#; every one must be tagged SI_Matched when the supplier uploads.
  // Phase 15: normalize both sides before comparing so PO-2026-1234 ==
  // 2026-1234 == 20261234. Same for SI. Loose matching prevents orphans
  // from format variance.
  const normPo = _normalizePo(poNumber);
  const normSi = _normalizeSi(siNumber);

  const matchedConsolidatedRows = [];  // [{ rowIdx, rr }]
  if (normPo && normSi) {
    const data = consolidated.getDataRange().getValues();
    // col indexes (0-based in data): 3=RR, 4=PO, 10=SI Number
    for (let i = 1; i < data.length; i++) {
      if (_normalizePo(data[i][4]) === normPo &&
          _normalizeSi(data[i][10]) === normSi) {
        matchedConsolidatedRows.push({ rowIdx: i + 1, rr: data[i][3] });
      }
    }
  }

  const matchStatus = matchedConsolidatedRows.length > 0 ? 'MATCHED' : 'ORPHAN';
  const matchedRRList = matchedConsolidatedRows.map(function(m) { return m.rr; }).join(',');

  // Write into 03_Supplier_SI_Uploads (12 cols post-Phase-12, Warehouse at col C)
  siUploads.appendRow([
    timestamp, supplierName, warehouse, poNumber, siNumber, siDate,
    amount, siPdfLink, notes, matchStatus, matchedRRList,
    matchedConsolidatedRows.length > 0 ? timestamp : '',
  ]);

  if (matchedConsolidatedRows.length > 0) {
    // Tag EVERY matched DR row in consolidated:
    // col T = SI_Matched (20), col U = SI_Upload_Link (21), col V = SI_Match_Timestamp (22)
    for (const m of matchedConsolidatedRows) {
      consolidated.getRange(m.rowIdx, 20).setValue(true);
      consolidated.getRange(m.rowIdx, 21).setValue(siPdfLink);
      consolidated.getRange(m.rowIdx, 22).setValue(timestamp);
    }

    // Also tag EVERY matching Pending GR row (same multi-line fix)
    const pending = masterSs.getSheetByName('06_Pending_GR');
    const pendingData = pending.getDataRange().getValues();
    let pendingTagged = 0;
    for (let i = 1; i < pendingData.length; i++) {
      if (_normalizePo(pendingData[i][3]) === normPo &&
          _normalizeSi(pendingData[i][9]) === normSi) {
        // Update SI PDF Link (col 11 = K, 1-based index 11)
        pending.getRange(i + 1, 11).setValue(siPdfLink);
        pending.getRange(i + 1, 12).setValue('READY');
        pendingTagged++;
      }
    }

    _logAudit(auditLog, 'handleSiUpload', supplierName, matchedConsolidatedRows.length,
              'SI_matched_' + matchedConsolidatedRows.length + '_DR_rows', 'OK',
              'PO=' + poNumber + ' SI=' + siNumber + ' warehouse=' + warehouse +
              ' supplierLookup=' + supplierLookupStatus +
              ' RRs=' + matchedRRList + ' pendingTagged=' + pendingTagged);
  } else {
    // Orphan: write to 04_Match_Queue (12 cols post-Phase-12, Warehouse at col D)
    matchQueue.appendRow([
      timestamp, 'Orphan SI — no matching DR found',
      supplierName, warehouse, poNumber, siNumber, siDate, amount, siPdfLink,
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
// Cleanup — remove any leftover Apps Script triggers (Phase 8 replaces them)
// ========================================================================

/**
 * removeAllTriggers — optional cleanup. With the Phase 8 Cloud Scheduler
 * switch, no Apps Script triggers are needed. If any were installed by a
 * pre-Phase-8 setup() run, this removes them. Safe to skip on fresh deploys.
 */
function removeAllTriggers() {
  const existing = ScriptApp.getProjectTriggers();
  let removed = 0;
  for (const t of existing) {
    ScriptApp.deleteTrigger(t);
    removed++;
  }
  console.log('removeAllTriggers: removed ' + removed);
  return { removed: removed };
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
