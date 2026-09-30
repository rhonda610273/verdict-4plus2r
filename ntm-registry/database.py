# -*- coding: utf-8 -*-
"""SQLite 資料層。所有資料都存在本機單一 .db 檔，不會離開這台電腦。"""

import json
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, timezone, timedelta

from fields import (FIELDS, FIELD_MAP, SQL_TYPE, KEY, STAT_FIELDS,
                    SEARCH_COLUMNS, VISIT_FIELDS, VISIT_EVENTS,
                    OUR_SITE, OUR_SITE_CODE)

ID_COL = KEY["id"]        # 唯一識別欄位（目前是 patient_code）

# 追蹤紀錄依研究時序排列，不是依建檔順序
LABEL_ORDER = {label: i for i, (_, label) in enumerate(VISIT_EVENTS)}

TAIPEI = timezone(timedelta(hours=8))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
# 密碼長度下限。院內單機環境、且有登入失敗鎖定，8 碼是可接受的折衷。
MIN_PASSWORD_LEN = 8

DB_PATH = os.path.join(DATA_DIR, "ntm.db")

PBKDF2_ROUNDS = 240_000
ROLES = ("admin", "editor", "viewer")


def now():
    return datetime.now(TAIPEI).isoformat(timespec="seconds")


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'editor',
    full_name     TEXT,
    created_at    TEXT NOT NULL,
    last_login    TEXT,
    disabled      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    ip         TEXT
);

CREATE TABLE IF NOT EXISTS cases (
    id         INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    created_by TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    deleted    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY,
    ts        TEXT NOT NULL,
    username  TEXT,
    ip        TEXT,
    action    TEXT NOT NULL,
    case_id   INTEGER,
    case_no   TEXT,
    detail    TEXT
);

CREATE TABLE IF NOT EXISTS visits (
    id         INTEGER PRIMARY KEY,
    case_id    INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    created_by TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    deleted    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_visits_case ON visits(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_at);
"""


def init_db():
    """建表 + 依 fields.py 自動補上缺少的欄位（安全的 additive migration）。"""
    conn = connect()
    with conn:
        conn.executescript(BASE_SCHEMA)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(cases)")}
        for f in FIELDS:
            if f["name"] not in existing:
                conn.execute(
                    'ALTER TABLE cases ADD COLUMN "%s" %s'
                    % (f["name"], SQL_TYPE[f["type"]])
                )
        existing_v = {r["name"] for r in conn.execute("PRAGMA table_info(visits)")}
        for f in VISIT_FIELDS:
            if f["name"] not in existing_v:
                conn.execute('ALTER TABLE visits ADD COLUMN "%s" %s'
                             % (f["name"], SQL_TYPE[f["type"]]))
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_case_id '
            'ON cases("%s") WHERE deleted = 0' % ID_COL
        )
        for col in (KEY["species"], KEY["enroll_date"], KEY["site"]):
            if col in FIELD_MAP:
                conn.execute('CREATE INDEX IF NOT EXISTS idx_case_%s ON cases("%s")'
                             % (col, col))
    conn.close()


# --------------------------------------------------------------------------
# users
# --------------------------------------------------------------------------

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    )
    return digest.hex(), salt


def create_user(username, password, role="editor", full_name=""):
    if role not in ROLES:
        raise ValueError("role 必須是 %s 其中之一" % (ROLES,))
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError("密碼至少 %d 個字元" % MIN_PASSWORD_LEN)
    pw, salt = hash_password(password)
    conn = connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, full_name, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (username, pw, salt, role, full_name, now()),
            )
    finally:
        conn.close()


def set_password(username, password):
    """改密碼並登出該帳號所有既有登入。

    若是因為密碼可能外洩才改，舊的登入狀態還能繼續用就等於沒改到。
    """
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError("密碼至少 %d 個字元" % MIN_PASSWORD_LEN)
    pw, salt = hash_password(password)
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE users SET password_hash=?, salt=? WHERE username=?",
                (pw, salt, username),
            )
            dropped = conn.execute(
                "DELETE FROM sessions WHERE user_id ="
                " (SELECT id FROM users WHERE username=?)", (username,)).rowcount
        return cur.rowcount, dropped
    finally:
        conn.close()


def verify_user(username, password):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND disabled=0", (username,)
        ).fetchone()
        if not row:
            # 即使帳號不存在也做一次雜湊，避免以回應時間推測帳號是否存在
            hash_password(password, "dummysalt")
            return None
        digest, _ = hash_password(password, row["salt"])
        if secrets.compare_digest(digest, row["password_hash"]):
            with conn:
                conn.execute(
                    "UPDATE users SET last_login=? WHERE id=?", (now(), row["id"])
                )
            return dict(row)
        return None
    finally:
        conn.close()


def list_users():
    conn = connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT id, username, role, full_name, created_at, last_login, disabled"
                " FROM users ORDER BY username"
            )
        ]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------------

def create_session(user_id, ip, hours=12):
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(TAIPEI) + timedelta(hours=hours)).isoformat(timespec="seconds")
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at, ip)"
                " VALUES (?,?,?,?,?)",
                (token, user_id, now(), expires, ip),
            )
        return token
    finally:
        conn.close()


def get_session_user(token):
    if not token:
        return None
    conn = connect()
    try:
        row = conn.execute(
            "SELECT u.id, u.username, u.role, u.full_name FROM sessions s"
            " JOIN users u ON u.id = s.user_id"
            " WHERE s.token=? AND s.expires_at > ? AND u.disabled=0",
            (token, now()),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def drop_session(token):
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    finally:
        conn.close()


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------

def audit(username, ip, action, case_id=None, case_no=None, detail=None):
    conn = connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_log (ts, username, ip, action, case_id, case_no, detail)"
                " VALUES (?,?,?,?,?,?,?)",
                (now(), username, ip, action, case_id, case_no,
                 json.dumps(detail, ensure_ascii=False) if detail is not None else None),
            )
    finally:
        conn.close()


def list_audit(limit=300):
    conn = connect()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

def _coerce(field, value):
    """把前端傳來的值轉成要存進 SQLite 的型別。"""
    t = field["type"]
    if value is None or value == "":
        return None
    if t == "bool":
        return 1 if value in (True, 1, "1", "true", "on", "是") else 0
    if t == "int":
        try:
            return int(str(value).strip())
        except ValueError:
            return None
    if t == "real":
        try:
            return float(str(value).strip())
        except ValueError:
            return None
    if t == "multi":
        if isinstance(value, str):
            value = [v for v in value.split(",") if v]
        allowed = set(field.get("options", []))
        value = [v for v in value if v in allowed] if allowed else list(value)
        return json.dumps(value, ensure_ascii=False)
    if t == "date":
        s = str(value).strip()
        if not s:
            return None
        try:
            datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            raise ValueError("「%s」的日期格式須為 YYYY-MM-DD（例：2026-01-15）"
                             % field["label"])
        return s
    return str(value).strip()


def _row_to_case(row):
    d = dict(row)
    for f in FIELDS:
        if f["type"] == "multi":
            raw = d.get(f["name"])
            try:
                d[f["name"]] = json.loads(raw) if raw else []
            except (TypeError, ValueError):
                d[f["name"]] = []
        elif f["type"] == "bool":
            d[f["name"]] = bool(d.get(f["name"]))
    # 收案年齡：REDCap 有 age 欄位就用它，否則由出生日期與收案日推算
    d["age_at_enroll"] = d.get(KEY["age"])
    if d["age_at_enroll"] in (None, "") and d.get("dob") and d.get(KEY["enroll_date"]):
        try:
            d["age_at_enroll"] = int(d[KEY["enroll_date"]][:4]) - int(d["dob"][:4])
        except (ValueError, TypeError):
            d["age_at_enroll"] = None
    return d


def save_case(payload, username, case_id=None):
    values, columns = [], []
    for f in FIELDS:
        if f["name"] not in payload:
            continue
        columns.append(f["name"])
        values.append(_coerce(f, payload[f["name"]]))

    if ID_COL in columns:
        idx = columns.index(ID_COL)
        if not values[idx]:
            raise ValueError("病人編號為必填")

    conn = connect()
    try:
        with conn:
            if case_id is None:
                cols = columns + ["created_at", "created_by", "updated_at", "updated_by"]
                vals = values + [now(), username, now(), username]
                sql = 'INSERT INTO cases (%s) VALUES (%s)' % (
                    ",".join('"%s"' % c for c in cols), ",".join("?" * len(cols))
                )
                cur = conn.execute(sql, vals)
                return cur.lastrowid
            sets = ",".join('"%s"=?' % c for c in columns)
            conn.execute(
                'UPDATE cases SET %s, updated_at=?, updated_by=? WHERE id=? AND deleted=0'
                % sets,
                values + [now(), username, case_id],
            )
            return case_id
    except sqlite3.IntegrityError:
        raise ValueError("病人編號重複，請換一個")
    finally:
        conn.close()


def get_case(case_id):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM cases WHERE id=? AND deleted=0", (case_id,)
        ).fetchone()
        return _row_to_case(row) if row else None
    finally:
        conn.close()


def search_cases(q="", filters=None, limit=200, offset=0):
    filters = filters or {}
    where, params = ["deleted=0"], []
    if q:
        like = "%" + q + "%"
        where.append("(%s)" % " OR ".join('"%s" LIKE ?' % c for c in SEARCH_COLUMNS))
        params += [like] * len(SEARCH_COLUMNS)
    for key, val in filters.items():
        if key in FIELD_MAP and val:
            where.append('"%s" = ?' % key)
            params.append(val)
    # 最近收案的排最前面
    sql = ('SELECT * FROM cases WHERE %s'
           ' ORDER BY COALESCE("%s", created_at) DESC, id DESC'
           ' LIMIT ? OFFSET ?' % (" AND ".join(where), KEY["enroll_date"]))
    conn = connect()
    try:
        rows = [_row_to_case(r) for r in conn.execute(sql, params + [limit, offset])]
        total = conn.execute(
            "SELECT COUNT(*) c FROM cases WHERE %s" % " AND ".join(where), params
        ).fetchone()["c"]
        return rows, total
    finally:
        conn.close()


def all_cases():
    conn = connect()
    try:
        return [
            _row_to_case(r)
            for r in conn.execute(
                'SELECT * FROM cases WHERE deleted=0 ORDER BY "%s"' % ID_COL
            )
        ]
    finally:
        conn.close()


def soft_delete(case_id):
    conn = connect()
    try:
        with conn:
            row = conn.execute('SELECT "%s" c FROM cases WHERE id=?' % ID_COL,
                               (case_id,)).fetchone()
            conn.execute(
                "UPDATE cases SET deleted=1, updated_at=? WHERE id=?", (now(), case_id)
            )
        return row["c"] if row else None
    finally:
        conn.close()


def stats():
    """給舊端點用的簡表；儀表板請用 dashboard()。"""
    conn = connect()
    try:
        return {"total": conn.execute(
            "SELECT COUNT(*) c FROM cases WHERE deleted=0").fetchone()["c"]}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# 儀表板聚合
# --------------------------------------------------------------------------

AGE_BANDS = [(0, 29, "≤29"), (30, 39, "30–39"), (40, 49, "40–49"),
             (50, 59, "50–59"), (60, 69, "60–69"), (70, 79, "70–79"),
             (80, 200, "≥80")]


def _age_band(age):
    if age is None:
        return None
    for lo, hi, label in AGE_BANDS:
        if lo <= age <= hi:
            return label
    return None


def _counter(rows, key_fn, blank="(未填)"):
    """依 key_fn 分組計數，回傳依數量遞減排序的清單。"""
    out = {}
    for r in rows:
        k = key_fn(r)
        if k is None:
            continue
        out[k] = out.get(k, 0) + 1
    return [{"key": k, "count": c}
            for k, c in sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))]


def _case_year(case):
    d = case.get(KEY["enroll_date"]) or case.get("created_at")
    return d[:4] if d else None


GROUPS = ("治療組", "觀察組")


def dashboard(year_from=None, year_to=None, species=None, group=None):
    """儀表板需要的所有聚合，一次算完。

    登錄型資料庫的量級（數百至數千筆）用 Python 聚合完全足夠，
    而且比散落各處的 SQL 好讀好改。
    """
    rows = all_cases()
    visits_by_case = all_visits_grouped()

    years = sorted({_case_year(c) for c in rows if _case_year(c)})

    def in_range(c):
        y = _case_year(c)
        if year_from and (not y or y < str(year_from)):
            return False
        if year_to and (not y or y > str(year_to)):
            return False
        if species and species not in _as_list(c.get(KEY["species"])):
            return False
        return True

    rows_all = [c for c in rows if in_range(c)]
    # group 只挑其中一個族群來看；by_group 那組對照表仍以全部個案計算，
    # 不然選了治療組之後對照圖會只剩一邊。
    rows = ([c for c in rows_all if c.get(KEY["group"]) == group]
            if group else rows_all)
    n = len(rows)

    # ---- KPI ----
    treat_group = [c for c in rows if c.get(KEY["group"]) == "治療組"]
    observe_group = [c for c in rows if c.get(KEY["group"]) == "觀察組"]
    converted = [c for c in rows if _has_conversion(visits_by_case.get(c["id"], []))]
    with_followup = [c for c in rows if visits_by_case.get(c["id"])]

    kpi = {
        "total": n,
        "treat_group": len(treat_group),
        "observe_group": len(observe_group),
        "with_followup": len(with_followup),
        "converted": len(converted),
        "conversion_rate": (round(len(converted) / len(treat_group) * 100, 1)
                            if treat_group else None),
        "visits_total": sum(len(v) for v in visits_by_case.values()),
    }

    # ---- 收案趨勢 ----
    def bucket(case, unit):
        d = case.get(KEY["enroll_date"])
        if not d or len(d) < 7:
            return None
        if unit == "year":
            return d[:4]
        if unit == "month":
            return d[:7]
        return "%s Q%d" % (d[:4], (int(d[5:7]) - 1) // 3 + 1)

    trend = {}
    for unit in ("year", "quarter", "month"):
        counts = {}
        for c in rows:
            b = bucket(c, unit)
            if b:
                counts[b] = counts.get(b, 0) + 1
        trend[unit] = [{"key": k, "count": counts[k]} for k in sorted(counts)]

    # ---- 年齡性別金字塔 ----
    bands = {label: {"band": label, "male": 0, "female": 0, "other": 0}
             for _, _, label in AGE_BANDS}
    for c in rows:
        band = _age_band(_to_int(c.get("age_at_enroll")))
        if not band:
            continue
        sex = (c.get(KEY["sex"]) or "").lower()
        key = "male" if "male" in sex and "fe" not in sex else \
              "female" if "female" in sex else "other"
        bands[band][key] += 1
    pyramid = [bands[label] for _, _, label in AGE_BANDS]

    # ---- 追蹤時間點分布：看各時間點各收到幾筆 ----
    from fields import VISIT_EVENTS
    ev_counts = {}
    for vs in visits_by_case.values():
        for v in vs:
            k = v.get("event") or "（未指定）"
            ev_counts[k] = ev_counts.get(k, 0) + 1
    order = [label for _, label in VISIT_EVENTS]
    visit_timeline = [{"key": k, "count": ev_counts[k]}
                      for k in order if k in ev_counts]
    visit_timeline += [{"key": k, "count": c} for k, c in ev_counts.items()
                       if k not in order]

    # ---- 共病盛行率 ----
    comorbid = []
    for f in FIELDS:
        if f.get("group") == "Comorbidity" and f["type"] == "bool":
            c = sum(1 for r in rows if r.get(f["name"]))
            if c:
                comorbid.append({"key": f["label"], "count": c,
                                 "pct": round(c / n * 100, 1) if n else 0})
    comorbid.sort(key=lambda d: -d["count"])

    # ---- 治療組 vs 觀察組 對照 ----
    by_group = {}
    for name in STAT_FIELDS:
        by_group[name] = _count_by_group(rows_all, name)
    comorbid_group = []
    for f in FIELDS:
        if f.get("group") == "Comorbidity" and f["type"] == "bool":
            item = {"key": f["label"]}
            total = 0
            for g in GROUPS:
                c = sum(1 for r in rows_all
                        if r.get(f["name"]) and r.get(KEY["group"]) == g)
                item[g] = c
                total += c
            if total:
                comorbid_group.append(item)
    comorbid_group.sort(key=lambda d: -(d[GROUPS[0]] + d[GROUPS[1]]))

    group_totals = {g: sum(1 for r in rows_all if r.get(KEY["group"]) == g)
                    for g in GROUPS}

    return {
        "filters": {"year_from": year_from, "year_to": year_to,
                    "species": species or "", "group": group or ""},
        "groups": list(GROUPS),
        "group_totals": group_totals,
        "by_group": by_group,
        "comorbid_group": comorbid_group,
        "years_available": years,
        "site": OUR_SITE,
        "kpi": kpi,
        "trend": trend,
        "pyramid": pyramid,
        "visit_timeline": visit_timeline,
        "comorbid": comorbid,
        "by": {name: _count_field(rows, name) for name in STAT_FIELDS},
    }


def _to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _as_list(value):
    """多選欄位存的是 JSON 陣列，單選是字串，統一成 list 方便比對。"""
    if isinstance(value, list):
        return value
    return [value] if value else []


def _count_field(rows, name):
    """複選欄位每個選項各計一次；單選就是一般計數。"""
    field = FIELD_MAP.get(name)
    counts = {}
    for r in rows:
        vals = _as_list(r.get(name)) if field and field["type"] == "multi" else \
               [r.get(name) or "（未填）"]
        for v in (vals or ["（未填）"]):
            v = v or "（未填）"
            counts[v] = counts.get(v, 0) + 1
    return [{"key": k, "count": c}
            for k, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _count_by_group(rows, name):
    """同一個欄位，治療組與觀察組各數一次，供兩組並排比較。"""
    field = FIELD_MAP.get(name)
    is_multi = bool(field and field["type"] == "multi")
    counts = {}
    for r in rows:
        g = r.get(KEY["group"])
        if g not in GROUPS:
            continue
        vals = _as_list(r.get(name)) if is_multi else [r.get(name) or "（未填）"]
        for v in (vals or ["（未填）"]):
            v = v or "（未填）"
            slot = counts.setdefault(v, {g2: 0 for g2 in GROUPS})
            slot[g] += 1
    out = [dict(key=k, **v) for k, v in counts.items()]
    out.sort(key=lambda d: (-sum(d[g] for g in GROUPS), d["key"]))
    return out


def _has_conversion(visits):
    """任一次追蹤的痰培養為陰性，視為曾經轉陰。"""
    for v in visits:
        val = v.get("ntm_sputumculture_initial") or ""
        if "陰" in str(val):
            return True
    return False


def all_visits_grouped():
    conn = connect()
    try:
        rows = [_row_to_visit(r) for r in conn.execute(
            "SELECT * FROM visits WHERE deleted=0")]
    finally:
        conn.close()
    out = {}
    for v in rows:
        out.setdefault(v["case_id"], []).append(v)
    return out



# --------------------------------------------------------------------------
# 追蹤紀錄
# --------------------------------------------------------------------------

def _row_to_visit(row):
    d = dict(row)
    for f in VISIT_FIELDS:
        if f["type"] == "multi":
            raw = d.get(f["name"])
            try:
                d[f["name"]] = json.loads(raw) if raw else []
            except (TypeError, ValueError):
                d[f["name"]] = []
        elif f["type"] == "bool":
            d[f["name"]] = bool(d.get(f["name"]))
    return d


def list_visits(case_id):
    """依研究時序排列，不是依建檔順序 —— 補登的紀錄也會排到正確位置。"""
    conn = connect()
    try:
        rows = [_row_to_visit(r) for r in conn.execute(
            "SELECT * FROM visits WHERE case_id=? AND deleted=0", (case_id,))]
    finally:
        conn.close()
    rows.sort(key=lambda v: (LABEL_ORDER.get(v.get("event"), 99),
                             v.get("visit_date") or "9999"))
    return rows


def save_visit(case_id, payload, username, visit_id=None):
    columns, values = [], []
    for f in VISIT_FIELDS:
        if f["name"] not in payload:
            continue
        columns.append(f["name"])
        values.append(_coerce(f, payload[f["name"]]))
    if not columns:
        raise ValueError("沒有任何內容可儲存")

    conn = connect()
    try:
        with conn:
            if visit_id is None:
                cols = columns + ["case_id", "created_at", "created_by",
                                  "updated_at", "updated_by"]
                vals = values + [case_id, now(), username, now(), username]
                cur = conn.execute(
                    'INSERT INTO visits (%s) VALUES (%s)'
                    % (",".join('"%s"' % c for c in cols), ",".join("?" * len(cols))),
                    vals)
                return cur.lastrowid
            conn.execute(
                'UPDATE visits SET %s, updated_at=?, updated_by=?'
                ' WHERE id=? AND case_id=? AND deleted=0'
                % ",".join('"%s"=?' % c for c in columns),
                values + [now(), username, visit_id, case_id])
            return visit_id
    finally:
        conn.close()


def delete_visit(case_id, visit_id):
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE visits SET deleted=1, updated_at=? WHERE id=? AND case_id=?",
                (now(), visit_id, case_id))
        return cur.rowcount
    finally:
        conn.close()


def visit_counts():
    """每個個案有幾次追蹤，供清單頁顯示。"""
    conn = connect()
    try:
        return {r["case_id"]: r["n"] for r in conn.execute(
            "SELECT case_id, COUNT(*) n FROM visits WHERE deleted=0 GROUP BY case_id")}
    finally:
        conn.close()


def clear_cases():
    """清空所有個案與追蹤紀錄，供重新匯入使用。帳號與稽核紀錄保留。"""
    conn = connect()
    try:
        with conn:
            n = conn.execute("SELECT COUNT(*) c FROM cases").fetchone()["c"]
            conn.execute("DELETE FROM visits")
            conn.execute("DELETE FROM cases")
        return n
    finally:
        conn.close()
