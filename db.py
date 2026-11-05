"""Direct Postgres access. Returns table data in the same 2D shape the
Apps Script code got from sheet.getDisplayValues(): values[row-1][col-1]."""
import os
import re
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

load_dotenv()

_pool = None
ALLOWED = {
    "users", "monthly_score", "checklist_ho", "checklist_site", "fms_data",
    "monthly_fms_data", "post_sales_followup_score", "department",
}


def pool():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            os.environ["DATABASE_URL"], min_size=1, max_size=int(os.environ.get("DB_POOL_MAX", "3")),
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )
    return _pool


def col_index(name):
    """col_a -> 1, col_z -> 26, col_aa -> 27."""
    n = 0
    for ch in name[4:]:
        n = n * 26 + (ord(ch) - 96)
    return n


def get_values(table, rows=None):
    """All rows (or only the given sheet rows) as a 2D list of strings.
    None -> table does not exist."""
    if table not in ALLOWED:
        raise ValueError("table not allowed: " + table)
    sql = "select * from public.%s" % table
    params = ()
    if rows:
        sql += " where sheet_row = any(%s)"
        params = (list(rows),)
    sql += " order by sheet_row"
    with pool().connection() as conn:
        try:
            recs = conn.execute(sql, params).fetchall()
        except Exception as e:  # missing table
            if "does not exist" in str(e):
                return None
            raise
    if not recs:
        return []
    cols = [k for k in recs[0].keys() if re.fullmatch(r"col_[a-z]+", k)]
    idx = {k: col_index(k) for k in cols}
    width = max(idx.values()) if idx else 0
    last = max(r["sheet_row"] for r in recs)
    values = [[""] * width for _ in range(last)]
    for r in recs:
        row = values[r["sheet_row"] - 1]
        for k in cols:
            v = r[k]
            if v is not None:
                row[idx[k] - 1] = v
    return values


def login_row(username_norm):
    with pool().connection() as conn:
        rows = conn.execute(
            "select username, default_password, updated_password "
            "from public.login_users"
        ).fetchall()
    return rows


def col_name(idx):
    """1 -> col_a, 27 -> col_aa."""
    s, n = "", idx
    while n > 0:
        n, m = divmod(n - 1, 26)
        s = chr(97 + m) + s
    return "col_" + s


def get_columns(table, col_numbers, width):
    """Only the given sheet columns (1-based) for every row, placed at their
    original positions in a 2D list that is `width` columns wide."""
    if table not in ALLOWED:
        raise ValueError("table not allowed: " + table)
    cols = [c for c in col_numbers if 1 <= c <= width]
    if not cols:
        return []
    select = "sheet_row, " + ", ".join('"%s"' % col_name(c) for c in cols)
    with pool().connection() as conn:
        recs = conn.execute(
            "select %s from public.%s order by sheet_row" % (select, table)
        ).fetchall()
    if not recs:
        return []
    last = max(r["sheet_row"] for r in recs)
    values = [[""] * width for _ in range(last)]
    for r in recs:
        row = values[r["sheet_row"] - 1]
        for c in cols:
            v = r[col_name(c)]
            if v is not None:
                row[c - 1] = v
    return values
