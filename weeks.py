import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
MON3 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEK_RE = re.compile(r"^([A-Za-z]{3})\s+\d{1,2}\s*[–—-]\s*([A-Za-z]{3})\s+\d{1,2},\s*\d{4}$", re.I)


def clean_week_label(v):
    s = "" if v is None else str(v)
    s = re.sub(r"^week\s*:\s*", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def normalize_week_label(v):
    s = "" if v is None else str(v)
    s = re.sub(r"^week\s*:\s*", "", s, flags=re.I)
    s = re.sub(r"[–—-]", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def is_week_label(v):
    return bool(WEEK_RE.match(clean_week_label(v)))


def parse_week_range(label):
    text = re.sub(r"[–—]", "-", clean_week_label(label))
    text = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})\s*-\s*(?:([A-Za-z]{3})\s+)?(\d{1,2}),\s*(\d{4})$", text, re.I)
    if not m:
        return None
    sm = MONTHS.get(m.group(1).lower())
    sd = int(m.group(2))
    em = MONTHS.get(m.group(3).lower()) if m.group(3) else sm
    ed = int(m.group(4))
    ey = int(m.group(5))
    if sm is None or em is None:
        return None
    if not m.group(3) and ed < sd:
        em = (sm + 1) % 12
    sy = ey
    if sm > em or (not m.group(3) and sm == 11 and em == 0):
        sy = ey - 1
    try:
        return date(sy, sm + 1, sd), date(ey, em + 1, ed)
    except ValueError:
        return None


def parse_week_start(label):
    r = parse_week_range(label)
    return datetime(r[0].year, r[0].month, r[0].day).timestamp() if r else 0


def week_label_current():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6)
    return "%s %d – %s %d, %d" % (MON3[mon.month - 1], mon.day, MON3[sun.month - 1], sun.day, sun.year)


def week_block_starts(values, header_row):
    """[(col_1based, label)] of week labels found in the header row."""
    if not values or len(values) < header_row:
        return []
    vals = values[header_row - 1] or []
    return [(c + 1, clean_week_label(v)) for c, v in enumerate(vals) if is_week_label(v)]
