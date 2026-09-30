#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帳號管理。

    python3 tools/manage_user.py list
    python3 tools/manage_user.py add  <帳號> --role admin|editor|viewer --name "王醫師"
    python3 tools/manage_user.py passwd <帳號>
    python3 tools/manage_user.py disable <帳號>
    python3 tools/manage_user.py enable  <帳號>

密碼一律以互動方式輸入，不會出現在命令列歷史紀錄裡。
"""

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db  # noqa: E402


def prompt_password():
    while True:
        pw1 = getpass.getpass("密碼（至少 %d 字）: " % db.MIN_PASSWORD_LEN)
        pw2 = getpass.getpass("再輸入一次: ")
        if pw1 != pw2:
            print("兩次輸入不一致")
            continue
        if len(pw1) < db.MIN_PASSWORD_LEN:
            print("密碼太短")
            continue
        return pw1


def set_disabled(username, value):
    conn = db.connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE users SET disabled=? WHERE username=?", (value, username))
            if value:
                conn.execute(
                    "DELETE FROM sessions WHERE user_id ="
                    " (SELECT id FROM users WHERE username=?)", (username,))
        return cur.rowcount
    finally:
        conn.close()


def suggest_users(username):
    """找不到帳號時，直接列出有哪些帳號可用。

    側邊欄顯示的是「顯示名稱」，使用者很容易拿它當帳號來用。
    """
    rows = db.list_users()
    print("找不到帳號 %s" % username)
    if not rows:
        print("（目前沒有任何帳號）")
        return
    hit = [r for r in rows if (r["full_name"] or "").strip() == username.strip()]
    if hit:
        print("「%s」是顯示名稱，不是帳號。這個人的帳號是：%s"
              % (username, hit[0]["username"]))
    print("\n目前有這些帳號：")
    for r in rows:
        print("   %-16s %-8s %s" % (r["username"], r["role"], r["full_name"] or ""))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p_add = sub.add_parser("add")
    p_add.add_argument("username")
    p_add.add_argument("--role", default="editor", choices=db.ROLES)
    p_add.add_argument("--name", default="")
    for name in ("passwd", "disable", "enable"):
        sp = sub.add_parser(name)
        sp.add_argument("username")
    args = parser.parse_args()

    db.init_db()

    if args.cmd == "list":
        rows = db.list_users()
        if not rows:
            print("（尚無帳號）")
            return 0
        print("%-16s %-8s %-14s %-20s %s" % ("帳號", "角色", "顯示名稱", "最後登入", "狀態"))
        for r in rows:
            print("%-16s %-8s %-14s %-20s %s" % (
                r["username"], r["role"], r["full_name"] or "",
                r["last_login"] or "—", "停用" if r["disabled"] else "啟用"))
        return 0

    if args.cmd == "add":
        db.create_user(args.username, prompt_password(), args.role, args.name)
        print("已建立帳號 %s（%s）" % (args.username, args.role))
        return 0

    if args.cmd == "passwd":
        if not any(r["username"] == args.username for r in db.list_users()):
            suggest_users(args.username)      # 先檢查，免得白打兩次密碼
            return 1
        changed, dropped = db.set_password(args.username, prompt_password())
        if changed == 0:
            print("找不到帳號 %s" % args.username)
            return 1
        print("已更新密碼。")
        if dropped:
            print("同時登出了 %d 個既有的登入狀態，請用新密碼重新登入。" % dropped)
        return 0

    value = 1 if args.cmd == "disable" else 0
    if set_disabled(args.username, value) == 0:
        suggest_users(args.username)
        return 1
    print("已%s帳號 %s" % ("停用" if value else "啟用", args.username))
    return 0


if __name__ == "__main__":
    sys.exit(main())
