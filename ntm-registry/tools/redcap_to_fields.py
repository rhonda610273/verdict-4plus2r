#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 REDCap 資料字典產生欄位定義。

    python3 tools/redcap_to_fields.py --dd NTMPDTAIWAN_DataDictionary.csv

427 個欄位手打一定會錯，所以直接讀 REDCap 的資料字典生成 fields_generated.py。
之後 REDCap 改欄位，重跑一次就同步了。

產生的內容：
  CASE_FIELDS   —— 由 baseline_v1 表單而來，一個病人一列
  VISIT_FIELDS  —— 由 v2/v3/v4/v5 追蹤表單合併而來，一個病人多列
  EXTRA_FORMS   —— daae（第3個月）、daae_8e12（治療結束/死亡）、ddcd（觀察組追蹤）
  REDCAP_MAP    —— REDCap 變數名 → 本系統欄位名，匯入時用
"""

import argparse
import csv
import io
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# REDCap 欄位型別 → 本系統型別
TYPE_MAP = {
    "text": "text", "notes": "textarea", "radio": "select",
    "dropdown": "select", "checkbox": "multi", "yesno": "bool",
    "truefalse": "bool", "calc": "real", "slider": "int",
}
SKIP_TYPES = {"descriptive", "file", "signature"}

# REDCap 的文字驗證 → 更精確的型別
VALIDATION_MAP = {
    "integer": "int", "number": "real", "number_1dp": "real",
    "number_2dp": "real", "date_ymd": "date", "date_mdy": "date",
    "date_dmy": "date", "datetime_ymd": "date",
}

FOLLOWUP_FORMS = ("v2", "v3", "v4", "v5")

# 額外三張表單各自成為一個分組
FORM_LABELS = {
    "daae": "治療組第 3 個月",
    "daae_8e12": "治療結束與死亡",
    "ddcd": "觀察組追蹤狀態",
}
# 追蹤欄位的權威定義取自 v3（欄位最完整，含 CT 與肺功能）
CANONICAL_FORM = "v3"


def clean(text):
    """去掉 HTML 標籤與多餘空白。"""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def read_dd(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SystemExit("看不懂資料字典的編碼")
    rows = list(csv.reader(io.StringIO(text)))
    header, body = rows[0], rows[1:]
    idx = {name: i for i, name in enumerate(header)}

    def col(row, key, default=""):
        i = idx.get(key)
        return row[i] if i is not None and i < len(row) else default

    out = []
    for row in body:
        if not row or not row[0].strip():
            continue
        out.append({
            "var": row[0].strip(),
            "form": col(row, "Form Name").strip(),
            "section": clean(col(row, "Section Header")),
            "type": col(row, "Field Type").strip(),
            "label": clean(col(row, "Field Label")),
            "choices": col(row, "Choices, Calculations, OR Slider Labels"),
            "note": clean(col(row, "Field Note")),
            "validation": col(row, "Text Validation Type OR Show Slider Number").strip(),
        })
    return out


def parse_choices(raw):
    """'0, 陰性 | 1, 陽性' → [('0','陰性'), ('1','陽性')]"""
    out = []
    for part in (raw or "").split("|"):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            code, label = part.split(",", 1)
            out.append((code.strip(), clean(label)))
        else:
            out.append((part, clean(part)))
    return out


def strip_suffix(var):
    """把 cough_rss_v2 / shift_regiment_causev3 都還原成同一個基底名稱。"""
    return re.sub(r"_?v[2-5]$", "", var)


def to_field(entry, name=None):
    ftype = TYPE_MAP.get(entry["type"])
    if ftype is None:
        return None
    if ftype == "text" and entry["validation"]:
        ftype = VALIDATION_MAP.get(entry["validation"], "text")

    field = {
        "name": name or entry["var"],
        "label": entry["label"] or entry["var"],
        "type": ftype,
    }
    if ftype in ("select", "multi"):
        choices = parse_choices(entry["choices"])
        labels = [label for _, label in choices]
        field["options"] = ([""] + labels) if ftype == "select" else labels
        field["codes"] = {code: label for code, label in choices}
    if entry["note"]:
        field["hint"] = entry["note"][:120]
    return field


def build(entries):
    by_form = {}
    for e in entries:
        by_form.setdefault(e["form"], []).append(e)

    # REDCap 的段落標題只出現在該段第一個欄位上，要往後延續
    for form_entries in by_form.values():
        current = ""
        for e in form_entries:
            if e["section"]:
                current = e["section"]
            e["section"] = current or "其他"

    # ---- 個案層（收案表） ----
    case_fields, case_map = [], {}
    for e in by_form.get("baseline_v1", []):
        if e["type"] in SKIP_TYPES:
            continue
        f = to_field(e)
        if f:
            f["group"] = e["section"]
            case_fields.append(f)
            case_map[e["var"]] = f["name"]

    # ---- 追蹤層（v2~v5 合併） ----
    canonical, visit_map = {}, {}
    for form in (CANONICAL_FORM,) + tuple(f for f in FOLLOWUP_FORMS if f != CANONICAL_FORM):
        for e in by_form.get(form, []):
            if e["type"] in SKIP_TYPES:
                continue
            base = strip_suffix(e["var"])
            if base not in canonical:
                f = to_field(e, name=base)
                if not f:
                    continue
                f["group"] = e["section"]
                canonical[base] = f
            visit_map[e["var"]] = base

    visit_fields = list(canonical.values())

    # ---- 其他三張表也併進追蹤層，用同一套結構存 ----
    extra_map = {}
    for form in ("daae", "daae_8e12", "ddcd"):
        for e in by_form.get(form, []):
            if e["type"] in SKIP_TYPES:
                continue
            base = strip_suffix(e["var"])
            if base not in canonical:
                f = to_field(e, name=base)
                if not f:
                    continue
                f["group"] = FORM_LABELS.get(form, e["section"])
                canonical[base] = f
                visit_fields.append(f)
            extra_map[e["var"]] = base

    return case_fields, visit_fields, case_map, visit_map, extra_map


def group_list(fields):
    """依欄位出現順序列出分組，順序就是表單上的順序。"""
    seen = []
    for f in fields:
        g = f.get("group", "其他")
        if g not in seen:
            seen.append(g)
    return seen


def render(fields):
    lines = []
    for f in fields:
        parts = ['name=%r' % f["name"], 'label=%r' % f["label"], 'type=%r' % f["type"],
                 'group=%r' % f.get("group", "其他")]
        if "options" in f:
            parts.append('options=%r' % (f["options"],))
        if "codes" in f:
            parts.append('codes=%r' % (f["codes"],))
        if "hint" in f:
            parts.append('hint=%r' % f["hint"])
        lines.append("    dict(%s)," % ", ".join(parts))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dd", required=True, help="REDCap 資料字典 CSV")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "fields_generated.py"))
    args = ap.parse_args()

    entries = read_dd(args.dd)
    case_fields, visit_fields, case_map, visit_map, extra_map = build(entries)

    redcap_map = {}
    redcap_map.update({k: ("case", v) for k, v in case_map.items()})
    redcap_map.update({k: ("visit", v) for k, v in visit_map.items()})
    redcap_map.update({k: ("visit", v) for k, v in extra_map.items()})

    body = '''# -*- coding: utf-8 -*-
"""由 REDCap 資料字典自動產生，請勿手動編輯。

重新產生：
    python3 tools/redcap_to_fields.py --dd 你的資料字典.csv

codes 是 REDCap 的代碼對照（例 "0" → "陰性"），匯入原始碼值時用得到。
"""

# 個案層欄位（REDCap baseline_v1，一個病人一列）
CASE_FIELDS = [
%s
]

# 追蹤層欄位（REDCap v2~v5 與其他表單合併，一個病人多列）
VISIT_FIELDS = [
%s
]

# REDCap 變數名 → ("case"|"visit", 本系統欄位名)
REDCAP_MAP = %r

CASE_GROUPS = %r
VISIT_GROUPS = %r
''' % (render(case_fields), render(visit_fields), redcap_map,
        group_list(case_fields), group_list(visit_fields))

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(body)

    print("已產生 %s" % args.out)
    print("  個案層分組：%s" % "、".join(group_list(case_fields)))
    print("  追蹤層分組：%s" % "、".join(group_list(visit_fields)))
    print("  個案層欄位：%d" % len(case_fields))
    print("  追蹤層欄位：%d" % len(visit_fields))
    print("  REDCap 變數對照：%d" % len(redcap_map))
    skipped = [e["var"] for e in entries if e["type"] in SKIP_TYPES]
    if skipped:
        print("  略過（說明文字/檔案類）：%d 個" % len(skipped))


if __name__ == "__main__":
    main()
