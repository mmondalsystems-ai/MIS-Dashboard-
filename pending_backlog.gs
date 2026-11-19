// ============================================================
// PENDING BACKLOG  (standalone add-on - touches NO existing function)
//
// Purpose: builds the "Pending Backlog" sheet used by the department
// admins' Monthly Score view (carry-forward of unfinished work).
//
// How it works
// - It re-uses the existing scoring engine TEMP_calculateEmployeeForWeek
//   (read only) for ONE long range: PBL_START_DATE -> end of today.
//   Every special rule (Purchase FMS routing, IMS allow-list, Orchard
//   Avaasa exclusion, Help Ticket, Demand Follow-up, CRM filters) is
//   therefore identical to the normal dashboard.
// - Items whose planned date is in the range and whose Actual date is
//   still blank are "pending as of today". An item that was finished
//   later (even late) is NOT pending any more, so the carry-forward
//   is always up to date.
// - One row per pending item is written to the "Pending Backlog" sheet:
//     A Employee | B Task | C Planned Date (dd/mm/yyyy) | D Month (yyyy-mm)
//     E Detail   | F Updated On
//
// Setup
// 1. Paste this file into the spreadsheet's Apps Script project.
// 2. Run PBL_showDialog() once from the editor (or add the line
//      .addItem("Build Pending Backlog", "PBL_showDialog")
//    to your existing onOpen menu) and press "Start".
// 3. Make sure the "Pending Backlog" tab is synced to Supabase as the
//    table pending_backlog (same sync as the other tabs).
// ============================================================

const PBL_SHEET_NAME = "Pending Backlog";

// First month that counts for the carry-forward (Aug 1, 2026).
// Change this date if the carry-forward should start from another month.
const PBL_START_DATE = new Date(2026, 7, 1, 0, 0, 0, 0);

const PBL_BATCH_SIZE = 3;

const PBL_HEADERS = [
  "Employee",
  "Task",
  "Planned Date",
  "Month",
  "Detail",
  "Updated On"
];


function PBL_getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(PBL_SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(PBL_SHEET_NAME);
  return sheet;
}


function PBL_endOfToday_() {
  const d = new Date();
  d.setHours(23, 59, 59, 999);
  return d;
}


// Step 1: prepare the sheet and return the employee list.
function PBL_prepare() {
  MDB_resetExecutionCache_();

  const sheet = PBL_getSheet_();

  sheet.getRange(1, 1, 1, PBL_HEADERS.length)
    .setValues([PBL_HEADERS])
    .setFontWeight("bold")
    .setBackground("#1a3f6f")
    .setFontColor("#ffffff");

  // Dates and months must stay plain text.
  const maxRows = sheet.getMaxRows();
  sheet.getRange(2, 3, Math.max(maxRows - 1, 1), 2).setNumberFormat("@");

  // Remove the previous result (only this sheet's own data rows).
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, PBL_HEADERS.length).clearContent();
  }

  sheet.setFrozenRows(1);

  return {
    success: true,
    employees: MDB_getEmployeeNames_()
  };
}


// Step 2: calculate one small batch of employees and append the rows.
function PBL_processBatch(employeeNames) {
  MDB_resetExecutionCache_();

  const names = Array.isArray(employeeNames)
    ? employeeNames.slice(0, PBL_BATCH_SIZE)
    : [];

  const sheet = PBL_getSheet_();
  const rangeEnd = PBL_endOfToday_();
  const updatedOn = Utilities.formatDate(
    new Date(),
    Session.getScriptTimeZone(),
    "dd/MM/yyyy HH:mm"
  );

  const rows = [];
  const errors = [];

  names.forEach(function(name) {
    try {
      const res = TEMP_calculateEmployeeForWeek(
        name,
        PBL_START_DATE,
        rangeEnd,
        true
      );

      if (!res || !res.taskScoreMap) return;

      Object.keys(res.taskScoreMap).forEach(function(task) {
        const pending = res.taskScoreMap[task].notDone || [];

        pending.forEach(function(detail) {
          // Every notDone text contains the planned date as dd/mm/yyyy
          // (Help Ticket: "ID - dd/mm/yyyy - issue").
          const match = String(detail).match(/(\d{2})\/(\d{2})\/(\d{4})/);
          if (!match) return;

          rows.push([
            name,
            task,
            match[1] + "/" + match[2] + "/" + match[3],
            match[3] + "-" + match[2],
            String(detail),
            updatedOn
          ]);
        });
      });
    } catch (error) {
      errors.push(name + ": " + error.message);
    }
  });

  if (rows.length > 0) {
    const start = Math.max(sheet.getLastRow(), 1) + 1;
    const needed = start + rows.length - 1;
    if (sheet.getMaxRows() < needed) {
      sheet.insertRowsAfter(sheet.getMaxRows(), needed - sheet.getMaxRows());
    }
    const target = sheet.getRange(start, 1, rows.length, PBL_HEADERS.length);
    sheet.getRange(start, 3, rows.length, 2).setNumberFormat("@");
    target.setValues(rows);
  }

  return {
    employees: names.length,
    rows: rows.length,
    errors: errors
  };
}


// Dialog that runs prepare + batches (same pattern as Employee Score Popup).
function PBL_showDialog() {
  const html = `<!doctype html><html><head><style>
    body{font-family:Arial,sans-serif;padding:16px;background:#f5f7fb;color:#173052}
    h3{margin:0 0 10px}p{font-size:12px;line-height:1.5}
    #status{white-space:pre-wrap;background:#fff;border:1px solid #ddd;
      border-radius:8px;padding:12px;min-height:90px;font-size:12px}
    button{background:#1a3f6f;color:#fff;border:0;border-radius:7px;
      padding:10px 14px;margin-top:12px;cursor:pointer;width:100%}
    button:disabled{opacity:.5;cursor:default}
  </style></head><body>
    <h3>Build Pending Backlog</h3>
    <p>Collects every unfinished item since ${Utilities.formatDate(
      PBL_START_DATE, Session.getScriptTimeZone(), "dd/MM/yyyy")} for all employees.</p>
    <div id="status">Ready to start.</div>
    <button id="run" onclick="start()">Start</button>
    <script>
      const batchSize = ${PBL_BATCH_SIZE};
      function status(t){document.getElementById('status').innerText=t;}
      function start(){
        document.getElementById('run').disabled = true;
        status('Preparing sheet...');
        google.script.run
          .withSuccessHandler(function(prepared){
            const names = prepared.employees || [];
            let offset = 0, rows = 0, errors = [];
            function next(){
              if (offset >= names.length) {
                status('Completed.\\n\\nEmployees: ' + names.length
                  + '\\nPending rows written: ' + rows
                  + (errors.length ? '\\n\\nErrors:\\n' + errors.join('\\n') : ''));
                document.getElementById('run').disabled = false;
                return;
              }
              const batch = names.slice(offset, offset + batchSize);
              status('Calculating ' + (offset + 1) + '-' + (offset + batch.length)
                + ' / ' + names.length);
              google.script.run
                .withSuccessHandler(function(r){
                  rows += r.rows || 0;
                  (r.errors || []).forEach(function(e){ errors.push(e); });
                  offset += batch.length; next();
                })
                .withFailureHandler(function(e){
                  errors.push(batch.join(', ') + ': ' + e.message);
                  offset += batch.length; next();
                })
                .PBL_processBatch(batch);
            }
            next();
          })
          .withFailureHandler(function(e){
            status('Failed: ' + e.message);
            document.getElementById('run').disabled = false;
          })
          .PBL_prepare();
      }
    <\/script></body></html>`;

  SpreadsheetApp.getUi().showModelessDialog(
    HtmlService.createHtmlOutput(html).setWidth(380).setHeight(300),
    "Build Pending Backlog"
  );
}
