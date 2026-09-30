#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""備份資料庫到本機（或院內核可的外接/網路磁碟）。

用法：
    python3 tools/backup.py                       # 備份到 backups/
    python3 tools/backup.py --dest E:\\NTM備份     # 備份到指定資料夾
    python3 tools/backup.py --keep 30             # 只保留最近 30 份

使用 SQLite 的線上備份 API，伺服器執行中也可以安全備份。
請不要把備份檔放到任何雲端同步資料夾（OneDrive / Google Drive / Dropbox）。
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db  # noqa: E402

CLOUD_HINTS = ("onedrive", "google drive", "googledrive", "dropbox",
               "icloud", "box sync", "megasync", "同步")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", default=os.path.join(db.BASE_DIR, "backups"))
    parser.add_argument("--keep", type=int, default=60, help="保留份數，0 表示全部保留")
    args = parser.parse_args()

    if not os.path.exists(db.DB_PATH):
        print("找不到資料庫：%s" % db.DB_PATH)
        return 1

    lowered = args.dest.lower()
    if any(h in lowered for h in CLOUD_HINTS):
        print("⚠ 備份路徑看起來是雲端同步資料夾：%s" % args.dest)
        print("  個案資料不得離開本機，請改用本機磁碟或院內核可的加密外接碟。")
        return 2

    os.makedirs(args.dest, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(args.dest, "ntm-%s.db" % stamp)

    src = sqlite3.connect(db.DB_PATH)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()

    size = os.path.getsize(target) / 1024
    print("已備份 → %s (%.1f KB)" % (target, size))

    if args.keep > 0:
        backups = sorted(
            f for f in os.listdir(args.dest)
            if f.startswith("ntm-") and f.endswith(".db")
        )
        for old in backups[:-args.keep]:
            os.remove(os.path.join(args.dest, old))
            print("刪除舊備份：%s" % old)
    return 0


if __name__ == "__main__":
    sys.exit(main())
