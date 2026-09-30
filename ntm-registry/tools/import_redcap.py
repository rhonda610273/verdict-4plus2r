#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 REDCap 匯出的 CSV 匯入本系統。全程在這台電腦上執行，資料不離開本機。

    python3 tools/import_redcap.py --file 匯出檔.csv --dry-run
    python3 tools/import_redcap.py --file 匯出檔.csv --commit

會做的事：
  * 只留本院（北榮）的個案，其他醫院一筆都不會進來
  * 依 redcap_event_name 把同一個病人的多列拆成「一筆個案 + 多次追蹤」
  * 把 REDCap 的代碼還原成文字（0 → 陰性），raw 與 labels 兩種匯出都吃得下
  * 複選題的 var___0 / var___1 展開欄位合併回一個複選欄位
"""

import argparse
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db                                    # noqa: E402
from fields import (FIELD_MAP, VISIT_FIELD_MAP, KEY, EVENT_LABEL,   # noqa: E402
                    OUR_SITE, OUR_SITE_CODE, REDCAP_MAP)

RECORD_COLS = ("study_id", "record_id", "patient_code")
EVENT_COL = "redcap_event_name"
BASELINE_EVENTS = {"v1_arm_1"}


def read_csv(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("看不懂這個 CSV 的編碼")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        raise SystemExit("檔案沒有資料")
    header = [h.strip() for h in rows[0]]
    return header, [dict(zip(header, r)) for r in rows[1:]]


def decode(field, value):
    """REDCap 匯出可能是代碼（raw）或文字（labels），兩種都要吃得下。"""
    if value in (None, ""):
        return None
    codes = field.get("codes") or {}
    if value in codes:
        return codes[value]
    labels = set(codes.values())
    if value in labels:
        return value
    return value


def collect_checkbox(row, base, field):
    """var___0 / var___1 這種展開欄位合併回一個複選欄位。"""
    codes = field.get("codes") or {}
    chosen = []
    for code, label in codes.items():
        # REDCap 匯出時把代碼裡的非英數字換成底線
        col = "%s___%s" % (base, re.sub(r"[^0-9a-zA-Z]", "_", str(code)).lower())
        if str(row.get(col, "")).strip() == "1":
            chosen.append(label)
    return chosen


def is_ours(row):
    """只留本院個案。醫院欄與病人編號任一符合即可，兩者都沒有就排除。"""
    site = str(row.get(KEY["site"], "")).strip()
    if site in (OUR_SITE_CODE, OUR_SITE, "1", "01"):
        return True
    code = str(row.get("patient_code", "")).strip()
    if re.search(r"[-_]0*%s[-_]" % OUR_SITE_CODE, code):
        return True
    return False


# 這些欄位就算有值也不算「有填資料」—— 作廢的紀錄往往還留著編號與組別
IDENTITY_ONLY = {"patient_code", "hospital_site", "observe_or_treat_group", "study_id"}


def is_voided(case_payload, visits):
    """收案資料整份空白 = 已被發現重複並清空作廢，不應匯入。

    使用者說明：真正重複的那一筆，收案會是全空白；只留編號不算有資料。
    """
    if visits:
        return False
    return not any(k not in IDENTITY_ONLY for k in case_payload)


def code_serial(code):
    """T-001-2410-PC018 → PC018；用來認出同一個人改組後的另一筆。"""
    parts = re.split(r"[-_]", str(code or "").strip())
    return parts[-1].upper() if len(parts) >= 2 else ""


def code_group(code):
    parts = re.split(r"[-_]", str(code or "").strip())
    return parts[0].upper() if parts else ""


def event_label(raw_event):
    if not raw_event:
        return "收案 V1"
    return EVENT_LABEL.get(raw_event.strip(), "其他")


def build(header, rows, report):
    record_col = next((c for c in RECORD_COLS if c in header), None)
    if not record_col:
        raise SystemExit("找不到病人識別欄位（study_id / record_id / patient_code）")
    has_event = EVENT_COL in header

    # 先掃一遍決定哪些病人是本院的 —— 醫院欄通常只填在收案那一列
    ours = set()
    for r in rows:
        if is_ours(r):
            ours.add(r.get(record_col, "").strip())

    by_record = {}
    excluded = 0
    for r in rows:
        rid = (r.get(record_col) or "").strip()
        if not rid:
            continue
        if rid not in ours:
            excluded += 1
            continue
        by_record.setdefault(rid, []).append(r)

    report["excluded_rows"] = excluded
    report["records"] = len(by_record)

    # 被排除的紀錄依醫院分組，讓人核對「確實都不是本院」。
    # 以病人為單位判定一次 —— 醫院欄通常只填在收案那一列，
    # 逐列判斷會讓同一個人被算進兩個不同的標籤。
    site_field = FIELD_MAP.get(KEY["site"], {})
    codes = site_field.get("codes") or {}
    per_record = {}
    for r in rows:
        rid = (r.get(record_col) or "").strip()
        if not rid or rid in ours:
            continue
        slot = per_record.setdefault(rid, {"site": "", "code": ""})
        raw = str(r.get(KEY["site"], "")).strip()
        if raw and not slot["site"]:
            slot["site"] = codes.get(raw, raw)
        m = re.search(r"[-_](\d{3})[-_]", str(r.get("patient_code", "")))
        if m and not slot["code"]:
            slot["code"] = m.group(1)

    breakdown = {}
    for slot in per_record.values():
        label = slot["site"] or (("醫院碼 " + slot["code"]) if slot["code"]
                                 else "（無醫院資訊）")
        breakdown[label] = breakdown.get(label, 0) + 1
    report["excluded_by_site"] = sorted(breakdown.items(), key=lambda kv: -kv[1])

    cases = []
    for rid, group in by_record.items():
        case_payload, visits = {}, []
        for r in group:
            ev_raw = (r.get(EVENT_COL) or "").strip() if has_event else ""
            is_baseline = (not has_event) or ev_raw in BASELINE_EVENTS
            target_map = FIELD_MAP if is_baseline else VISIT_FIELD_MAP
            payload = {}

            for col, value in r.items():
                if col in (EVENT_COL, record_col) or value in (None, ""):
                    continue
                base = re.sub(r"___.*$", "", col)
                mapped = REDCAP_MAP.get(base) or REDCAP_MAP.get(col)
                name = mapped[1] if mapped else base
                field = target_map.get(name)
                if field is None:
                    continue
                if field["type"] == "multi":
                    vals = collect_checkbox(r, base, field)
                    if vals:
                        payload[name] = vals
                elif "___" in col:
                    continue
                else:
                    payload[name] = decode(field, value.strip())

            if is_baseline:
                case_payload.update(payload)
            elif payload:
                payload["event"] = event_label(ev_raw)
                visits.append(payload)

        if not case_payload.get(KEY["id"]):
            case_payload[KEY["id"]] = rid
        if is_voided(case_payload, visits):
            report.setdefault("voided", []).append(case_payload[KEY["id"]])
            continue
        cases.append((rid, case_payload, visits))

    # 同一個病人編號被兩筆以上的 REDCap 紀錄使用。依使用者指示：作廢就好 ——
    # 保留資料最完整的那一筆（填的欄位最多、其次追蹤次數多、再其次紀錄編號小），
    # 其餘視為作廢不匯入，並在報表中列出以便回頭核對。
    by_code = {}
    for rid, c, vs in cases:
        by_code.setdefault(c.get(KEY["id"], ""), []).append((rid, c, vs))

    kept, dup_report = [], []
    for code, group in by_code.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        ranked = sorted(
            group,
            key=lambda t: (-sum(1 for k in t[1] if k not in IDENTITY_ONLY),
                           -len(t[2]), str(t[0])))
        kept.append(ranked[0])
        dup_report.append((code, [
            (rid, sum(1 for k in c if k not in IDENTITY_ONLY), len(vs),
             rid == ranked[0][0])
            for rid, c, vs in ranked]))
    cases = kept
    report["duplicate_codes"] = sorted(dup_report)

    # 改組：同一個人由觀察組重新收案為治療組，會有兩筆不同編號。
    # 這是研究設計不是重複，所以只提報讓人確認，不自動合併。
    by_serial = {}
    for _, c, _ in cases:
        code = c.get(KEY["id"], "")
        serial = code_serial(code)
        if serial:
            by_serial.setdefault(serial, []).append(code)
    report["regrouped"] = sorted(
        (codes for codes in by_serial.values()
         if len(codes) > 1 and len({code_group(c) for c in codes}) > 1),
        key=lambda cs: cs[0])

    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="REDCap 匯出的 CSV")
    ap.add_argument("--dry-run", action="store_true", help="檢查但不寫入")
    ap.add_argument("--commit", action="store_true", help="真的寫入資料庫")
    ap.add_argument("--update", action="store_true", help="病人編號已存在時更新")
    ap.add_argument("--reset", action="store_true",
                    help="匯入前清空所有既有個案與追蹤（帳號與稽核紀錄保留）")
    args = ap.parse_args()

    if not (args.dry_run or args.commit):
        raise SystemExit("請指定 --dry-run 或 --commit")
    if not os.path.exists(args.file):
        raise SystemExit("找不到檔案：%s" % args.file)

    header, rows = read_csv(args.file)
    report = {}
    cases = build(header, rows, report)

    print("\n檔案共 %d 列。" % len(rows))
    print("排除非本院（%s 以外）的資料列：%d 列" % (OUR_SITE, report["excluded_rows"]))
    print("本院個案數：%d" % len(cases))
    print("追蹤紀錄數：%d" % sum(len(v) for _, _, v in cases))

    if report.get("voided"):
        print("\n略過 %d 筆作廢紀錄（收案欄位整份空白，視為已刪除）：" % len(report["voided"]))
        for code in report["voided"][:10]:
            print("   %s" % code)
        if len(report["voided"]) > 10:
            print("   …另有 %d 筆" % (len(report["voided"]) - 10))

    if report.get("duplicate_codes"):
        print("\n有 %d 個病人編號被重複使用 —— 保留資料最完整的一筆，其餘作廢："
              % len(report["duplicate_codes"]))
        for code, entries in report["duplicate_codes"][:10]:
            print("   %s" % code)
            for rid, filled, nvisits, is_kept in entries:
                print("      REDCap 紀錄 %-8s 填了 %3d 個欄位、%d 次追蹤   %s"
                      % (rid, filled, nvisits, "← 保留" if is_kept else "作廢"))
        if len(report["duplicate_codes"]) > 10:
            print("   …另有 %d 個" % (len(report["duplicate_codes"]) - 10))

    if report.get("regrouped"):
        print("\n疑似改組（同一編號序號、不同組別）%d 組 —— 這是研究設計，"
              "不會自動合併：" % len(report["regrouped"]))
        for codes in report["regrouped"][:10]:
            print("   %s" % "　↔　".join(codes))
        if len(report["regrouped"]) > 10:
            print("   …另有 %d 組" % (len(report["regrouped"]) - 10))
        print("   （兩筆都會匯入。若要視為同一人，請告訴我要怎麼併。）")

    if report.get("excluded_by_site"):
        print("\n被排除的個案（依醫院）—— 請確認裡面沒有本院的：")
        for label, count in report["excluded_by_site"]:
            mark = "  ← 這是本院！" if OUR_SITE in label or OUR_SITE_CODE in label else ""
            print("   %-22s %d 人%s" % (label[:20], count, mark))

    if not cases:
        print("\n沒有任何本院個案。請確認匯出檔是否包含 %s（醫院碼 %s）。"
              % (OUR_SITE, OUR_SITE_CODE))
        return

    filled = {}
    for _, c, _ in cases:
        for k in c:
            filled[k] = filled.get(k, 0) + 1
    print("\n有填到值的個案欄位（前 12 名）：")
    for name, cnt in sorted(filled.items(), key=lambda kv: -kv[1])[:12]:
        label = FIELD_MAP[name]["label"] if name in FIELD_MAP else name
        print("   %-34s %d 筆" % (label[:32], cnt))

    print("\n前 3 筆個案：")
    for rid, c, vs in cases[:3]:
        print("   %-18s 追蹤 %d 次   組別:%s" % (
            c.get(KEY["id"], rid), len(vs), c.get(KEY["group"]) or "—"))

    if args.dry_run:
        print("\n這是試跑，沒有寫入任何東西。")
        print("確認無誤後執行：")
        print("    python tools/import_redcap.py --file %s --commit" % args.file)
        return

    db.init_db()
    print("\n即將寫入 %s" % db.DB_PATH)
    if args.reset:
        existing_n = len(db.all_cases())
        print("⚠ --reset：會先刪除既有的 %d 筆個案與其追蹤紀錄" % existing_n)
        print("  （使用者帳號與稽核紀錄不受影響）")
    if input("確定要匯入嗎？輸入 yes 繼續：").strip().lower() != "yes":
        print("已取消。")
        return

    if args.reset:
        removed = db.clear_cases()
        print("已清除 %d 筆舊個案。" % removed)

    existing = {c[KEY["id"]]: c["id"] for c in db.all_cases() if c.get(KEY["id"])}
    added = updated = skipped = visits_added = 0
    for rid, payload, visits in cases:
        code = payload[KEY["id"]]
        try:
            if code in existing:
                if not args.update:
                    skipped += 1
                    continue
                case_id = existing[code]
                db.save_case(payload, "redcap_import", case_id)
                updated += 1
            else:
                case_id = db.save_case(payload, "redcap_import")
                added += 1
            for v in visits:
                db.save_visit(case_id, v, "redcap_import")
                visits_added += 1
        except ValueError as exc:
            print("   %s 匯入失敗：%s" % (code, exc))
            skipped += 1

    db.audit("redcap_import", "local", "import",
             detail={"file": os.path.basename(args.file), "added": added,
                     "updated": updated, "skipped": skipped, "visits": visits_added})
    print("\n完成：新增 %d 筆個案、更新 %d 筆、略過 %d 筆，追蹤紀錄 %d 筆。"
          % (added, updated, skipped, visits_added))


if __name__ == "__main__":
    main()
