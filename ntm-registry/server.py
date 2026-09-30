#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""非結核分枝桿菌（NTM）管理系統 — 院內網頁伺服器。

特色：
  * 只用 Python 標準函式庫，不需要 pip install（醫院電腦常無法對外安裝套件）
  * 個案資料存在 data/ntm.db，不會上傳到任何雲端服務
  * 前端沒有任何外部 CDN 連線，完全離線可用
  * 存取需登入，並記錄稽核軌跡

連線範圍由 config.json 的 host 與 allowed_ips 決定，
預設開放院內網路（見 README 第二章）。

啟動：  python3 server.py
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from fields import FIELDS, GROUPS, LIST_COLUMNS, VISIT_FIELDS, KEY, OUR_SITE

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    # 監聽所有網卡，讓科內其他電腦連得到（比照 TB 系統的做法）
    "host": "0.0.0.0",
    # 規格書要求不可使用 3000（TB 系統已佔用），故預設 3001
    "port": 3001,
    # "*" = 不限來源 IP。要收緊就改成明確的電腦清單，例如
    # ["127.0.0.1", "::1", "10.100.144.50", "10.100.144.51"]
    "allowed_ips": ["*"],
    "session_hours": 12,
    "max_login_attempts": 5,
    "lockout_seconds": 300,
    # 「核而為一」入口頁與 TB 系統的位址（同事主機）
    "portal_url": "http://10.100.144.109:3000/index.html",
    "tb_url": "http://10.100.144.109:3000/TB主系統整合.html",
}

CONFIG = dict(DEFAULT_CONFIG)

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

# 登入失敗計數：{ip: [失敗次數, 最後一次失敗時間]}
_login_fails = {}

# 合法 Host 標頭快取（本機各網卡位址不會在執行期間變動）
_hosts_cache = None


def _allowed_hosts():
    """開放區網連線時，使用者用 10.x.x.x 連進來，本機各網卡位址也要算合法。"""
    global _hosts_cache
    if _hosts_cache is None:
        hosts = {"127.0.0.1", "localhost", "::1"}
        cfg_host = CONFIG.get("host", "")
        if cfg_host and cfg_host != "0.0.0.0":
            hosts.add(cfg_host)
        hosts.update(local_ips())
        _hosts_cache = hosts
    return _hosts_cache


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            CONFIG.update(json.load(fh))
    return CONFIG


class Handler(BaseHTTPRequestHandler):
    server_version = "NTMRegistry"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s - %s\n" % (db.now(), self.client_address[0], fmt % args))

    @property
    def client_ip(self):
        return self.client_address[0]

    def send_json(self, obj, status=HTTPStatus.OK, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, message):
        self.send_json({"error": message}, status=status)

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        # 只允許同源資源，禁止任何對外連線
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'",
        )

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 2_000_000:
            raise ValueError("請求內容過大")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def cookie_token(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:
            return None
        morsel = jar.get("ntm_session")
        return morsel.value if morsel else None

    def current_user(self):
        return db.get_session_user(self.cookie_token())

    # ------------------------------------------------------------------
    # 存取控制
    # ------------------------------------------------------------------
    def ip_allowed(self):
        allowed = CONFIG.get("allowed_ips") or []
        if "*" in allowed:
            return True
        return self.client_ip in allowed

    def host_allowed(self):
        """擋 DNS rebinding：Host 標頭必須是這台機器自己的位址之一。"""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in _allowed_hosts()

    def csrf_ok(self):
        """瀏覽器在跨站情境下無法自行加上自訂標頭，用它擋 CSRF。"""
        return self.headers.get("X-NTM-Client") == "1"

    # ------------------------------------------------------------------
    # routing
    # ------------------------------------------------------------------
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method):
        if not self.ip_allowed():
            self.log_message("拒絕非允許來源 IP")
            self.send_error_json(HTTPStatus.FORBIDDEN, "此網站僅限本機使用")
            return
        if not self.host_allowed():
            self.send_error_json(HTTPStatus.FORBIDDEN, "Host 不被允許")
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        try:
            if path.startswith("/api/"):
                if method != "GET" and not self.csrf_ok():
                    self.send_error_json(HTTPStatus.FORBIDDEN, "缺少用戶端標頭")
                    return
                self.handle_api(method, path, query)
            elif method == "GET":
                self.serve_static(path)
            else:
                self.send_error_json(HTTPStatus.METHOD_NOT_ALLOWED, "不支援的方法")
        except ValueError as exc:
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))
        except BrokenPipeError:
            pass
        except Exception as exc:  # noqa: BLE001
            self.log_message("錯誤: %r", exc)
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, "伺服器內部錯誤")

    # ------------------------------------------------------------------
    # static
    # ------------------------------------------------------------------
    def serve_static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        safe = os.path.normpath(path).lstrip("/\\")
        full = os.path.join(STATIC_DIR, safe)
        if not os.path.abspath(full).startswith(STATIC_DIR) or not os.path.isfile(full):
            self.send_error_json(HTTPStatus.NOT_FOUND, "找不到頁面")
            return
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def handle_api(self, method, path, query):
        # ---- 公開端點 ----
        if path == "/api/login" and method == "POST":
            return self.api_login()

        user = self.current_user()
        if path == "/api/me" and method == "GET":
            return self.send_json({"user": user})
        if user is None:
            return self.send_error_json(HTTPStatus.UNAUTHORIZED, "請先登入")

        if path == "/api/logout" and method == "POST":
            db.drop_session(self.cookie_token())
            db.audit(user["username"], self.client_ip, "logout")
            return self.send_json({"ok": True}, extra_headers={
                "Set-Cookie": "ntm_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"
            })

        if path == "/api/schema" and method == "GET":
            return self.send_json({
                "fields": FIELDS,
                "groups": [{"key": k, "label": v} for k, v in GROUPS],
                "list_columns": LIST_COLUMNS,
                "db_path": db.DB_PATH,
                "visit_fields": VISIT_FIELDS,
                "key": KEY,
                "site": OUR_SITE,
                "portal_url": CONFIG.get("portal_url", ""),
                "tb_url": CONFIG.get("tb_url", ""),
            })

        if path == "/api/stats" and method == "GET":
            return self.send_json(db.stats())

        if path == "/api/dashboard" and method == "GET":
            def one(key):
                val = (query.get(key) or [""])[0].strip()
                return val or None
            return self.send_json(db.dashboard(
                year_from=one("year_from"), year_to=one("year_to"),
                species=one("species"), group=one("group")))

        if path == "/api/export.csv" and method == "GET":
            # 唯讀帳號只能在畫面上看，不能把整份個案帶出平台。
            # 要放寬就刪掉這兩行。
            if user["role"] == "viewer":
                return self.send_error_json(HTTPStatus.FORBIDDEN, "唯讀帳號不能匯出")
            return self.api_export(user)

        if path == "/api/audit" and method == "GET":
            if user["role"] != "admin":
                return self.send_error_json(HTTPStatus.FORBIDDEN, "需要管理員權限")
            return self.send_json({"entries": db.list_audit()})

        if path == "/api/users" and method == "GET":
            if user["role"] != "admin":
                return self.send_error_json(HTTPStatus.FORBIDDEN, "需要管理員權限")
            return self.send_json({"users": db.list_users()})

        if path == "/api/cases":
            if method == "GET":
                return self.api_list_cases(query)
            if method == "POST":
                return self.api_save_case(user, None)

        # ---- 追蹤紀錄 ----
        m = re.fullmatch(r"/api/cases/(\d+)/visits", path)
        if m:
            case_id = int(m.group(1))
            if method == "GET":
                return self.send_json({"visits": db.list_visits(case_id)})
            if method == "POST":
                if user["role"] == "viewer":
                    return self.send_error_json(HTTPStatus.FORBIDDEN, "唯讀帳號不能編輯")
                vid = db.save_visit(case_id, self.read_json(), user["username"])
                db.audit(user["username"], self.client_ip, "visit_create", case_id)
                return self.send_json({"ok": True, "id": vid})

        m = re.fullmatch(r"/api/cases/(\d+)/visits/(\d+)", path)
        if m:
            case_id, visit_id = int(m.group(1)), int(m.group(2))
            if user["role"] == "viewer":
                return self.send_error_json(HTTPStatus.FORBIDDEN, "唯讀帳號不能編輯")
            if method == "PUT":
                db.save_visit(case_id, self.read_json(), user["username"], visit_id)
                db.audit(user["username"], self.client_ip, "visit_update", case_id)
                return self.send_json({"ok": True})
            if method == "DELETE":
                db.delete_visit(case_id, visit_id)
                db.audit(user["username"], self.client_ip, "visit_delete", case_id)
                return self.send_json({"ok": True})

        m = re.fullmatch(r"/api/cases/(\d+)", path)
        if m:
            case_id = int(m.group(1))
            if method == "GET":
                case = db.get_case(case_id)
                if not case:
                    return self.send_error_json(HTTPStatus.NOT_FOUND, "找不到個案")
                return self.send_json({"case": case})
            if method == "PUT":
                return self.api_save_case(user, case_id)
            if method == "DELETE":
                if user["role"] != "admin":
                    return self.send_error_json(HTTPStatus.FORBIDDEN, "只有管理員可刪除")
                case_no = db.soft_delete(case_id)
                db.audit(user["username"], self.client_ip, "delete", case_id, case_no)
                return self.send_json({"ok": True})

        self.send_error_json(HTTPStatus.NOT_FOUND, "未知的 API 路徑")

    def api_login(self):
        ip = self.client_ip
        fails, last = _login_fails.get(ip, (0, 0.0))
        lockout = CONFIG.get("lockout_seconds", 300)
        if fails >= CONFIG.get("max_login_attempts", 5) and time.time() - last < lockout:
            wait = int(lockout - (time.time() - last))
            return self.send_error_json(
                HTTPStatus.TOO_MANY_REQUESTS, "登入失敗次數過多，請於 %d 秒後再試" % wait)

        data = self.read_json()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        user = db.verify_user(username, password) if username and password else None
        if not user:
            _login_fails[ip] = (fails + 1, time.time())
            db.audit(username or "(空白)", ip, "login_failed")
            return self.send_error_json(HTTPStatus.UNAUTHORIZED, "帳號或密碼錯誤")

        _login_fails.pop(ip, None)
        token = db.create_session(user["id"], ip, CONFIG.get("session_hours", 12))
        db.audit(user["username"], ip, "login")
        cookie = ("ntm_session=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Strict"
                  % (token, CONFIG.get("session_hours", 12) * 3600))
        self.send_json(
            {"user": {"username": user["username"], "role": user["role"],
                      "full_name": user["full_name"]}},
            extra_headers={"Set-Cookie": cookie},
        )

    def api_list_cases(self, query):
        q = (query.get("q") or [""])[0]
        limit = min(int((query.get("limit") or ["200"])[0]), 1000)
        offset = int((query.get("offset") or ["0"])[0])
        filters = {}
        from fields import KEY as FKEY
        for key in (FKEY["species"], FKEY["group"], FKEY["site"], FKEY["sex"]):
            val = (query.get(key) or [""])[0]
            if val:
                filters[key] = val
        rows, total = db.search_cases(q, filters, limit, offset)
        counts = db.visit_counts()
        for r in rows:
            r["visit_count"] = counts.get(r["id"], 0)
        self.send_json({"cases": rows, "total": total})

    def api_save_case(self, user, case_id):
        if user["role"] == "viewer":
            return self.send_error_json(HTTPStatus.FORBIDDEN, "唯讀帳號不能編輯")
        payload = self.read_json()
        new_id = db.save_case(payload, user["username"], case_id)
        db.audit(user["username"], self.client_ip,
                 "update" if case_id else "create", new_id, payload.get("case_no"))
        self.send_json({"ok": True, "id": new_id})

    def api_export(self, user):
        cases = db.all_cases()
        buf = io.StringIO()
        cols = (["case_no"] + [f["name"] for f in FIELDS if f["name"] != "case_no"]
                + ["ats_met", "age_at_dx", "treatment_months",
                   "created_at", "created_by", "updated_at", "updated_by"])
        writer = csv.writer(buf)
        writer.writerow(cols)
        for case in cases:
            row = []
            for col in cols:
                val = case.get(col)
                if isinstance(val, list):
                    val = "; ".join(val)
                elif isinstance(val, bool):
                    val = "是" if val else "否"
                row.append("" if val is None else val)
            writer.writerow(row)
        # 加 BOM，Excel 開啟中文才不會亂碼
        body = ("﻿" + buf.getvalue()).encode("utf-8")
        db.audit(user["username"], self.client_ip, "export_csv",
                 detail={"rows": len(cases)})
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition",
                         'attachment; filename="ntm_cases_%s.csv"' % db.now()[:10])
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)


def local_ips():
    """找出這台電腦在區域網路上的 IP，供回報給 TB 系統負責人使用。"""
    import socket
    found = set()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))   # 不會真的送出封包，只為取得出口網卡
        found.add(sock.getsockname()[0])
        sock.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in found if not ip.startswith("127."))


def bootstrap_admin():
    """第一次啟動且沒有任何帳號時，引導建立管理員。"""
    if db.list_users():
        return
    if not sys.stdin or not sys.stdin.isatty():
        print("\n" + "=" * 62)
        print(" 尚未建立任何帳號，而且目前不是互動視窗，無法詢問你要設什麼密碼。")
        print("=" * 62)
        print(" 請先在「命令提示字元」或終端機裡手動建立管理員帳號：")
        print("     python tools/manage_user.py add <帳號> --role admin")
        print(" 建立完成後再啟動系統即可。")
        print("（如果你是用工作排程器/開機自動啟動，就會看到這個訊息。）")
        print("=" * 62)
        sys.exit(1)

    print("\n=== 第一次啟動：建立管理員帳號 ===")
    import getpass
    username = input("管理員帳號: ").strip()
    while True:
        pw1 = getpass.getpass("密碼（至少 %d 字）: " % db.MIN_PASSWORD_LEN)
        pw2 = getpass.getpass("再輸入一次: ")
        if pw1 != pw2:
            print("兩次輸入不一致，請重試")
            continue
        if len(pw1) < db.MIN_PASSWORD_LEN:
            print("密碼太短")
            continue
        break
    db.create_user(username, pw1, role="admin", full_name=input("顯示名稱（可留空）: ").strip())
    print("已建立管理員 %s\n" % username)


def main():
    parser = argparse.ArgumentParser(description="NTM 個案資料庫（本機專用）")
    parser.add_argument("--host", help="綁定位址，預設 127.0.0.1")
    parser.add_argument("--port", type=int, help="連接埠，預設 8787")
    args = parser.parse_args()

    load_config()
    if args.host:
        CONFIG["host"] = args.host
    if args.port:
        CONFIG["port"] = args.port

    db.init_db()
    bootstrap_admin()

    host, port = CONFIG["host"], CONFIG["port"]
    httpd = ThreadingHTTPServer((host, port), Handler)
    ips = local_ips()
    print("=" * 62)
    print(" 非結核分枝桿菌管理系統　已啟動")
    print("   本機請連      : http://127.0.0.1:%d/" % port)
    print("   資料庫檔案    : %s" % db.DB_PATH)
    print("   允許連線的 IP : %s" % ", ".join(CONFIG["allowed_ips"]))
    if host in ("127.0.0.1", "localhost", "::1"):
        print("   連線範圍      : 只有這台電腦")
        if ips:
            print("   本機院內位址  : %s" % "、".join(ips))
    else:
        print("   連線範圍      : 院內網路")
        for ip in ips:
            print("   其他電腦請連  : http://%s:%d/   ← 回報這個給 TB 系統負責人" % (ip, port))
        print()
        print("   ⚠ 開放區網連線請注意：")
        print("     1. 連線是 HTTP 明文，密碼與個案資料在院內網路上可被側錄；")
        print("        要長期跨電腦使用，請請資訊室協助架設 HTTPS。")
        print("     2. Windows 防火牆預設會擋，需手動開放 port %d 的輸入連線。" % port)
        if "*" in (CONFIG.get("allowed_ips") or []):
            print("     3. allowed_ips 目前是 \"*\"（不限來源電腦）；要收緊的話，")
            print("        在 config.json 列出允許連線的電腦 IP 即可。")
    print("   按 Ctrl+C 結束")
    print("=" * 62)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
