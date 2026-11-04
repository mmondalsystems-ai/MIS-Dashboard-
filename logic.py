"""Ported from Code.gs. Same rules, same return shapes."""
import re
from datetime import date, timedelta
from db import get_values, get_columns, pool
from jsutil import s, parse_float, parse_int, to_fixed
from weeks import (clean_week_label, normalize_week_label, parse_week_start,
                   parse_week_range, week_label_current, week_block_starts, MON3)

ADMINS = {
    "SYSTEM TEAM": {"password": "@2003", "displayName": "System Team", "departmentFilter": True},
    "ADMIN2": {"password": "1234", "displayName": "Admin2", "departmentFilter": False},
    "ADMIN3": {"password": "1234", "displayName": "Admin3", "departmentFilter": False},
    "ADMIN4": {"password": "1234", "displayName": "Admin4", "departmentFilter": False},
}
MAX_WEEKS_IN_FILTER = 6
SKIP_NAMES = {"NAME", "DEPARTMENT", "TASK", "TOTAL SCORE"}


def norm_name(v):
    s = "" if v is None else str(v)
    return re.sub(r"\s+", " ", s.replace(" ", " ")).strip().upper()


def add_unique(seen, out, value):
    raw = re.sub(r"\s+", " ", ("" if value is None else str(value)).replace(" ", " ")).strip()
    key = norm_name(raw)
    if not raw or not key or key in SKIP_NAMES:
        return
    if key not in seen:
        seen[key] = raw
        out.append(raw)


def sort_names(lst):
    return sorted(lst, key=lambda s: s.casefold())


def cell(values, r, c):
    """1-based, blank when missing."""
    try:
        v = values[r - 1][c - 1]
    except IndexError:
        return ""
    return "" if v is None else v


# ---------------- login ----------------

def validateLogin(username, password):
    u = norm_name(username)
    if u in ADMINS:
        a = ADMINS[u]
        if str(password or "") == a["password"]:
            return {"success": True, "role": "admin", "displayName": a["displayName"],
                    "departmentFilter": bool(a["departmentFilter"])}
        return {"success": False, "message": "Wrong password!"}

    with pool().connection() as conn:
        rows = conn.execute(
            "select username, default_password, updated_password from public.login_users"
        ).fetchall()
    for r in rows:
        if norm_name(r["username"]) != u:
            continue
        default = str(r["default_password"] or "").strip()
        updated = str(r["updated_password"] or "").strip()
        valid = updated if updated != "" else default
        if str(password or "") == valid:
            return {"success": True, "role": "user", "displayName": str(r["username"] or "").strip()}
        return {"success": False, "message": "Wrong Password!"}
    return {"success": False, "message": "No User Found!"}


def changePassword(username, new_password):
    u = norm_name(username)
    with pool().connection() as conn:
        rows = conn.execute("select username from public.login_users").fetchall()
        for r in rows:
            if norm_name(r["username"]) == u:
                conn.execute(
                    "update public.login_users set updated_password=%s where username=%s",
                    (new_password, r["username"]))
                return {"success": True}
    return {"success": False, "message": "No User Found!"}


# ---------------- employees ----------------

def getLoginUsernames():
    with pool().connection() as conn:
        rows = conn.execute("select username from public.login_users").fetchall()
    seen, out = {}, []
    for r in rows:
        add_unique(seen, out, r["username"])
    return sort_names(out)


def _name_columns(table, header_row, offset):
    """Name columns of every week block, read with a column projection."""
    hv = get_values(table, rows=list(range(1, header_row + 1)))
    if not hv:
        return None, [], []
    cols = [c + offset for c, _ in week_block_starts(hv, header_row)]
    return hv, (get_columns(table, cols, len(hv[0])) if cols else []), cols


def getAllEmployees():
    seen, out = {}, []
    for name in getLoginUsernames():
        add_unique(seen, out, name)
    for table in ("checklist_ho", "checklist_site"):
        res = _name_columns(table, 2, 1)
        if res[0] is None:
            continue
        _, vals, cols = res
        for col in cols:
            for r in range(4, len(vals) + 1):
                add_unique(seen, out, cell(vals, r, col))
    res = _name_columns("fms_data", 1, 0)
    if res[0] is not None:
        _, vals, cols = res
        for col in cols:
            data = [cell(vals, r, col) for r in range(2, len(vals) + 1)]
            for i, val in enumerate(data):
                val = s(val).strip()
                if not val or norm_name(val) in ("TASK", "TOTAL SCORE"):
                    continue
                nxt = norm_name(data[i + 1]) if i + 1 < len(data) else ""
                if nxt == "TASK":
                    add_unique(seen, out, val)
    return sort_names(out)


# ---------------- shared helpers ----------------

CHECKLIST_TABLES = [("Checklist HO", "checklist_ho"), ("Checklist Site", "checklist_site")]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

SITE_EMPLOYEE_NAMES = [
    "DEBASHISH MAITY", "ABHIJIT MUKHERJEE", "PRADIP", "ASISH ADHIKARY", "SAIKAT SAMANTA",
    "UJJAL GAYEN", "MITHUN NANDI", "PARIKSHIT DEBNATH", "MITHUN BISWAS", "ANWAR MOLLA",
    "CHIRANJIT ADHIKARY", "RAJU ADHIKARY", "RAHUL MONDAL", "DIPEN PANDA", "LALAN THAKUR",
    "BIKASH HALDAR", "ATANU NANDY", "MASIDUR HAQUE", "ASIT CHOWDHURY", "BISWAJIT METE",
    "BISWANATH TAPADAR", "SOURAV MONDAL", "ARITRA KUMAR ROY", "ABHOY MONDAL",
    "SUBHODEEP NEOGI", "PRITAM HAZRA", "SUPRAVO SINGH", "RAKESH SINGH", "SUBRATA SEN",
    "SK. MOSIYAR RAHMAN", "BIBHAS", "PRAVAT MONDAL", "MRIGANKA SAHA", "NILADRI", "KUNAL",
    "SARAT CHATTERJEE", "CHINMOY SIT", "BAPPADITYA GHOSH", "RAGHUNATH HALDER", "SANTOSH DAS",
    "SUMAN PRADHAN", "CHIRANJIT CHAKRABORTTY", "ASHIM CHAKRABORTTY", "SUBHAJIT BAIDYA",
    "JOY HAZRA", "ASHIS HALDER", "SANDIP BHADRA", "SANTANU HALDAR",
]
HO_EMPLOYEE_NAMES = [
    "ARUP GAYEN", "DEEPAN MUKHERJEE", "MANISH MONDAL", "BHISHMADEV NASKAR",
    "ARINDAM CHOWDHURY", "SUMITRA DAS", "PRIYANKA AGARWAL", "SUDESHNA CHAKRABORTY",
    "SAYANTANI BOSE", "PRASANJIT BISWAS", "SME", "CRM", "LEEZA LAHA", "SUMAN MONDAL",
    "SHYAN DUTTA", "TIASHA DAS", "SUTAPA ROY", "TANMAY CHATTERJEE", "SOMSUBHRA MAJUMDER",
    "SWARUP MUKHERJEE", "ABHIRUP HATAI", "AMAR SHARMA", "SANDIP DAS", "SUBHAJIT CHAKRABORTY",
    "RANIT DAS", "ANAND SHAW", "TULIKA SAHA", "RISHABH PRAJAPATI", "MOUMITA SASMAL",
    "SRISTI DEY", "BHARTI TRIPATHI", "BHARTI (Admin)", "MANJARIKA DATTA", "BONDITA PHUKON",
    "SHRAYASHI SARKAR", "DEBASHREE BHAKAT", "PIYALI SAHA DAS", "KAUSIK GHOSH",
    "ABHRADEEP SINHA", "DEBASISH NATH", "SOURAV MONDAL", "ATANU JANA", "RAJAT DAS DEY",
]
PSF_ALLOWED = {"SAYANTANI BOSE": True, "SUDESHNA CHAKRABORTY": True, "LEEZA LAHA": True}
FMS_OVERTIME_PENALTY_WEIGHT = 1.00


def last_col(values):
    return len(values[0]) if values and values[0] else 0


def find_week_block_start(values, header_row, week_label):
    if not values or last_col(values) < 1:
        return None
    headers = values[header_row - 1] if len(values) >= header_row else []
    wanted = normalize_week_label(week_label)
    for c, v in enumerate(headers):
        v = s(v).strip()
        if v and normalize_week_label(v) == wanted:
            return c + 1
    return None


def week_values(table, header_row, week_label, block_width):
    """Header rows + only the columns of the selected week (same 2D shape as the sheet)."""
    hv = get_values(table, rows=list(range(1, header_row + 1)))
    if not hv:
        return hv
    start = find_week_block_start(hv, header_row, week_label)
    if start is None:
        return hv
    width = last_col(hv)
    blk = get_columns(table, list(range(start, start + block_width)), width)
    if not blk:
        return hv
    for r in range(min(header_row, len(blk))):
        for c in range(width):
            if hv[r][c] != "":
                blk[r][c] = hv[r][c]
    return blk


def checklist_week_values(sh_name, week):
    table = dict(CHECKLIST_TABLES).get(sh_name)
    return week_values(table, 2, week, 5) if table else None


def fms_week_values(week):
    return week_values("fms_data", 1, week, 6)


def monthly_fms_week_values(period):
    return week_values("monthly_fms_data", 1, period, 6)


def slice_values(values, row, col, num_rows, num_cols):
    out = []
    for r in range(num_rows):
        src = values[row - 1 + r] if 0 <= row - 1 + r < len(values) else []
        line = []
        for c in range(num_cols):
            i = col - 1 + c
            v = src[i] if 0 <= i < len(src) else ""
            line.append("" if v is None else v)
        out.append(line)
    return out


def resolve_week_label(week_label):
    supplied = clean_week_label(week_label)
    if supplied:
        return supplied
    info = getAvailableWeeks()
    return info["defaultWeek"] or week_label_current()


def is_fms_employee_header_row(data, idx):
    val = s(data[idx][0]).strip()
    if not val:
        return False
    key = norm_name(val)
    if key in ("TASK", "TOTAL SCORE"):
        return False
    nxt = norm_name(data[idx + 1][0]) if idx + 1 < len(data) else ""
    return nxt == "TASK"


# ---------------- weeks ----------------

def getAvailableWeeks():
    found = {}

    def collect(values, header_row):
        for _, label in week_block_starts(values, header_row):
            key = normalize_week_label(label)
            if key not in found:
                found[key] = {"label": label, "time": parse_week_start(label)}

    collect(get_values("checklist_ho", rows=[1, 2]), 2)
    collect(get_values("checklist_site", rows=[1, 2]), 2)
    collect(get_values("fms_data", rows=[1]), 1)

    items = sorted(found.values(), key=lambda x: x["time"], reverse=True)[:MAX_WEEKS_IN_FILTER]
    weeks = [x["label"] for x in items]
    current = week_label_current()
    cur_norm = normalize_week_label(current)
    default = weeks[0] if weeks else current
    for w in weeks:
        if normalize_week_label(w) == cur_norm:
            default = w
            break
    return {"weeks": weeks, "defaultWeek": default}


def get_all_available_weeks():
    found = {}

    def collect(values, header_row):
        for _, label in week_block_starts(values, header_row):
            label = clean_week_label(label)
            key = normalize_week_label(label)
            if key not in found:
                found[key] = {"label": label, "time": parse_week_start(label)}

    collect(get_values("checklist_ho", rows=[1, 2]), 2)
    collect(get_values("checklist_site", rows=[1, 2]), 2)
    collect(get_values("fms_data", rows=[1]), 1)

    big = float("inf")

    def k(x):
        t = x["time"] if x["time"] > 0 else big
        return (t, x["label"].casefold())

    return [x["label"] for x in sorted(found.values(), key=k)]


# ---------------- department directory ----------------

def getDepartmentDirectory():
    result = {"success": True, "sheetFound": False, "sheetName": "", "departments": [],
              "byDepartment": {}, "rowCount": 0, "message": ""}
    try:
        dv = get_values("department")
    except Exception as e:
        result.update(success=False, message="Department data could not be read: " + str(e))
        return result
    if dv is None:
        result.update(success=False, message="Department sheet not found.")
        return result
    result["sheetFound"] = True
    result["sheetName"] = "Department"
    if len(dv) < 1 or last_col(dv) < 2:
        result.update(success=False, message="Department sheet has no Department/Name data.")
        return result

    display, seen = {}, {}
    for row in slice_values(dv, 1, 1, len(dv), 2):
        dept = re.sub(r"\s+", " ", s(row[0]).replace(" ", " ")).strip()
        name = re.sub(r"\s+", " ", s(row[1]).replace(" ", " ")).strip()
        if not dept or not name:
            continue
        dkey, nkey = norm_name(dept), norm_name(name)
        if dkey == "DEPARTMENT" and nkey == "NAME":
            continue
        if not dkey or not nkey:
            continue
        if re.match(r"^SITE\s*[12]$", dkey):
            dept, dkey = "Amritaya", "AMRITAYA"
        if dkey not in display:
            display[dkey] = dept
            result["byDepartment"][dkey] = []
            seen[dkey] = {}
        if nkey not in seen[dkey]:
            seen[dkey][nkey] = True
            result["byDepartment"][dkey].append(name)
            result["rowCount"] += 1

    for dkey in display:
        result["departments"].append({"key": dkey, "name": display[dkey]})
        result["byDepartment"][dkey].sort(key=lambda x: x.casefold())
    result["departments"].sort(key=lambda d: d["name"].casefold())
    if not result["departments"]:
        result.update(success=False, message="No valid Department/Name rows found in the Department sheet.")
    return result


# ---------------- employee data ----------------

def getChecklistData(employeeName, weekLabel):
    selected = resolve_week_label(weekLabel)
    result = {"ho": [], "site": [], "weekLabel": selected}
    wanted = norm_name(employeeName)
    for sh_name, _ in CHECKLIST_TABLES:
        vals = checklist_week_values(sh_name, selected)
        if not vals or len(vals) < 4:
            continue
        start = find_week_block_start(vals, 2, selected)
        if start is None or start + 4 > last_col(vals):
            continue
        data = slice_values(vals, 4, start, len(vals) - 3, 5)
        key = "ho" if sh_name == "Checklist HO" else "site"
        last_dept = last_name = ""
        for row in data:
            if all(s(v).strip() == "" for v in row):
                last_dept = last_name = ""
                continue
            dept_raw, name_raw = s(row[0]).strip(), s(row[1]).strip()
            part, n_date, n_pct = s(row[2]).strip(), s(row[3]).strip(), s(row[4]).strip()
            if dept_raw:
                last_dept = dept_raw
            if name_raw:
                last_name = name_raw
            dept = dept_raw or last_dept
            name = name_raw or last_name
            if not part:
                continue
            if norm_name(part) == "PARTICULARS":
                continue
            if wanted and norm_name(name) != wanted:
                continue
            result[key].append({"dept": dept, "name": name, "particular": part,
                                "notDoneDate": n_date, "notDonePct": n_pct})
    return result


def getFmsData(employeeName, weekLabel, values=None):
    selected = resolve_week_label(weekLabel)
    fms = values if values is not None else fms_week_values(selected)
    result = {"tasks": [], "total": None, "weekLabel": selected}
    if not fms or len(fms) < 2:
        return result
    start = find_week_block_start(fms, 1, selected)
    if start is None or start + 5 > last_col(fms):
        return result
    data = slice_values(fms, 2, start, len(fms) - 1, 6)
    wanted = norm_name(employeeName)
    in_block, block_name = False, ""
    for r in range(len(data)):
        val = s(data[r][0]).strip()
        key = norm_name(val)
        if is_fms_employee_header_row(data, r):
            block_name = val
            in_block = (norm_name(block_name) == wanted) if wanted else True
            continue
        if not in_block:
            continue
        if key == "TASK":
            continue
        if key == "TOTAL SCORE":
            parts = fms_score_parts(data[r][4], data[r][1], data[r][2], data[r][3])
            result["total"] = {
                "employeeName": block_name,
                "planned": s(data[r][1]).strip(), "actual": s(data[r][2]).strip(),
                "overTime": s(data[r][3]).strip(), "score": s(data[r][4]).strip(),
                "onTimeScore": parts["onTimeScore"], "notDoneScore": parts["notDoneScore"],
                "overTimeScore": parts["overTimeScore"], "finalScore": parts["finalScore"],
                "notDone": s(data[r][5]).strip(),
            }
            if wanted:
                break
            in_block = False
            continue
        if not val:
            continue
        result["tasks"].append({
            "employeeName": block_name, "task": val,
            "planned": s(data[r][1]).strip(), "actual": s(data[r][2]).strip(),
            "overTime": s(data[r][3]).strip(), "score": s(data[r][4]).strip(),
            "notDone": s(data[r][5]).strip(),
        })
    return result


def getEmployeeData(employeeName, weekLabel):
    selected = resolve_week_label(weekLabel)
    return {"checklist": getChecklistData(employeeName, selected),
            "fms": getFmsData(employeeName, selected),
            "weekLabel": selected}


# ---------------- monthly FMS ----------------

def getMonthlyFmsPeriods():
    hv = get_values("monthly_fms_data", rows=[1])
    if not hv or last_col(hv) < 1:
        return {"periods": [], "defaultPeriod": None}
    periods, seen = [], {}
    for v in hv[0]:
        label = clean_week_label(v)
        key = normalize_week_label(label)
        if label and key not in seen:
            seen[key] = True
            periods.append(label)
    periods.reverse()
    return {"periods": periods, "defaultPeriod": periods[0] if periods else None}


def getMonthlyEmployeeData(employeeName, periodLabel):
    label = clean_week_label(periodLabel)
    vals = monthly_fms_week_values(label)
    return {
        "checklist": {"ho": [], "site": [], "weekLabel": label},
        "fms": getFmsData(employeeName, label, vals) if vals is not None
        else {"tasks": [], "total": None, "weekLabel": label},
        "weekLabel": label,
    }


def monthly_fms_maps(period):
    return {"checklist": {}, "fms": fms_week_score_map(monthly_fms_week_values(period), period)}


# ---------------- FMS score math ----------------

def parse_fms_number(v):
    raw = s(v).replace(",", "").strip()
    if not raw or raw in ("—", "-"):
        return None
    return parse_float(raw)


def format_fms_percent(value, decimals=0):
    if value is None:
        return "—"
    places = max(0, int(decimals))
    if abs(value) < 0.5 / (10 ** places):
        value = 0
    return to_fixed(value, places) + "%"


def fms_not_done_count(planned_v, actual_v, over_v):
    planned = parse_fms_number(planned_v)
    actual = parse_fms_number(actual_v)
    over = parse_fms_number(over_v)
    if planned is None or planned <= 0:
        return 0
    actual = 0 if actual is None else max(0, actual)
    over = 0 if over is None else max(0, over)
    return max(0, planned - actual - over)


def fms_not_done_penalty(planned_v, actual_v, over_v):
    planned = parse_fms_number(planned_v)
    if planned is None or planned <= 0:
        return None
    nd = fms_not_done_count(planned_v, actual_v, over_v)
    return -((nd / planned) * 100)


def fms_over_time_penalty(planned_v, over_v):
    planned = parse_fms_number(planned_v)
    over = parse_fms_number(over_v)
    if planned is None or planned <= 0 or over is None:
        return None
    if over <= 0:
        return 0
    return -((over / planned) * 100 * FMS_OVERTIME_PENALTY_WEIGHT)


def over_time_score_text(planned_v, over_v):
    p = fms_over_time_penalty(planned_v, over_v)
    if p is None:
        return "—"
    if p == 0:
        return "0%"
    return format_fms_percent(p, 1)


def final_fms_score_text(source, planned_v, actual_v, over_v):
    planned = parse_fms_number(planned_v)
    if planned is None or planned <= 0:
        return "0"
    nd = fms_not_done_penalty(planned_v, actual_v, over_v)
    if nd is None:
        return "—"
    ot = fms_over_time_penalty(planned_v, over_v)
    return format_fms_percent(nd + (0 if ot is None else ot), 0)


def fms_score_parts(source, planned_v, actual_v, over_v):
    planned = parse_fms_number(planned_v)
    if planned is None or planned <= 0:
        return {"onTimeScore": "0", "notDoneScore": "0", "overTimeScore": "—", "finalScore": "0"}
    nd = fms_not_done_penalty(planned_v, actual_v, over_v)
    nd_score = "—" if nd is None else format_fms_percent(nd, 0)
    return {"onTimeScore": nd_score, "notDoneScore": nd_score,
            "overTimeScore": over_time_score_text(planned_v, over_v),
            "finalScore": final_fms_score_text(source, planned_v, actual_v, over_v)}


def num(v):
    """Number(x || 0) for the simple cases used here."""
    if v in (None, "", False):
        return 0
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def fms_score_text_from_map(entry):
    if not entry:
        return "0"
    if not (num(entry.get("planned")) > 0):
        return "0"
    if num(entry.get("taskCount")) == 0:
        return "0"
    return (entry.get("notDoneScore") or entry.get("onTimeScore") or
            fms_score_parts(entry.get("score"), entry.get("planned"), entry.get("actual"),
                            entry.get("overTime"))["notDoneScore"])


def fms_time_score_text_from_map(entry):
    if not entry:
        return "-"
    if not (num(entry.get("planned")) > 0):
        return "-"
    if num(entry.get("taskCount")) == 0:
        return "-"
    return (entry.get("overTimeScore") or
            fms_score_parts(entry.get("score"), entry.get("planned"), entry.get("actual"),
                            entry.get("overTime"))["overTimeScore"])


def is_real_percentage_score(v):
    raw = s(v).strip()
    if not raw.endswith("%"):
        return False
    return parse_float(raw.replace("%", "").strip()) is not None


def checklist_score_text_from_map(entry):
    if not entry or int(entry.get("taskCount") or 0) == 0:
        return "0"
    if not entry.get("hasScore"):
        return "0%"
    return to_fixed(entry.get("score") or 0, 0) + "%"


# ---------------- averages ----------------

def average_score_values(values):
    total, count, no_task = 0.0, 0, False
    for v in values or []:
        raw = s(v).strip()
        if raw == "0":
            no_task = True
            continue
        if not is_real_percentage_score(raw):
            continue
        total += parse_float(raw.replace("%", "").strip())
        count += 1
    if count > 0:
        return to_fixed(total / count, 0) + "%"
    return "0" if no_task else "—"


def average_time_score_values(values):
    total, count, no_fms = 0.0, 0, False
    for v in values or []:
        raw = s(v).strip()
        if raw in ("-", "—", "0"):
            no_fms = True
            continue
        if not is_real_percentage_score(raw):
            continue
        total += parse_float(raw.replace("%", "").strip())
        count += 1
    if count > 0:
        return to_fixed(total / count, 0) + "%"
    return "-" if no_fms else "—"


def quantity_score_text(checklist_score, fms_score):
    return average_score_values([checklist_score, fms_score])


def average_monthly_score_values(values):
    lst = values or []
    if not lst:
        return "—"
    total = 0.0
    for v in lst:
        raw = s(v).strip()
        if is_real_percentage_score(raw):
            total += parse_float(raw.replace("%", "").strip())
    return to_fixed(total / len(lst), 0) + "%"


def average_monthly_time_score_values(values):
    lst = values or []
    if not lst:
        return "-"
    total, any_real = 0.0, False
    for v in lst:
        raw = s(v).strip()
        if is_real_percentage_score(raw):
            total += parse_float(raw.replace("%", "").strip())
            any_real = True
    if not any_real:
        return "-"
    return to_fixed(total / len(lst), 0) + "%"


# ---------------- score maps ----------------

def count_not_done_dates(text):
    return len([d for d in (x.strip() for x in re.split(r"\r?\n", s(text))) if d and d not in ("—", "-")])


def checklist_week_score_map(values, week_label):
    out = {}
    if not values or len(values) < 4:
        return out
    start = find_week_block_start(values, 2, week_label)
    if start is None or start + 4 > last_col(values):
        return out
    row_count = len(values) - 3
    if row_count <= 0:
        return out
    data = slice_values(values, 4, start, row_count, 5)
    last_name = ""
    for row in data:
        if all(s(v).strip() == "" for v in row):
            last_name = ""
            continue
        name_raw, particular = s(row[1]).strip(), s(row[2]).strip()
        dates_raw, pct_raw = s(row[3]).strip(), s(row[4]).strip()
        if name_raw:
            last_name = name_raw
        name = name_raw or last_name
        if not name or not particular:
            continue
        if norm_name(particular) == "PARTICULARS":
            continue
        key = norm_name(name)
        if not key:
            continue
        if key not in out:
            out[key] = {"name": name, "score": None, "hasScore": False,
                        "taskCount": 0, "notDoneCount": 0}
        out[key]["taskCount"] += 1
        out[key]["notDoneCount"] += count_not_done_dates(dates_raw)
        value = parse_float(pct_raw.replace("%", "").strip())
        if value is None:
            continue
        if not out[key]["hasScore"]:
            out[key]["score"] = value
            out[key]["hasScore"] = True
    return out


def merge_checklist_score_maps(target, source):
    for key, src in (source or {}).items():
        if key not in target:
            target[key] = {"name": src["name"], "score": None, "hasScore": False,
                           "taskCount": 0, "notDoneCount": 0}
        if not target[key]["hasScore"] and src["hasScore"]:
            target[key]["score"] = src["score"]
            target[key]["hasScore"] = True
        target[key]["taskCount"] += src.get("taskCount") or 0
        target[key]["notDoneCount"] += src.get("notDoneCount") or 0
    return target


def fms_week_score_map(values, week_label):
    out = {}
    if not values or len(values) < 2:
        return out
    start = find_week_block_start(values, 1, week_label)
    if start is None or start + 5 > last_col(values):
        return out
    row_count = len(values) - 1
    if row_count <= 0:
        return out
    data = slice_values(values, 2, start, row_count, 6)

    def to_int(v):
        n = parse_int(s(v).replace(",", "").strip())
        return 0 if n is None else n

    cur_emp, cur_tasks, cur_items = "", 0, []
    for r in range(len(data)):
        first = s(data[r][0]).strip()
        key_text = norm_name(first)
        if is_fms_employee_header_row(data, r):
            cur_emp, cur_tasks, cur_items = first, 0, []
            continue
        if not cur_emp:
            continue
        if key_text == "TASK":
            continue
        if key_text == "TOTAL SCORE":
            emp_key = norm_name(cur_emp)
            if emp_key:
                score = s(data[r][4]).strip()
                planned, actual, over = to_int(data[r][1]), to_int(data[r][2]), to_int(data[r][3])
                parts = fms_score_parts(score, planned, actual, over)
                done = actual + over
                out[emp_key] = {
                    "name": cur_emp, "score": score or "—",
                    "onTimeScore": parts["onTimeScore"], "notDoneScore": parts["notDoneScore"],
                    "overTimeScore": parts["overTimeScore"], "finalScore": parts["finalScore"],
                    "planned": planned, "actual": actual, "overTime": over, "done": done,
                    "notDone": max(0, planned - done), "taskCount": cur_tasks,
                    "notDoneItems": cur_items,
                }
            cur_emp, cur_tasks, cur_items = "", 0, []
            continue
        if first:
            cur_tasks += 1
            nd_raw = s(data[r][5]).strip()
            if nd_raw:
                dates = [d for d in (x.strip() for x in re.split(r"\r?\n", nd_raw)) if d]
                if dates:
                    cur_items.append({"task": first, "dates": dates})
    return out


def fast_week_score_maps(week_label):
    checklist = {}
    for sh_name, _ in CHECKLIST_TABLES:
        merge_checklist_score_maps(
            checklist, checklist_week_score_map(checklist_week_values(sh_name, week_label), week_label))
    fms = fms_week_score_map(fms_week_values(week_label), week_label)
    return {"checklist": checklist, "fms": fms}


# ---------------- department summary ----------------

def getDepartmentScoreSummary(selectedWeek, mode=None):
    week_label = resolve_week_label(selectedWeek)
    directory = getDepartmentDirectory()
    if not directory or directory.get("success") is False:
        return {"success": False, "weekLabel": week_label,
                "message": (directory or {}).get("message") or "Department data not available.",
                "departments": []}
    maps = monthly_fms_maps(week_label) if mode == "MONTHLY" else fast_week_score_maps(week_label)
    dept_rows = []
    for dept_index, dept in enumerate(directory["departments"]):
        members = list(directory["byDepartment"].get(dept["key"], []))
        cl_vals, fm_vals, qt_vals, tm_vals = [], [], [], []
        cl_n = fm_n = qt_n = tm_n = 0
        member_rows = []
        for name in members:
            ekey = norm_name(name)
            cl, fm = maps["checklist"].get(ekey), maps["fms"].get(ekey)
            cs = checklist_score_text_from_map(cl)
            fs = fms_score_text_from_map(fm)
            qs = quantity_score_text(cs, fs)
            ts = fms_time_score_text_from_map(fm)
            cl_vals.append(cs); fm_vals.append(fs); qt_vals.append(qs); tm_vals.append(ts)
            cl_n += is_real_percentage_score(cs)
            fm_n += is_real_percentage_score(fs)
            qt_n += is_real_percentage_score(qs)
            tm_n += is_real_percentage_score(ts)
            member_rows.append({"name": name, "checklistScore": cs, "fmsScore": fs,
                                "quantityScore": qs, "timeScore": ts,
                                "notDone": (fm.get("notDone") or 0) if fm else 0})
        dept_rows.append({
            "key": dept["key"], "name": dept["name"], "employeeCount": len(members),
            "checklistScoredCount": cl_n, "fmsScoredCount": fm_n,
            "quantityScoredCount": qt_n, "timeScoredCount": tm_n,
            "checklistAverage": average_score_values(cl_vals),
            "fmsAverage": average_score_values(fm_vals),
            "quantityAverage": average_score_values(qt_vals),
            "timeAverage": average_time_score_values(tm_vals),
            "members": member_rows,
            "totalNotDone": sum((m["notDone"] or 0) for m in member_rows),
            "paletteIndex": (dept_index % 8) + 1,
        })
    all_c, all_f, all_q, all_t = [], [], [], []
    for d in dept_rows:
        for m in d["members"]:
            all_c.append(m["checklistScore"]); all_f.append(m["fmsScore"])
            all_q.append(m["quantityScore"]); all_t.append(m["timeScore"])
    return {
        "success": True, "weekLabel": week_label, "departmentCount": len(dept_rows),
        "employeeCount": sum(d["employeeCount"] or 0 for d in dept_rows),
        "checklistAverage": average_score_values(all_c), "fmsAverage": average_score_values(all_f),
        "quantityAverage": average_score_values(all_q), "timeAverage": average_time_score_values(all_t),
        "totalNotDone": sum(d["totalNotDone"] or 0 for d in dept_rows),
        "departments": dept_rows,
    }


# ---------------- print summaries ----------------

def print_key_map(employee_map, fixed_names):
    keys = {}
    for n in fixed_names:
        k = norm_name(n)
        if k and k in employee_map:
            keys[k] = True
    return keys


def is_print_excluded(name):
    key = norm_name(name)
    if not key:
        return True
    return key == "ADMIN" or bool(re.match(r"^ADMIN\d+$", key))


def login_names():
    with pool().connection() as conn:
        rows = conn.execute("select username from public.login_users").fetchall()
    return [r["username"] for r in rows]


def by_name(rows):
    rows.sort(key=lambda r: s(r.get("name")).casefold())


def getWeeklyScoreSummary(selectedWeek, printGroup=None, departmentKey=None):
    week_label = resolve_week_label(selectedWeek)
    maps = fast_week_score_maps(week_label)
    employee_map = {}
    for n in login_names():
        name = s(n).strip()
        key = norm_name(name)
        if name and key and key not in employee_map:
            employee_map[key] = name
    for key, e in maps["checklist"].items():
        employee_map.setdefault(key, e.get("name") or key)
    for key, e in maps["fms"].items():
        employee_map.setdefault(key, e.get("name") or key)

    ho_keys = print_key_map(employee_map, HO_EMPLOYEE_NAMES)
    site_keys = print_key_map(employee_map, SITE_EMPLOYEE_NAMES)

    group = norm_name(printGroup or "ALL")
    if group not in ("HO", "SITE"):
        group = "ALL"
    dept_key = norm_name(departmentKey or "ALL")
    dept_emp_keys, dept_label = None, ""
    if dept_key and dept_key != "ALL":
        directory = getDepartmentDirectory()
        if not directory or directory.get("success") is False:
            return {"success": False,
                    "message": (directory or {}).get("message") or "Department data not available.",
                    "weekLabel": week_label, "rows": []}
        members = directory["byDepartment"].get(dept_key, [])
        dept_emp_keys = {norm_name(n): True for n in members if norm_name(n)}
        for d in directory["departments"]:
            if norm_name(d["key"]) == dept_key:
                dept_label = s(d.get("name") or d.get("key")).strip()
                break
        if not dept_label:
            dept_label = s(departmentKey).strip()

    rows = []
    for key, name in employee_map.items():
        if key not in maps["checklist"]:
            continue
        if is_print_excluded(name):
            continue
        if dept_emp_keys is not None and key not in dept_emp_keys:
            continue
        if group == "HO" and key not in ho_keys:
            continue
        if group == "SITE" and key not in site_keys:
            continue
        cl, fm = maps["checklist"].get(key), maps["fms"].get(key)
        cl_tasks = cl["taskCount"] if cl and cl.get("taskCount") else 0
        fm_tasks = fm["taskCount"] if fm and fm.get("taskCount") else 0
        cs, fs = checklist_score_text_from_map(cl), fms_score_text_from_map(fm)
        rows.append({
            "name": name, "checklistScore": cs, "fmsScore": fs,
            "quantityScore": quantity_score_text(cs, fs),
            "timeScore": fms_time_score_text_from_map(fm),
            "totalTasks": cl_tasks + fm_tasks,
            "checklistNotDone": (cl.get("notDoneCount") or 0) if cl else 0,
            "fmsNotDone": (fm.get("notDone") or 0) if fm else 0,
            "done": (fm.get("done") or 0) if fm else 0,
            "notDone": (fm.get("notDone") or 0) if fm else 0,
        })
    by_name(rows)
    final_label = dept_label if dept_label else (
        "HO" if group == "HO" else ("Site" if group == "SITE" else "All Employees"))
    return {"success": True, "weekLabel": week_label, "printGroup": group,
            "groupLabel": final_label, "departmentKey": dept_key or "ALL",
            "departmentLabel": dept_label, "employeeCount": len(rows),
            "hoEmployeeCount": len(ho_keys), "siteEmployeeCount": len(site_keys), "rows": rows}


def dept_of_employee_map(directory):
    dept_of, order = {}, []
    if directory and directory.get("success") is not False:
        for dept in directory["departments"]:
            order.append(dept)
            for name in directory["byDepartment"].get(dept["key"], []):
                k = norm_name(name)
                if k and k not in dept_of:
                    dept_of[k] = dept
    return dept_of, order


def getHoDepartmentWiseWeeklyScoreSummary(selectedWeek):
    base = getWeeklyScoreSummary(selectedWeek, "HO", "ALL")
    if not base or base.get("success") is False:
        return base
    dept_of, order = dept_of_employee_map(getDepartmentDirectory())
    groups, other = {}, []
    for row in base["rows"]:
        dept = dept_of.get(norm_name(row["name"]))
        if not dept:
            other.append(row)
            continue
        groups.setdefault(dept["key"], []).append(row)
    departments, all_rows = [], []
    for dept in order:
        rows = groups.get(dept["key"])
        if not rows:
            continue
        departments.append({"key": dept["key"], "name": s(dept.get("name") or dept["key"]).strip(),
                            "employeeCount": len(rows), "rows": rows})
        all_rows.extend(rows)
    if other:
        departments.append({"key": "OTHER", "name": "Other", "employeeCount": len(other), "rows": other})
        all_rows.extend(other)
    return {"success": True, "weekLabel": base["weekLabel"], "printGroup": "HO",
            "departmentKey": "ALL", "groupLabel": "HO · Department-wise",
            "departmentCount": len(departments), "employeeCount": len(all_rows),
            "rows": all_rows, "departments": departments}


def getMonthlyDepartmentWiseScoreSummary(periodLabel, printGroup=None):
    label = clean_week_label(periodLabel)
    if not label:
        label = getMonthlyFmsPeriods()["defaultPeriod"] or ""
    if not label or get_values("monthly_fms_data", rows=[1]) is None:
        return {"success": False,
                "message": '"Monthly FMS Data" sheet or period not found.',
                "weekLabel": label, "rows": [], "departments": []}
    fms_map = fms_week_score_map(monthly_fms_week_values(label), label)
    group = norm_name(printGroup or "ALL")
    if group not in ("HO", "SITE"):
        group = "ALL"
    employee_map = {k: (v.get("name") or k) for k, v in fms_map.items()}
    allowed = None
    if group == "HO":
        allowed = print_key_map(employee_map, HO_EMPLOYEE_NAMES)
    if group == "SITE":
        allowed = print_key_map(employee_map, SITE_EMPLOYEE_NAMES)
    dept_of, order = dept_of_employee_map(getDepartmentDirectory())
    groups, other = {}, []
    for key, name in employee_map.items():
        if is_print_excluded(name):
            continue
        if allowed is not None and key not in allowed:
            continue
        entry = fms_map[key]
        row = {"name": name, "fmsScore": fms_score_text_from_map(entry),
               "timeScore": fms_time_score_text_from_map(entry),
               "planned": entry.get("planned") or 0, "done": entry.get("done") or 0,
               "notDone": entry.get("notDone") or 0, "totalTasks": entry.get("taskCount") or 0,
               "notDoneItems": entry.get("notDoneItems") or []}
        dept = dept_of.get(key)
        if not dept:
            other.append(row)
        else:
            groups.setdefault(dept["key"], []).append(row)
    departments, all_rows = [], []
    for dept in order:
        rows = groups.get(dept["key"])
        if not rows:
            continue
        by_name(rows)
        departments.append({"key": dept["key"], "name": s(dept.get("name") or dept["key"]).strip(),
                            "employeeCount": len(rows),
                            "totalNotDone": sum(r["notDone"] or 0 for r in rows), "rows": rows})
        all_rows.extend(rows)
    if other:
        by_name(other)
        departments.append({"key": "OTHER", "name": "Other", "employeeCount": len(other),
                            "totalNotDone": sum(r["notDone"] or 0 for r in other), "rows": other})
        all_rows.extend(other)
    return {
        "success": True, "weekLabel": label, "printGroup": group,
        "groupLabel": ("HO" if group == "HO" else ("Site" if group == "SITE" else "All Employees")) + " · Monthly",
        "employeeCount": len(all_rows), "departmentCount": len(departments),
        "averageFms": average_score_values([r["fmsScore"] for r in all_rows]),
        "averageTime": average_time_score_values([r["timeScore"] for r in all_rows]),
        "totalPlanned": sum(r["planned"] or 0 for r in all_rows),
        "totalNotDone": sum(r["notDone"] or 0 for r in all_rows),
        "rows": all_rows, "departments": departments,
    }


def getDepartmentWiseWeeklyScoreSummary(selectedWeek, departmentKey=None):
    week_label = resolve_week_label(selectedWeek)
    maps = fast_week_score_maps(week_label)
    directory = getDepartmentDirectory()
    if not directory or directory.get("success") is False:
        return {"success": False, "message": (directory or {}).get("message") or "Department data not available.",
                "weekLabel": week_label, "rows": [], "departments": []}
    wanted = norm_name(departmentKey or "ALL")
    departments, all_rows = [], []
    for dept in directory["departments"]:
        dkey = norm_name(dept.get("key") or dept.get("name"))
        if wanted != "ALL" and dkey != wanted:
            continue
        rows = []
        for name in list(directory["byDepartment"].get(dept["key"], [])):
            key = norm_name(name)
            cl, fm = maps["checklist"].get(key), maps["fms"].get(key)
            if not cl:
                continue
            if is_print_excluded(name):
                continue
            cl_tasks = cl["taskCount"] if cl.get("taskCount") else 0
            fm_tasks = fm["taskCount"] if fm and fm.get("taskCount") else 0
            cs, fs = checklist_score_text_from_map(cl), fms_score_text_from_map(fm)
            rows.append({
                "name": name, "departmentKey": dept["key"],
                "departmentName": s(dept.get("name") or dept["key"]).strip(),
                "checklistScore": cs, "fmsScore": fs,
                "quantityScore": quantity_score_text(cs, fs),
                "timeScore": fms_time_score_text_from_map(fm),
                "totalTasks": cl_tasks + fm_tasks,
                "checklistNotDone": cl.get("notDoneCount") or 0,
                "fmsNotDone": (fm.get("notDone") or 0) if fm else 0,
                "done": (fm.get("done") or 0) if fm else 0,
                "notDone": (fm.get("notDone") or 0) if fm else 0,
            })
        by_name(rows)
        if not rows:
            continue
        departments.append({"key": dept["key"], "name": s(dept.get("name") or dept["key"]).strip(),
                            "employeeCount": len(rows), "rows": rows})
        all_rows.extend(rows)
    if wanted != "ALL" and not departments:
        return {"success": True, "weekLabel": week_label, "departmentKey": wanted,
                "groupLabel": s(departmentKey or "Department"), "employeeCount": 0,
                "rows": [], "departments": []}
    return {"success": True, "weekLabel": week_label, "departmentKey": wanted or "ALL",
            "groupLabel": "Department-wise" if wanted == "ALL" else (
                departments[0]["name"] if departments else s(departmentKey or "Department")),
            "departmentCount": len(departments), "employeeCount": len(all_rows),
            "rows": all_rows, "departments": departments}


# ---------------- month / week helpers ----------------

def week_month_info(week_label):
    rng = parse_week_range(week_label)
    if not rng:
        now = date.today()
        return {"key": "%d-%02d" % (now.year, now.month),
                "label": "%s %d" % (MONTH_NAMES[now.month - 1], now.year)}
    ref = rng[0] + timedelta(days=3)
    return {"key": "%d-%02d" % (ref.year, ref.month),
            "label": "%s %d" % (MONTH_NAMES[ref.month - 1], ref.year)}


def format_stored_week_label(start, end):
    return "%s %d – %s %d, %d" % (MON3[start.month - 1], start.day, MON3[end.month - 1], end.day, end.year)


def calendar_weeks_for_month(month_info):
    parts = s(month_info["key"]).split("-")
    try:
        y, m = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return []
    month_start = date(y, m, 1)
    next_start = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    week_start = month_start - timedelta(days=month_start.weekday())
    weeks = []
    while week_start < next_start:
        weeks.append(format_stored_week_label(week_start, week_start + timedelta(days=6)))
        week_start += timedelta(days=7)
    return weeks


def month_weeks_for_selected_week(selected_week):
    selected = resolve_week_label(selected_week)
    info = week_month_info(selected)
    all_weeks = get_all_available_weeks()
    y, m = (int(x) for x in info["key"].split("-"))
    month_start = date(y, m, 1)
    next_start = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    month_weeks = calendar_weeks_for_month(info)
    keys = {normalize_week_label(w): True for w in month_weeks}
    for w in all_weeks:
        rng = parse_week_range(w)
        if rng:
            overlaps = rng[1] >= month_start and rng[0] < next_start
        else:
            overlaps = week_month_info(w)["key"] == info["key"]
        k = normalize_week_label(w)
        if overlaps and k not in keys:
            month_weeks.append(w)
            keys[k] = True
    if normalize_week_label(selected) not in {normalize_week_label(w) for w in month_weeks}:
        month_weeks.append(selected)
    month_weeks.sort(key=parse_week_start)
    return {"selected": selected, "monthInfo": info, "weeks": month_weeks}


def weighted_month_info(week_labels):
    counts, order = {}, []
    for w in week_labels or []:
        rng = parse_week_range(w)
        if not rng:
            fb = week_month_info(w)
            if fb["key"] not in counts:
                counts[fb["key"]] = {"key": fb["key"], "label": fb["label"], "days": 0,
                                     "firstTime": parse_week_start(w)}
                order.append(fb["key"])
            counts[fb["key"]]["days"] += 1
            continue
        cursor, end = rng
        while cursor <= end:
            key = "%d-%02d" % (cursor.year, cursor.month)
            if key not in counts:
                counts[key] = {"key": key, "label": "%s %d" % (MONTH_NAMES[cursor.month - 1], cursor.year),
                               "days": 0, "firstTime": cursor.toordinal()}
                order.append(key)
            counts[key]["days"] += 1
            cursor += timedelta(days=1)
    if not order:
        return week_month_info("")
    order.sort(key=lambda k: (-counts[k]["days"], counts[k]["firstTime"]))
    return {"key": counts[order[0]]["key"], "label": counts[order[0]]["label"]}


def month_weeks_for_selection(selected_weeks):
    if not isinstance(selected_weeks, list):
        return month_weeks_for_selected_week(selected_weeks)
    known = {normalize_week_label(w): w for w in get_all_available_weeks()}
    picked, seen = [], {}
    for w in selected_weeks:
        cleaned = clean_week_label(w)
        key = normalize_week_label(cleaned)
        if not key or key in seen:
            continue
        picked.append(known.get(key) or cleaned)
        seen[key] = True
    if not picked:
        return month_weeks_for_selected_week("")
    picked.sort(key=parse_week_start)
    return {"selected": picked[0], "monthInfo": weighted_month_info(picked), "weeks": picked}


# ---------------- monthly score ----------------

def getMonthlyScoreData(employeeName, selectedWeek):
    month = month_weeks_for_selection(selectedWeek)
    ekey = norm_name(employeeName)
    rows = []
    for w in month["weeks"]:
        maps = fast_week_score_maps(w)
        cl, fm = maps["checklist"].get(ekey), maps["fms"].get(ekey)
        cs, fs = checklist_score_text_from_map(cl), fms_score_text_from_map(fm)
        rows.append({"weekLabel": w, "checklistScore": cs, "fmsScore": fs,
                     "quantityScore": quantity_score_text(cs, fs),
                     "timeScore": fms_time_score_text_from_map(fm)})
    return {
        "success": True, "employeeName": employeeName,
        "monthLabel": month["monthInfo"]["label"], "selectedWeek": month["selected"], "weeks": rows,
        "averageChecklist": average_monthly_score_values([r["checklistScore"] for r in rows]),
        "averageFms": average_monthly_score_values([r["fmsScore"] for r in rows]),
        "averageQuantity": average_monthly_score_values([r["quantityScore"] for r in rows]),
        "averageTime": average_monthly_time_score_values([r["timeScore"] for r in rows]),
    }


def getMonthlyTeamScoreData(selectedWeek):
    month = month_weeks_for_selection(selectedWeek)
    employee_map, week_maps = {}, {}

    def add(name):
        raw = re.sub(r"\s+", " ", s(name).replace(" ", " ")).strip()
        key = norm_name(raw)
        if raw and key and key not in employee_map:
            employee_map[key] = raw

    for n in login_names():
        add(n)
    for w in month["weeks"]:
        maps = fast_week_score_maps(w)
        week_maps[normalize_week_label(w)] = maps
        for k, e in maps["checklist"].items():
            add(e.get("name") or k)
        for k, e in maps["fms"].items():
            add(e.get("name") or k)

    employees = sorted(({"key": k, "name": n} for k, n in employee_map.items()),
                       key=lambda e: s(e["name"]).casefold())
    rows = []
    for emp in employees:
        week_scores, cl_v, fm_v, qt_v, tm_v = [], [], [], [], []
        for w in month["weeks"]:
            maps = week_maps.get(normalize_week_label(w)) or {"checklist": {}, "fms": {}}
            cl, fm = maps["checklist"].get(emp["key"]), maps["fms"].get(emp["key"])
            cs, fs = checklist_score_text_from_map(cl), fms_score_text_from_map(fm)
            qs = quantity_score_text(cs, fs)
            ts = fms_time_score_text_from_map(fm)
            cl_tasks = cl["taskCount"] if cl and cl.get("taskCount") else 0
            fm_tasks = fm["taskCount"] if fm and fm.get("taskCount") else 0
            week_scores.append({"weekLabel": w, "checklistScore": cs, "fmsScore": fs,
                                "quantityScore": qs, "timeScore": ts,
                                "done": (fm.get("done") or 0) if fm else 0,
                                "notDone": (fm.get("notDone") or 0) if fm else 0,
                                "totalTasks": cl_tasks + fm_tasks})
            cl_v.append(cs); fm_v.append(fs); qt_v.append(qs); tm_v.append(ts)
        m_qty = average_monthly_score_values(qt_v)
        m_time = average_monthly_time_score_values(tm_v)
        rows.append({"name": emp["name"], "weekScores": week_scores,
                     "monthlyChecklist": average_monthly_score_values(cl_v),
                     "monthlyFms": average_monthly_score_values(fm_v),
                     "monthlyQuantity": m_qty, "monthlyTime": m_time,
                     "monthlyScore": average_score_values([m_qty, m_time])})
    return {
        "success": True, "monthLabel": month["monthInfo"]["label"],
        "selectedWeek": month["selected"], "weeks": month["weeks"],
        "employeeCount": len(rows), "rows": rows,
        "averageChecklist": average_score_values([r["monthlyChecklist"] for r in rows]),
        "averageFms": average_score_values([r["monthlyFms"] for r in rows]),
        "averageQuantity": average_score_values([r["monthlyQuantity"] for r in rows]),
        "averageTime": average_time_score_values([r["monthlyTime"] for r in rows]),
        "averageMonthScore": average_score_values([r["monthlyScore"] for r in rows]),
    }


def generateMonthlyTeamScoreSheet(selectedWeek):
    # The Google Sheet output ("Monthly Score" tab) cannot be written from this server;
    # the dashboard still receives the full monthly data.
    res = getMonthlyTeamScoreData(selectedWeek)
    res["sheetUpdated"] = False
    return res


# ---------------- post sales followup ----------------

def psf_week_key(value):
    text = re.sub(r"\s+", " ", re.sub(r"[–—]", "-",
          re.sub(r"^range\s*:\s*", "", re.sub(r"^week\s*:\s*", "", s(value), flags=re.I), flags=re.I))).strip()
    if not text:
        return ""
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s*(?:-|to)\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", text, re.I)
    if m:
        try:
            a = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            b = date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
        except ValueError:
            return ""
        return a.strftime("%Y%m%d") + "|" + b.strftime("%Y%m%d")
    m = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})\s*-\s*(?:([A-Za-z]{3})\s+)?(\d{1,2}),\s*(\d{4})$", text, re.I)
    if not m:
        return ""
    months = {x: i for i, x in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul",
                                          "aug", "sep", "oct", "nov", "dec"])}
    sm = months.get(m.group(1).lower())
    em = months.get(m.group(3).lower()) if m.group(3) else sm
    if sm is None or em is None:
        return ""
    sd, ed, ey = int(m.group(2)), int(m.group(4)), int(m.group(5))
    sy = ey - 1 if sm > em else ey
    try:
        a, b = date(sy, sm + 1, sd), date(ey, em + 1, ed)
    except ValueError:
        return ""
    return a.strftime("%Y%m%d") + "|" + b.strftime("%Y%m%d")


def getFollowupScoreData(employeeName, weekLabel):
    ekey = norm_name(employeeName)
    if ekey not in PSF_ALLOWED:
        return {"success": True, "eligible": False, "employeeName": employeeName,
                "weekLabel": weekLabel or "", "due": None, "expected": None}
    hv = get_values("post_sales_followup_score", rows=[1])
    if hv is None:
        return {"success": False, "eligible": True, "employeeName": employeeName,
                "weekLabel": weekLabel or "",
                "message": 'Sheet "Post Sales Followup Score" not found.', "due": None, "expected": None}
    if len(hv) < 1:
        return {"success": False, "eligible": True, "employeeName": employeeName,
                "weekLabel": weekLabel or "", "message": "Followup Score sheet is empty.",
                "due": None, "expected": None}
    selected = resolve_week_label(weekLabel)
    wanted = psf_week_key(selected)
    start = None
    if wanted:
        header = hv[0]
        for col in range(1, last_col(hv) + 1, 5):
            hk = psf_week_key(header[col - 1] if col - 1 < len(header) else "")
            if hk and hk == wanted:
                start = col
                break
    if start is None:
        return {"success": True, "eligible": True, "employeeName": employeeName, "weekLabel": selected,
                "message": "No Followup Score data found for " + selected + ".",
                "due": None, "expected": None}
    block = get_columns("post_sales_followup_score", list(range(start, start + 5)), last_col(hv)) or hv
    data = slice_values(block, 2, start, max(1, len(block) - 1), 5)
    result = {"success": True, "eligible": True, "employeeName": employeeName,
              "weekLabel": selected, "due": None, "expected": None}
    section = "DUE"
    for row in data:
        first = norm_name(row[0])
        if first == "DUE AMOUNT":
            section = "DUE"
            continue
        if first == "EXPECTED AMOUNT":
            section = "EXPECTED"
            continue
        if first == "NAME" or not first:
            continue
        if first != ekey:
            continue
        item = {"name": s(row[0]).strip(), "demandAmount": s(row[1]).strip(),
                "outstanding": s(row[2]).strip(), "netAmount": s(row[3]).strip(),
                "score": s(row[4]).strip()}
        if section == "DUE":
            result["due"] = item
        else:
            result["expected"] = item
    return result
