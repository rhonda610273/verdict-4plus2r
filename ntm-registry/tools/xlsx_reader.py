# -*- coding: utf-8 -*-
"""極簡 .xlsx 讀取器，只用 Python 標準函式庫。

醫院電腦通常裝不了 openpyxl，所以自己解析。
.xlsx 本質上是一個 zip，裡面放 XML。
"""

import datetime
import re
import zipfile
import xml.etree.ElementTree as ET

# Excel 的日期原點是 1899-12-30（因為它沿用了 Lotus 1-2-3 把 1900 當閏年的錯誤）
EXCEL_EPOCH = datetime.date(1899, 12, 30)

# 內建的日期/時間格式代碼
BUILTIN_DATE_FMTS = set(range(14, 23)) | set(range(45, 48))


def _tag(elem):
    """去掉 XML 命名空間，只留標籤名。"""
    return elem.tag.rsplit("}", 1)[-1]


def _find_all(root, name):
    return [e for e in root.iter() if _tag(e) == name]


def _shared_strings(zf):
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root:
        if _tag(si) != "si":
            continue
        # 一個 si 可能被拆成多個 r/t 片段（字型不同時），要全部串起來
        out.append("".join(t.text or "" for t in si.iter() if _tag(t) == "t"))
    return out


def _date_style_indexes(zf):
    """回傳哪些樣式索引代表日期格式。"""
    try:
        root = ET.fromstring(zf.read("xl/styles.xml"))
    except KeyError:
        return set()

    custom_date = set()
    for nf in _find_all(root, "numFmt"):
        code = (nf.get("formatCode") or "").lower()
        # 去掉引號內的字面文字再判斷，避免把 "年" 之類誤判
        stripped = re.sub(r'"[^"]*"', "", code)
        if re.search(r"[ymdhs]", stripped) and "general" not in stripped:
            custom_date.add(int(nf.get("numFmtId")))

    date_styles = set()
    cell_xfs = None
    for e in root:
        if _tag(e) == "cellXfs":
            cell_xfs = e
            break
    if cell_xfs is None:
        return set()
    for idx, xf in enumerate(cell_xfs):
        fmt_id = int(xf.get("numFmtId") or 0)
        if fmt_id in BUILTIN_DATE_FMTS or fmt_id in custom_date:
            date_styles.add(idx)
    return date_styles


def _col_index(ref):
    """A1 → 0、B1 → 1、AA1 → 26。"""
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return None
    n = 0
    for ch in letters.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def sheet_names(path):
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist()
                 if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
    return sorted(names, key=lambda n: int(re.search(r"(\d+)", n).group(1)))


def read_rows(path, sheet=1):
    """讀出指定工作表的所有列，回傳 list[list[str]]。空白儲存格為空字串。"""
    with zipfile.ZipFile(path) as zf:
        strings = _shared_strings(zf)
        date_styles = _date_style_indexes(zf)
        sheets = sheet_names(path)
        if not sheets:
            raise ValueError("這個檔案裡找不到工作表")
        if sheet < 1 or sheet > len(sheets):
            raise ValueError("工作表編號超出範圍（共 %d 個）" % len(sheets))
        root = ET.fromstring(zf.read(sheets[sheet - 1]))

    rows = []
    for row in _find_all(root, "row"):
        cells = {}
        for c in row:
            if _tag(c) != "c":
                continue
            idx = _col_index(c.get("r"))
            if idx is None:
                continue
            ctype = c.get("t")
            style = c.get("s")
            value = ""

            if ctype == "inlineStr":
                value = "".join(t.text or "" for t in c.iter() if _tag(t) == "t")
            else:
                v = None
                for child in c:
                    if _tag(child) == "v":
                        v = child.text
                        break
                if v is None:
                    value = ""
                elif ctype == "s":
                    i = int(v)
                    value = strings[i] if 0 <= i < len(strings) else ""
                elif ctype == "b":
                    value = "是" if v == "1" else "否"
                else:
                    value = v
                    # 有日期格式的數值要換算回日期
                    if style is not None and int(style) in date_styles:
                        try:
                            serial = float(v)
                            d = EXCEL_EPOCH + datetime.timedelta(days=int(serial))
                            value = d.isoformat()
                        except (ValueError, OverflowError):
                            pass
                    elif value and re.fullmatch(r"-?\d+\.0+", value):
                        value = value.split(".")[0]      # 3.0 → 3

            cells[idx] = (value or "").strip()

        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(i, "") for i in range(width)])
    return rows
