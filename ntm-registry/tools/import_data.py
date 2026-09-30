#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把既有的 Excel / CSV 個案資料匯入系統。

全程在這台電腦上執行，資料不會離開本機。

三個步驟：

  1) 看看檔案裡有什麼，並產生對應表
     python tools/import_data.py --file 資料.xlsx --inspect

  2) 用記事本打開 import_mapping.json，把猜錯的對應改掉，
     不要匯入的欄位設成 null

  3) 先試跑（不寫入），確認沒問題再真的匯入
     python tools/import_data.py --file 資料.xlsx --dry-run
     python tools/import_data.py --file 資料.xlsx --commit

支援民國年（114/1/5 會轉成 2025-01-05）、多種日期寫法、
性別與是/否欄位的各種寫法。看不懂的值會在試跑時全部列出來，不會亂猜。
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db          # noqa: E402
from fields import FIELDS, FIELD_MAP   # noqa: E402
import xlsx_reader             # noqa: E402

MAPPING_PATH = os.path.join(db.BASE_DIR, "import_mapping.json")

# 常見的欄位別名 → 系統欄位。只用來「猜」，猜錯可以在對應表裡改。
ALIASES = {
    "chart_no": ["病歷號", "病歷號碼", "病歷", "病例號", "chartno", "chart no",
                 "his", "medical record", "mrn", "身分證號", "病患編號"],
    "patient_name": ["姓名", "病患姓名", "患者姓名", "病人姓名", "name"],
    "phone": ["電話", "聯絡電話", "手機", "連絡電話", "phone", "tel"],
    "case_no": ["個案編號", "編號", "序號", "case no", "caseno", "研究編號", "id"],
    "sex": ["性別", "sex", "gender"],
    "birth_year": ["出生年", "出生年份", "生日", "出生日期", "birth", "dob", "年次"],
    "bmi": ["bmi", "身體質量指數"],
    "smoking": ["吸菸", "抽菸", "吸菸史", "菸酒史", "smoking"],
    "symptom_onset": ["症狀出現", "發病日", "症狀開始"],
    "enroll_date": ["收案日期", "收案日", "納入日期", "建檔日"],
    "case_status": ["收案狀態", "個案狀態", "狀態", "status"],
    "last_visit": ["最近訪視", "訪視日", "上次訪視", "最後訪視"],
    "followup_interval": ["追蹤頻率", "追蹤間隔", "回診頻率"],
    "next_followup": ["下次追蹤", "下次回診", "應追蹤日", "預定追蹤"],
    "visit_note": ["訪視紀錄", "訪視記錄", "備註訪視", "個管紀錄"],
    "species": ["菌種", "菌種鑑定", "細菌", "ntm 菌種", "species", "菌名"],
    "first_positive_date": ["首次陽性", "第一次陽性", "初次培養陽性", "培養陽性日"],
    "positive_culture_count": ["陽性套數", "陽性次數", "培養陽性套數"],
    "afb_smear": ["抗酸菌塗片", "塗片", "afb", "smear"],
    "specimen_types": ["檢體", "檢體來源", "檢體種類", "specimen"],
    "radiographic_pattern": ["影像型態", "影像分型", "ct 表現", "影像"],
    "cavity": ["空洞", "cavity"],
    "ct_date": ["hrct", "ct 日期", "影像日期"],
    "disease_form": ["疾病型態", "感染部位", "疾病分類"],
    "diagnosis_date": ["確診日期", "診斷日期", "診斷日", "確診日"],
    "referral_source": ["來源", "轉介來源", "個案來源"],
    "dst_done": ["有做藥敏", "藥敏", "dst"],
    "dst_date": ["藥敏日期", "藥敏檢驗日"],
    "dst_clarithromycin": ["clarithromycin", "clr", "克拉黴素"],
    "dst_amikacin": ["amikacin", "amk"],
    "dst_moxifloxacin": ["moxifloxacin", "mxf"],
    "dst_linezolid": ["linezolid", "lzd"],
    "treated": ["有治療", "是否治療", "治療與否"],
    "treatment_start": ["治療開始", "起始治療", "開始用藥", "治療起日"],
    "treatment_end": ["治療結束", "停藥日", "治療迄日"],
    "regimen": ["處方", "治療處方", "用藥", "藥物", "regimen"],
    "culture_conversion": ["培養轉陰", "轉陰", "conversion"],
    "conversion_date": ["轉陰日期", "轉陰日"],
    "outcome": ["治療結果", "結果", "預後", "outcome"],
    "last_followup": ["最後追蹤", "末次追蹤"],
    "notes": ["備註", "註記", "說明", "remark", "note"],
}

SEX_MAP = {"男": "男", "m": "男", "male": "男", "1": "男", "男性": "男",
           "女": "女", "f": "女", "female": "女", "2": "女", "女性": "女"}

TRUE_WORDS = {"是", "y", "yes", "true", "1", "v", "有", "✓", "ｖ", "o", "○"}
FALSE_WORDS = {"否", "n", "no", "false", "0", "無", "x", "×", "-", "nil"}


def norm(text):
    """正規化用來比對的字串：全形轉半形、去空白、轉小寫。"""
    text = unicodedata.normalize("NFKC", str(text or ""))
    return re.sub(r"[\s_\-()（）]", "", text).lower()


# --------------------------------------------------------------------------
# 讀檔
# --------------------------------------------------------------------------

def read_table(path, sheet=1):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        rows = xlsx_reader.read_rows(path, sheet)
    elif ext in (".csv", ".txt"):
        rows = read_csv(path)
    elif ext == ".xls":
        raise SystemExit("舊版 .xls 不支援。請用 Excel 另存成 .xlsx 或 CSV。")
    else:
        raise SystemExit("不認得的檔案類型：%s（支援 .xlsx / .csv）" % ext)

    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        raise SystemExit("檔案是空的，或第一個工作表沒有資料。")
    return rows


def read_csv(path):
    """Excel 存出來的 CSV 可能是 UTF-8、UTF-8-BOM 或 Big5，逐一嘗試。"""
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("看不懂這個 CSV 的編碼。請用 Excel 另存成「CSV UTF-8」。")
    return [row for row in csv.reader(io.StringIO(text))]


# --------------------------------------------------------------------------
# 猜對應
# --------------------------------------------------------------------------

def guess_mapping(headers):
    lookup = {}
    for f in FIELDS:
        lookup[norm(f["label"])] = f["name"]
        lookup[norm(f["name"])] = f["name"]
    for name, words in ALIASES.items():
        for w in words:
            lookup.setdefault(norm(w), name)

    mapping, used = {}, set()
    for h in headers:
        key = norm(h)
        hit = lookup.get(key)
        if not hit:
            # 退而求其次：欄名包含別名，或別名包含欄名
            for alias, name in lookup.items():
                if len(alias) >= 2 and (alias in key or key in alias):
                    hit = name
                    break
        if hit and hit not in used:
            mapping[h] = hit
            used.add(hit)
        else:
            mapping[h] = None
    return mapping


# --------------------------------------------------------------------------
# 值的轉換
# --------------------------------------------------------------------------

def parse_date(value):
    """支援西元與民國年、多種分隔符號。回傳 YYYY-MM-DD 或 None。"""
    s = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not s:
        return None
    s = re.sub(r"\s+\d{1,2}:\d{2}(:\d{2})?$", "", s)     # 去掉時間部分
    s = s.replace("年", "/").replace("月", "/").replace("日", "")
    m = re.match(r"^(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,2})$", s)
    if not m:
        m2 = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)     # 20250105
        if not m2:
            m3 = re.match(r"^(\d{3})(\d{2})(\d{2})$", s)  # 1140105（民國）
            if not m3:
                return None
            y, mo, d = int(m3.group(1)) + 1911, int(m3.group(2)), int(m3.group(3))
            return _mkdate(y, mo, d)
        y, mo, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        return _mkdate(y, mo, d)

    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 200:                    # 民國年
        y += 1911
    return _mkdate(y, mo, d)


def _mkdate(y, mo, d):
    import datetime
    try:
        return datetime.date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_bool(value):
    s = norm(value)
    if not s:
        return None
    if s in TRUE_WORDS:
        return True
    if s in FALSE_WORDS:
        return False
    return "?"                      # 看不懂，交給試跑報告


def match_option(field, value):
    """把儲存格的值對到選項清單。回傳 (值, 是否成功)。

    模糊比對只在「剛好只有一個選項符合」時才採用。像 MAC 這種同時符合
    多個選項的寫法，寧可原樣保留並提報，也不要自作主張挑一個 —— 悄悄把
    MAC 變成 MAC – M. avium 會讓資料看起來比實際更精確。
    """
    options = [o for o in field.get("options", []) if o]
    s = norm(value)
    if not s:
        return None, True
    for o in options:
        if norm(o) == s:
            return o, True
    hits = [o for o in options if s in norm(o) or norm(o) in s]
    if len(hits) == 1:
        return hits[0], True
    return value, False


def convert(field, raw, problems, row_no, header):
    t = field["type"]
    name = field["name"]
    s = str(raw or "").strip()
    if not s:
        return None

    if t == "date":
        d = parse_date(s)
        if d is None:
            problems.append("第 %d 列「%s」：看不懂的日期 %r" % (row_no, header, s))
        return d

    if t == "bool":
        b = parse_bool(s)
        if b == "?":
            problems.append("第 %d 列「%s」：看不懂的是/否 %r" % (row_no, header, s))
            return None
        return b

    if t == "int":
        if name == "birth_year":
            d = parse_date(s)
            if d:
                return int(d[:4])
            m = re.search(r"(\d{2,4})", s)
            if m:
                y = int(m.group(1))
                if y < 200:
                    y += 1911
                if 1900 <= y <= 2100:
                    return y
            problems.append("第 %d 列「%s」：看不懂的出生年 %r" % (row_no, header, s))
            return None
        m = re.search(r"-?\d+", s.replace(",", ""))
        if not m:
            problems.append("第 %d 列「%s」：不是數字 %r" % (row_no, header, s))
            return None
        return int(m.group())

    if t == "real":
        m = re.search(r"-?\d+(\.\d+)?", s.replace(",", ""))
        if not m:
            problems.append("第 %d 列「%s」：不是數字 %r" % (row_no, header, s))
            return None
        return float(m.group())

    if name == "sex":
        hit = SEX_MAP.get(norm(s))
        if hit:
            return hit
        problems.append("第 %d 列「%s」：看不懂的性別 %r" % (row_no, header, s))
        return None

    if t == "select":
        val, ok = match_option(field, s)
        if not ok:
            problems.append("第 %d 列「%s」：%r 對不到唯一選項，會原樣存入，"
                            "請匯入後手動確認" % (row_no, header, s))
        return val

    if t == "multi":
        parts = [p for p in re.split(r"[;,、，/\|]+", s) if p.strip()]
        out = []
        for p in parts:
            val, ok = match_option(field, p.strip())
            if ok and val:
                out.append(val)
            elif not ok:
                problems.append("第 %d 列「%s」：%r 對不到唯一選項，已略過"
                                % (row_no, header, p.strip()))
        return out

    return s


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

# 可識別欄位的範例值一律遮蔽 —— 這張表常被截圖出去問人，
# 不該因為要確認對應就把病人姓名一起送出去。
IDENTIFYING = {"patient_name", "chart_no", "phone"}
IDENTIFYING_WORDS = ["姓名", "名字", "病歷", "身分證", "電話", "手機", "name", "phone", "tel"]


def _mask(header, target, value):
    if target in IDENTIFYING:
        return "（已遮蔽）"
    key = norm(header)
    if any(w in key for w in (norm(x) for x in IDENTIFYING_WORDS)):
        return "（已遮蔽）"
    return value


def do_inspect(rows, args):
    headers = [str(h).strip() for h in rows[0]]
    mapping = guess_mapping(headers)

    print("\n檔案裡有 %d 欄、%d 列資料（不含標題列）。\n" % (len(headers), len(rows) - 1))
    print("%-24s %-22s %s" % ("你的欄位", "對應到系統欄位", "第一筆的值"))
    print("-" * 78)
    sample = rows[1] if len(rows) > 1 else []
    masked = 0
    for i, h in enumerate(headers):
        target = mapping[h]
        label = FIELD_MAP[target]["label"] if target else "（不匯入）"
        val = str(sample[i]) if i < len(sample) else ""
        shown = _mask(h, target, val)
        if shown != val:
            masked += 1
        print("%-24s %-22s %s" % (h[:22], label[:20], shown[:26]))

    if masked:
        print("\n（姓名、病歷號、電話等欄位的範例值已自動遮蔽，"
              "這張表可以直接截圖問人。實際匯入不受影響。）")

    with open(MAPPING_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "_說明": "把不要匯入的欄位設成 null。可用的系統欄位名稱見下方 _可用欄位。",
            "_可用欄位": {f["name"]: f["label"] for f in FIELDS},
            "對應": mapping,
        }, fh, ensure_ascii=False, indent=2)

    print("\n對應表已寫到：%s" % MAPPING_PATH)
    print("請用記事本打開檢查，改好之後執行：")
    print("    python tools/import_data.py --file %s --dry-run" % args.file)


def load_mapping(headers):
    if not os.path.exists(MAPPING_PATH):
        print("找不到對應表，先用自動猜的結果。")
        print("（建議先跑 --inspect 檢查對應是否正確）\n")
        return guess_mapping(headers)
    with open(MAPPING_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    mapping = data.get("對應", {})
    for name in mapping.values():
        if name is not None and name not in FIELD_MAP:
            raise SystemExit("對應表裡有不存在的系統欄位：%s" % name)
    return mapping


def build_cases(rows, mapping, args):
    headers = [str(h).strip() for h in rows[0]]
    problems, cases = [], []
    year = args.case_no_year

    for n, row in enumerate(rows[1:], start=2):
        case, has_data = {}, False
        for i, h in enumerate(headers):
            target = mapping.get(h)
            if not target:
                continue
            raw = row[i] if i < len(row) else ""
            if not str(raw).strip():
                continue
            value = convert(FIELD_MAP[target], raw, problems, n, h)
            if value not in (None, [], ""):
                case[target] = value
                has_data = True
        if not has_data:
            continue
        if not case.get("case_no"):
            case["case_no"] = "%s-%03d" % (year, len(cases) + 1)
        cases.append((n, case))
    return cases, problems


def main():
    ap = argparse.ArgumentParser(
        description="把 Excel / CSV 的既有個案匯入系統（全程在本機執行）")
    ap.add_argument("--file", required=True, help=".xlsx 或 .csv 檔案路徑")
    ap.add_argument("--sheet", type=int, default=1, help="第幾個工作表（預設 1）")
    ap.add_argument("--inspect", action="store_true", help="檢視欄位並產生對應表")
    ap.add_argument("--dry-run", action="store_true", help="試跑，檢查但不寫入")
    ap.add_argument("--commit", action="store_true", help="真的寫入資料庫")
    ap.add_argument("--update", action="store_true",
                    help="個案編號已存在時更新該筆，預設是略過")
    ap.add_argument("--case-no-year", default="IMPORT",
                    help="自動產生個案編號時的前綴（預設 IMPORT）")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        raise SystemExit("找不到檔案：%s" % args.file)
    if not (args.inspect or args.dry_run or args.commit):
        raise SystemExit("請指定 --inspect、--dry-run 或 --commit 其中一個。")

    rows = read_table(args.file, args.sheet)

    if args.inspect:
        return do_inspect(rows, args)

    db.init_db()
    mapping = load_mapping([str(h).strip() for h in rows[0]])
    cases, problems = build_cases(rows, mapping, args)

    used = sorted({v for v in mapping.values() if v})
    print("\n對應了 %d 個欄位：%s" % (
        len(used), "、".join(FIELD_MAP[u]["label"] for u in used)))
    print("讀到 %d 筆個案。" % len(cases))

    if problems:
        print("\n有 %d 個值需要你確認：" % len(problems))
        for p in problems[:40]:
            print("  - " + p)
        if len(problems) > 40:
            print("  …還有 %d 個，修好上面的再重跑" % (len(problems) - 40))
    else:
        print("\n所有值都看得懂，沒有問題。")

    existing = {c["case_no"] for c in db.all_cases() if c.get("case_no")}
    dup = [(n, c) for n, c in cases if c["case_no"] in existing]
    if dup:
        print("\n有 %d 筆的個案編號已存在：%s" % (
            len(dup), "、".join(c["case_no"] for _, c in dup[:5])))
        print("  目前設定：%s" % ("更新既有資料" if args.update else "略過不匯入"))

    if args.dry_run:
        print("\n這是試跑，沒有寫入任何東西。")
        print("確認無誤後執行：")
        print("    python tools/import_data.py --file %s --commit" % args.file)
        return

    print("\n即將寫入 %s" % db.DB_PATH)
    if input("確定要匯入嗎？輸入 yes 繼續：").strip().lower() != "yes":
        print("已取消，沒有寫入任何東西。")
        return

    id_by_no = {c["case_no"]: c["id"] for c in db.all_cases() if c.get("case_no")}
    added = updated = skipped = 0
    for n, case in cases:
        try:
            if case["case_no"] in id_by_no:
                if not args.update:
                    skipped += 1
                    continue
                db.save_case(case, "import", id_by_no[case["case_no"]])
                updated += 1
            else:
                db.save_case(case, "import")
                added += 1
        except ValueError as exc:
            print("  第 %d 列匯入失敗：%s" % (n, exc))
            skipped += 1

    db.audit("import", "local", "import",
             detail={"file": os.path.basename(args.file),
                     "added": added, "updated": updated, "skipped": skipped})
    print("\n完成：新增 %d 筆、更新 %d 筆、略過 %d 筆。" % (added, updated, skipped))
    print("打開網站的「個案追蹤」就看得到了。")


if __name__ == "__main__":
    main()
