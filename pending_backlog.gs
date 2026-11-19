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
// 2. AUTOMATIC: run PBL_installTrigger() once from the editor. The backlog
//    is then rebuilt every day at about 6 AM (script time zone) with no
//    clicks. Long runs continue themselves in 1-minute steps.
//    MANUAL (any time): run PBL_showDialog() and press "Start"
//    (or add .addItem("Build Pending Backlog", "PBL_showDialog") to onOpen).
// 3. Make sure the "Pending Backlog" tab is synced to Supabase as the
//    table pending_backlog (same sync as the other tabs).
//
// The automatic run builds the new data in a temporary sheet and replaces
// "Pending Backlog" in one step at the end, so the dashboard never sees a
// half-built list.
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


// Step 2 (manual dialog): calculate one small batch and append to the sheet.
function PBL_processBatch(employeeNames) {
  return PBL_processBatch_(employeeNames, PBL_getSheet_(), PBL_stamp_());
}


function PBL_stamp_() {
  return Utilities.formatDate(
    new Date(),
    Session.getScriptTimeZone(),
    "dd/MM/yyyy HH:mm"
  );
}


function PBL_processBatch_(employeeNames, sheet, updatedOn) {
  MDB_resetExecutionCache_();

  const names = Array.isArray(employeeNames)
    ? employeeNames.slice(0, PBL_BATCH_SIZE)
    : [];

  const rangeEnd = PBL_endOfToday_();

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
                const summary = 'Employees: ' + names.length
                  + '\\nPending rows written: ' + rows
                  + (errors.length ? '\\n\\nErrors:\\n' + errors.join('\\n') : '');
                status('Sheet done. Sending to Supabase...');
                google.script.run
                  .withSuccessHandler(function(msg){
                    status('Completed.\\n\\n' + summary + '\\n\\n' + msg);
                    document.getElementById('run').disabled = false;
                  })
                  .withFailureHandler(function(e){
                    status('Sheet done, but Supabase push failed:\\n' + e.message
                      + '\\n\\n' + summary);
                    document.getElementById('run').disabled = false;
                  })
                  .PBL_pushToSupabase();
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


// ============================================================
// AUTOMATIC DAILY RUN
// ============================================================

const PBL_TEMP_SHEET_NAME = "Pending Backlog Build";
const PBL_TIME_BUDGET_MS = 4.5 * 60 * 1000; // stay below the 6 minute limit
const PBL_STATE_KEY = "PBL_STATE";


// Run this ONCE: creates the daily trigger (about 6 AM script time).
function PBL_installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === "PBL_autoRun") ScriptApp.deleteTrigger(t);
  });

  ScriptApp.newTrigger("PBL_autoRun")
    .timeBased()
    .everyDays(1)
    .atHour(6)
    .create();

  MDB_alert("Pending Backlog will now rebuild automatically every day at about 6 AM.");
}


// Optional: stop the automatic run.
function PBL_removeTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    const name = t.getHandlerFunction();
    if (name === "PBL_autoRun" || name === "PBL_autoContinue") {
      ScriptApp.deleteTrigger(t);
    }
  });
  PropertiesService.getScriptProperties().deleteProperty(PBL_STATE_KEY);
}


function PBL_autoContinue() {
  PBL_autoRun();
}


function PBL_clearContinueTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === "PBL_autoContinue") ScriptApp.deleteTrigger(t);
  });
}


function PBL_scheduleContinue_(minutes) {
  PBL_clearContinueTriggers_();
  ScriptApp.newTrigger("PBL_autoContinue")
    .timeBased()
    .after(minutes * 60 * 1000)
    .create();
}


function PBL_autoRun() {
  const lock = LockService.getScriptLock();

  if (!lock.tryLock(10000)) return; // another run is active

  const props = PropertiesService.getScriptProperties();
  const started = Date.now();

  try {
    PBL_clearContinueTriggers_();

    let state = null;

    try {
      state = JSON.parse(props.getProperty(PBL_STATE_KEY) || "null");
    } catch (e) {
      state = null;
    }

    // Start fresh when there is no run, or the old one is stuck (> 3 h).
    if (!state || (Date.now() - state.startedAt) > 3 * 60 * 60 * 1000) {

      MDB_resetExecutionCache_();

      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const old = ss.getSheetByName(PBL_TEMP_SHEET_NAME);
      if (old) ss.deleteSheet(old);

      const temp = ss.insertSheet(PBL_TEMP_SHEET_NAME);
      temp.getRange(1, 1, 1, PBL_HEADERS.length).setValues([PBL_HEADERS]);
      temp.getRange(2, 3, Math.max(temp.getMaxRows() - 1, 1), 2).setNumberFormat("@");
      temp.hideSheet();

      state = {
        names: MDB_getEmployeeNames_(),
        offset: 0,
        startedAt: Date.now(),
        updatedOn: PBL_stamp_(),
        retries: 0
      };

      props.setProperty(PBL_STATE_KEY, JSON.stringify(state));
    }

    const temp = SpreadsheetApp.getActiveSpreadsheet()
      .getSheetByName(PBL_TEMP_SHEET_NAME);

    if (!temp) {
      props.deleteProperty(PBL_STATE_KEY);
      return;
    }

    while (
      state.offset < state.names.length
      && (Date.now() - started) < PBL_TIME_BUDGET_MS
    ) {
      const batch = state.names.slice(state.offset, state.offset + PBL_BATCH_SIZE);

      const result = PBL_processBatch_(batch, temp, state.updatedOn);

      if (result.errors && result.errors.length) {
        console.warn("Pending Backlog: " + result.errors.join(" | "));
      }

      state.offset += batch.length;
      props.setProperty(PBL_STATE_KEY, JSON.stringify(state));
    }

    if (state.offset < state.names.length) {
      PBL_scheduleContinue_(1); // continue in a fresh execution
      return;
    }

    PBL_publishTemp_(temp);
    props.deleteProperty(PBL_STATE_KEY);

  } catch (error) {
    console.error("Pending Backlog auto run failed: " + error.message);

    let state = null;
    try {
      state = JSON.parse(props.getProperty(PBL_STATE_KEY) || "null");
    } catch (e) {}

    // Retry a few times, then give up until the next daily run.
    if (state && (state.retries || 0) < 3) {
      state.retries = (state.retries || 0) + 1;
      props.setProperty(PBL_STATE_KEY, JSON.stringify(state));
      PBL_scheduleContinue_(5);
    } else {
      props.deleteProperty(PBL_STATE_KEY);
    }

  } finally {
    lock.releaseLock();
  }
}


// Replace the live sheet with the finished temporary result in one step.
function PBL_publishTemp_(temp) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const live = PBL_getSheet_();

  const lastRow = temp.getLastRow();
  const rows = lastRow > 1
    ? temp.getRange(2, 1, lastRow - 1, PBL_HEADERS.length).getValues()
    : [];

  live.getRange(1, 1, 1, PBL_HEADERS.length)
    .setValues([PBL_HEADERS])
    .setFontWeight("bold")
    .setBackground("#1a3f6f")
    .setFontColor("#ffffff");
  live.setFrozenRows(1);

  const liveLast = live.getLastRow();
  if (liveLast > 1) {
    live.getRange(2, 1, liveLast - 1, PBL_HEADERS.length).clearContent();
  }

  if (rows.length > 0) {
    if (live.getMaxRows() < rows.length + 1) {
      live.insertRowsAfter(live.getMaxRows(), rows.length + 1 - live.getMaxRows());
    }
    live.getRange(2, 3, rows.length, 2).setNumberFormat("@");
    live.getRange(2, 1, rows.length, PBL_HEADERS.length).setValues(rows);
  }

  SpreadsheetApp.flush();
  ss.deleteSheet(temp);

  // Send the fresh data to Supabase (table pending_backlog).
  try {
    PBL_pushToSupabase();
  } catch (error) {
    console.error("Pending Backlog push to Supabase failed: " + error.message);
  }
}


// ============================================================
// PUSH THE "Pending Backlog" SHEET TO SUPABASE
//
// Writes the sheet into the table public.pending_backlog using the
// same layout as the other synced tabs:
//   sheet_row = sheet row number, col_a .. col_f = columns A .. F
// Row 1 (header) is stored as sheet_row 1. Rows that no longer exist
// in the sheet are deleted, so the table always equals the sheet.
// Uses SupabaseSync_getConfig() from the existing sync
// (SUPABASE_URL + key in Script Properties). The key must be allowed
// to write (service role), as for the other synced tabs.
// ============================================================

function PBL_pushToSupabase() {
  const config = SupabaseSync_getConfig();
  const sheet = PBL_getSheet_();

  const lastRow = Math.max(sheet.getLastRow(), 1);
  const values = sheet
    .getRange(1, 1, lastRow, PBL_HEADERS.length)
    .getDisplayValues();

  const records = values.map(function(row, i) {
    return {
      sheet_row: i + 1,
      col_a: String(row[0] || ""),
      col_b: String(row[1] || ""),
      col_c: String(row[2] || ""),
      col_d: String(row[3] || ""),
      col_e: String(row[4] || ""),
      col_f: String(row[5] || "")
    };
  });

  const headers = {
    apikey: config.key,
    Authorization: "Bearer " + config.key
  };

  // 1) insert / update every sheet row (in chunks)
  const CHUNK = 500;

  for (let i = 0; i < records.length; i += CHUNK) {
    const res = UrlFetchApp.fetch(
      config.baseUrl + "/rest/v1/pending_backlog?on_conflict=sheet_row",
      {
        method: "post",
        contentType: "application/json",
        headers: Object.assign({
          Prefer: "resolution=merge-duplicates,return=minimal"
        }, headers),
        payload: JSON.stringify(records.slice(i, i + CHUNK)),
        muteHttpExceptions: true
      }
    );

    if (res.getResponseCode() >= 300) {
      throw new Error(
        "Supabase insert failed (" + res.getResponseCode() + "): "
        + res.getContentText().slice(0, 300)
      );
    }
  }

  // 2) remove rows that are no longer in the sheet
  const del = UrlFetchApp.fetch(
    config.baseUrl + "/rest/v1/pending_backlog?sheet_row=gt." + lastRow,
    {
      method: "delete",
      headers: Object.assign({ Prefer: "return=minimal" }, headers),
      muteHttpExceptions: true
    }
  );

  if (del.getResponseCode() >= 300) {
    throw new Error(
      "Supabase cleanup failed (" + del.getResponseCode() + "): "
      + del.getContentText().slice(0, 300)
    );
  }

  return "Supabase updated: " + (lastRow - 1) + " pending row(s).";
}
