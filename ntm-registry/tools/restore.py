#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""從備份還原資料庫。

    python3 tools/restore.py                 # 列出所有備份，挑一份還原
    python3 tools/restore.py --list          # 只列出，不做事
    python3 tools/restore.py --file backups/ntm-20260824-180000.db --yes

還原前會先把目前的資料庫另存成 data/ntm-取代前-時間.db，
所以按錯了也救得回來。

⚠ 還原前請先關掉伺服器（啟動系統的黑色視窗按 Ctrl+C），
否則正在使用中的資料可能覆蓋不完全。
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db  # noqa: E402

BACKUP_DIR = os.path.join(db.BASE_DIR, "backups")


def find_backups(folder):
    if not os.path.isdir(folder):
        return []
    files = [os.path.join(folder, f) for f in os.listdir(folder)
             if f.startswith("ntm-") and f.endswith(".db")]
    return sorted(files, reverse=True)


def describe(path):
    """看一眼備份裡有幾筆個案，才不會還原到空檔。"""
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        cases = con.execute(
            "SELECT COUNT(*) FROM cases WHERE deleted=0").fetchone()[0]
        visits = con.execute(
            "SELECT COUNT(*) FROM visits WHERE deleted=0").fetchone()[0]
        con.close()
        return "%d 筆個案、%d 筆追蹤" % (cases, visits)
    except Exception as exc:                      # 壞掉的備份也要看得出來
        return "無法讀取（%s）" % exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=BACKUP_DIR, help="備份資料夾")
    parser.add_argument("--file", help="直接指定要還原的備份檔")
    parser.add_argument("--list", action="store_true", help="只列出備份")
    parser.add_argument("--yes", action="store_true", help="不再詢問，直接還原")
    args = parser.parse_args()

    target = args.file
    if not target:
        backups = find_backups(args.dir)
        if not backups:
            print("在 %s 找不到任何備份。" % args.dir)
            print("請先執行一次 backup.bat（或 python3 tools/backup.py）。")
            return 1

        print("備份清單（新到舊）：\n")
        for i, path in enumerate(backups, 1):
            size = os.path.getsize(path) / 1024
            print("  %2d. %s  %.1f KB  %s"
                  % (i, os.path.basename(path), size, describe(path)))
        print()
        if args.list:
            return 0

        pick = input("要還原第幾份？（直接按 Enter 取消）").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(backups):
            print("取消。")
            return 0
        target = backups[int(pick) - 1]

    if not os.path.exists(target):
        print("找不到檔案：%s" % target)
        return 1

    print("\n即將還原：%s（%s）" % (target, describe(target)))
    if os.path.exists(db.DB_PATH):
        print("目前的資料庫：%s（%s）" % (db.DB_PATH, describe(db.DB_PATH)))
    print("⚠ 請確認伺服器已經關閉。")

    if not args.yes:
        if input("確定要還原嗎？輸入 yes 繼續：").strip().lower() != "yes":
            print("取消。")
            return 0

    if os.path.exists(db.DB_PATH):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        keep = os.path.join(db.BASE_DIR, "data", "ntm-取代前-%s.db" % stamp)
        shutil.copy2(db.DB_PATH, keep)
        print("目前的資料庫已另存：%s" % keep)

    # WAL 檔留著會蓋掉剛還原的內容，一併清掉
    for suffix in ("-wal", "-shm"):
        stale = db.DB_PATH + suffix
        if os.path.exists(stale):
            os.remove(stale)

    shutil.copy2(target, db.DB_PATH)
    print("已還原完成 → %s（%s）" % (db.DB_PATH, describe(db.DB_PATH)))
    print("現在可以重新啟動系統（start.bat）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
