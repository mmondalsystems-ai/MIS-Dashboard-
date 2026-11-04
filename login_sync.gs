// Run once from the spreadsheet's Apps Script: copies Users (username, default
// password, updated password) into the Supabase table login_users.
// Uses the same Script Properties as the existing sync (SUPABASE_URL, key).
function LoginSync_pushUsers() {
  var config = SupabaseSync_getConfig();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Login Details") || ss.getSheetByName("Users");
  if (!sheet) throw new Error("Login sheet not found");

  var last = sheet.getLastRow();
  if (last < 2) return;

  var data = sheet.getRange(2, 1, last - 1, 3).getDisplayValues();
  var rows = [];
  data.forEach(function(r) {
    var name = String(r[0] || "").trim();
    if (!name) return;
    rows.push({
      username: name,
      default_password: String(r[1] || "").trim(),
      updated_password: String(r[2] || "").trim()
    });
  });

  var res = UrlFetchApp.fetch(config.baseUrl + "/rest/v1/login_users?on_conflict=username", {
    method: "post",
    contentType: "application/json",
    headers: {
      apikey: config.key,
      Authorization: "Bearer " + config.key,
      Prefer: "resolution=merge-duplicates,return=minimal"
    },
    payload: JSON.stringify(rows),
    muteHttpExceptions: true
  });
  Logger.log(res.getResponseCode() + " " + res.getContentText().slice(0, 300));
}
