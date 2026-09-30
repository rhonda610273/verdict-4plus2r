#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 fields.py 產生資料字典 docs/DATA_MODEL.md。

改完 fields.py 之後執行一次，文件就會跟著更新：
    python3 tools/gen_datadict.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fields import FIELDS, GROUPS  # noqa: E402

TYPE_LABEL = {
    "text": "文字", "textarea": "長文字", "int": "整數", "real": "小數",
    "date": "日期", "bool": "是/否", "select": "單選", "multi": "複選",
}

HEADER = """# 資料字典

> 這份文件由 `tools/gen_datadict.py` 從 `fields.py` 自動產生，請勿手動編輯。
> 修改欄位請改 `fields.py`，然後重新執行該腳本。

欄位設計參考 ATS/IDSA/ERS/ESCMID 2020 年 NTM 肺病治療指引，
以及常見的 NTM 世代研究登錄項目。實際使用時請依科內需求增刪。

## 系統自動產生的欄位

| 欄位 | 說明 |
|---|---|
| `id` | 內部流水號 |
| `ats_met` | 三項 ATS/IDSA 條件是否皆符合（由臨床／影像／微生物三個勾選欄位計算） |
| `age_at_dx` | 確診年齡 = 確診日期年份 − 出生年 |
| `treatment_months` | 療程月數 = (治療結束日 − 治療開始日) / 30.44 |
| `created_at` / `created_by` | 建檔時間與建檔者 |
| `updated_at` / `updated_by` | 最後修改時間與修改者 |
| `deleted` | 軟刪除旗標，刪除的個案不會真的消失 |

## 登錄欄位
"""

FOOTER = """
---

## 定義註記

填寫前建議先在科內統一以下定義，並寫進填寫規範：

* **確診日期** — 建議採「第一次同時滿足 ATS/IDSA 臨床、影像、微生物三項條件」的日期。
* **微生物條件** — ATS/IDSA 標準為：≥2 套分開採檢的痰液培養陽性，或 1 套支氣管沖洗液／
  BAL 培養陽性，或肺組織切片有分枝桿菌組織學特徵且培養陽性。
* **培養轉陰** — 本系統採「連續 ≥3 次培養陰性」，日期記錄第一次陰性的採檢日。
* **持續轉陰 12 個月** — 轉陰後持續陰性滿 12 個月，且療程結束時仍為陰性。
* **復發 vs. 再感染** — 需菌株基因型比對才能區分；無法比對時請填「不詳」。
* **M. abscessus 的 erm(41)** — 功能型會造成誘導型 macrolide 抗藥，影響處方選擇，
  建議常規記錄。

## 匯出

網頁上「匯出 CSV」會輸出所有登錄欄位加上系統自動欄位。
複選欄位以分號 `;` 分隔，是/否欄位輸出「是」／「否」，檔案帶 UTF-8 BOM，
Excel 直接打開不會亂碼，也可直接用 R 的 `read.csv(..., fileEncoding="UTF-8-BOM")` 讀入。
"""


def main():
    out = [HEADER]
    for key, label in GROUPS:
        fs = [f for f in FIELDS if f["group"] == key]
        if not fs:
            continue
        out.append("\n### %s\n" % label)
        out.append("| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |")
        out.append("|---|---|---|---|")
        for f in fs:
            note = ""
            if f["type"] in ("select", "multi"):
                opts = [o for o in f.get("options", []) if o]
                note = "、".join(opts)
            if f.get("hint"):
                note = (note + "<br>" if note else "") + "＊" + f["hint"]
            if f.get("required"):
                note = (note + "<br>" if note else "") + "**必填**"
            out.append("| `%s` | %s | %s | %s |" % (
                f["name"], f["label"], TYPE_LABEL[f["type"]], note.replace("|", "\\|")))
    out.append(FOOTER)

    target = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "DATA_MODEL.md")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("已產生 %s（%d 個欄位）" % (target, len(FIELDS)))


if __name__ == "__main__":
    main()
