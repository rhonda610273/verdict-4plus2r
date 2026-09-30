# -*- coding: utf-8 -*-
"""欄位定義。

臨床欄位不是手寫的，而是由 REDCap 資料字典自動生成（fields_generated.py）。
427 個欄位手打必然出錯，而且 REDCap 一改就會不同步。要更新：

    python3 tools/redcap_to_fields.py --dd 你的資料字典.csv

這個檔案負責的是「生成結果之外的東西」：語意對照、清單欄位、統計欄位，
以及追蹤紀錄的時間點定義。
"""

from fields_generated import (
    CASE_FIELDS as _GEN_CASE_FIELDS,
    VISIT_FIELDS as _GEN_VISIT_FIELDS,
    CASE_GROUPS as _GEN_CASE_GROUPS,
    REDCAP_MAP,
)

# --------------------------------------------------------------------------
# 語意對照：程式邏輯只認這些角色，不直接寫死 REDCap 的變數名。
# REDCap 改欄位時，只要改這裡就好。
# --------------------------------------------------------------------------
KEY = {
    "id": "patient_code",                    # 唯一識別碼（去識別化編號）
    "site": "hospital_site",                 # 收案醫院
    "group": "observe_or_treat_group",       # 觀察組 / 治療組
    "species": "ntm_species",                # 主要致病菌
    "enroll_date": "date_enrolled",          # 收案日期
    "sex": "sex",
    "age": "age",
    "pattern": "ct_imagepattern",            # 影像型態
    "treated": "start_treatment",            # 收案時是否啟動治療
    "first_positive": "ntm_positive_day",
    "afs": "afs_initial",
    "afs_titer": "afs_titer_initial",    # 首次培養陽性日
}

# 只保留本院個案 —— 其他醫院的資料不進本平台
OUR_SITE = "北榮"
OUR_SITE_CODE = "001"          # patient_code 中段的醫院碼

# --------------------------------------------------------------------------
# 個案層
# --------------------------------------------------------------------------

# REDCap 有些欄位沒填標題，生成時只好用變數名，這裡補上看得懂的中文
LABEL_OVERRIDES = {
    "observe_or_treat_group": "組別",
    "patient_code": "病人編號",
    "hospital_site": "收案醫院",
    "date_enrolled": "簽署同意書日期",
    "dob": "出生日期",
    "age": "年齡",
    "sex": "性別",
    "height": "身高 (cm)",
    "weight": "體重 (kg)",
    "smoke": "吸菸史",
    "ntm_species": "主要致病菌",
    "ntm_positive_day": "首次痰培養陽性日期",
    "ct_imagepattern": "胸部電腦斷層影像型態",
    "start_treatment": "收案時是否啟動治療",
    "cough_rss": "咳嗽 (RSS)",
    "dyspnea_rss": "喘 (RSS)",
    "phlegm_rss": "痰 (RSS)",
    "hemoptysis_rss": "咳血 (RSS)",
    "chesttightness_rss": "胸悶 (RSS)",
    "sleepdistrubance_rss": "睡眠中斷 (RSS)",
    "total_rss_score": "RSS 總分",
    "mmrc": "mMRC 分數",
    "afs_initial": "痰液抗酸染色抹片",
    "ntm_sputumculture_initial": "痰液分枝桿菌培養",
    "cxr": "胸部 X 光變化",
    "follow_up_status": "追蹤狀態",
    "last_followup_date": "最後追蹤時間",
}

FIELDS = [dict(f) for f in _GEN_CASE_FIELDS]

for _f in FIELDS:
    if _f["name"] in LABEL_OVERRIDES:
        _f["label"] = LABEL_OVERRIDES[_f["name"]]
    if _f["name"] == KEY["id"]:
        _f["required"] = True
        _f["unique"] = True
        _f["hint"] = "去識別化編號，格式 組別-醫院碼-年月-個案序（例 T-001-2410-001）"

FIELD_MAP = {f["name"]: f for f in FIELDS}

GROUPS = [(g, g) for g in _GEN_CASE_GROUPS]

# --------------------------------------------------------------------------
# 追蹤層（一個個案多次）
# --------------------------------------------------------------------------

# 事件代碼沿用 REDCap 的 redcap_event_name，匯入時才對得上
VISIT_EVENTS = [
    ("v1_arm_1", "收案 V1"),
    ("3_arm_1", "治療組第 3 個月"),
    ("v2_arm_1", "第 6 個月 V2"),
    ("12v3_arm_1", "第 12 個月 V3"),
    ("18v4_arm_1", "第 18 個月 V4"),
    ("24v5_arm_1", "第 24 個月 V5"),
    ("3e72e62e9d_arm_1", "治療結束／死亡"),
    ("852886ad86_arm_1", "觀察組追蹤狀態"),
    ("other", "其他"),
]
EVENT_LABEL = dict(VISIT_EVENTS)

_EVENT_FIELD = dict(
    name="event", label="追蹤時間點", type="select", group="本次追蹤",
    options=[""] + [label for _, label in VISIT_EVENTS],
    required=True,
)
_DATE_FIELD = dict(name="visit_date", label="訪視日期", type="date", group="本次追蹤")

VISIT_FIELDS = [_EVENT_FIELD, _DATE_FIELD]
for _f in (dict(f) for f in _GEN_VISIT_FIELDS):
    if _f["name"] in ("event", "visit_date"):
        continue
    if _f["name"] in LABEL_OVERRIDES:
        _f["label"] = LABEL_OVERRIDES[_f["name"]]
    VISIT_FIELDS.append(_f)
VISIT_FIELD_MAP = {f["name"]: f for f in VISIT_FIELDS}

VISIT_GROUPS = []
for _f in VISIT_FIELDS:
    _g = _f.get("group", "其他")
    if _g not in VISIT_GROUPS:
        VISIT_GROUPS.append(_g)

# 追蹤摘要列上要顯示哪幾項（欄位不存在就自動略過）
VISIT_SUMMARY = ["ntm_sputumculture_initial", "cxr", "total_rss_score",
                 "adverse_effect", "stop_treatment"]

# --------------------------------------------------------------------------
# 清單與統計
# --------------------------------------------------------------------------

SQL_TYPE = {
    "text": "TEXT", "textarea": "TEXT", "select": "TEXT", "multi": "TEXT",
    "date": "TEXT", "int": "INTEGER", "real": "REAL", "bool": "INTEGER",
}

LIST_COLUMNS = [KEY["id"], KEY["group"], KEY["sex"], KEY["age"],
                KEY["species"], KEY["enroll_date"]]
LIST_COLUMNS = [c for c in LIST_COLUMNS if c in FIELD_MAP]

# 搜尋會掃這幾個欄位
SEARCH_COLUMNS = [c for c in (KEY["id"], KEY["species"], "ntm_species_other")
                  if c in FIELD_MAP]

# 儀表板要分組計數的欄位
STAT_FIELDS = [c for c in (KEY["species"], KEY["group"], KEY["sex"],
                           KEY["pattern"], "smoke",
                           KEY["afs"], KEY["afs_titer"])
               if c in FIELD_MAP]

# 有序欄位：抹片價數是有序變項，要照 0 → 4+ 排，不能照數量多寡排，
# 否則「價數愈高菌量愈多」這件事在圖上就看不出來了。
# 沒列在這裡的值排在後面，資料有髒東西也不會整個亂掉。
ORDERED_VALUES = {
    KEY["afs_titer"]: ["0", "trace", "1+", "2+", "3+", "4+"],
}

# 空值沒有意義的欄位：只有抹片陽性的個案才會有價數，
# 把「未填」一起畫進去會讓長條圖被一根巨大的未填吃掉。
SKIP_BLANK_FIELDS = {KEY["afs_titer"]}
