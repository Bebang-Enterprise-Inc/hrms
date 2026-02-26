const SPREADSHEET_ID = '1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Sales Model')
    .addItem('Refresh Model Now', 'refreshSalesModel')
    .addItem('Install 15-min Auto Refresh', 'installRefreshTrigger')
    .addItem('Remove Auto Refresh Triggers', 'removeRefreshTriggers')
    .addSeparator()
    .addItem('Write Model Health Snapshot', 'writeModelHealthSnapshot')
    .addToUi();
}

function refreshSalesModel() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const now = new Date();

  SpreadsheetApp.flush();

  const dq = ss.getSheetByName('DATA_QUALITY');
  if (dq) {
    dq.getRange('D1').setValue('last_refresh_at');
    dq.getRange('D2').setValue(now);
    dq.getRange('D2').setNumberFormat('yyyy-mm-dd hh:mm:ss');
    dq.getRange('E1').setValue('refreshed_by');
    dq.getRange('E2').setValue(Session.getEffectiveUser().getEmail() || 'unknown');
  }

  const sa = ss.getSheetByName('SUMMARY_AUTO');
  if (sa) {
    sa.getRange('J1').setValue('last_refresh_at');
    sa.getRange('J2').setValue(now);
    sa.getRange('J2').setNumberFormat('yyyy-mm-dd hh:mm:ss');
    sa.getRange('K1').setValue('refreshed_by');
    sa.getRange('K2').setValue(Session.getEffectiveUser().getEmail() || 'unknown');
  }

  writeModelHealthSnapshot();
  SpreadsheetApp.flush();
}

function installRefreshTrigger() {
  removeRefreshTriggers();
  ScriptApp.newTrigger('refreshSalesModel')
    .timeBased()
    .everyMinutes(15)
    .create();
  refreshSalesModel();
}

function removeRefreshTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach((t) => {
    if (t.getHandlerFunction() === 'refreshSalesModel') {
      ScriptApp.deleteTrigger(t);
    }
  });
}

function writeModelHealthSnapshot() {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const dq = ss.getSheetByName('DATA_QUALITY');
  if (!dq) return;

  const checks = [
    ['has_FP_CLEAN', !!ss.getSheetByName('FP_CLEAN')],
    ['has_BEBANG_CLEAN', !!ss.getSheetByName('BEBANG_CLEAN')],
    ['has_SALES_FACT_DAILY', !!ss.getSheetByName('SALES_FACT_DAILY')],
    ['has_SUMMARY_AUTO', !!ss.getSheetByName('SUMMARY_AUTO')],
    ['has_DASHBOARD', !!ss.getSheetByName('DASHBOARD')],
  ];

  dq.getRange('D4:E8').clearContent();
  dq.getRange(4, 4, checks.length, 2).setValues(checks);

  const fpClean = ss.getSheetByName('FP_CLEAN');
  const webClean = ss.getSheetByName('BEBANG_CLEAN');
  const fact = ss.getSheetByName('SALES_FACT_DAILY');

  const fpRows = fpClean ? Math.max(fpClean.getLastRow() - 1, 0) : 0;
  const webRows = webClean ? Math.max(webClean.getLastRow() - 1, 0) : 0;
  const factRows = fact ? Math.max(fact.getLastRow() - 1, 0) : 0;

  dq.getRange('D10').setValue('model_row_snapshot');
  dq.getRange('D11:E13').setValues([
    ['fp_clean_rows', fpRows],
    ['bebang_clean_rows', webRows],
    ['fact_rows', factRows],
  ]);
}
