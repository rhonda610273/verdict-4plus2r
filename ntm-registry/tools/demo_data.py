#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""產生示範個案，讓你在還沒開始收案前就能看到儀表板長什麼樣。

    python3 tools/demo_data.py --yes          # 產生 60 筆示範個案
    python3 tools/demo_data.py --yes -n 200   # 指定筆數
    python3 tools/demo_data.py --clear        # 把示範個案全部刪掉

所有示範個案的研究編號都以 DEMO- 開頭，跟真實個案一眼可分，
也可以用 --clear 一次清乾淨。資料是亂數生成的，不對應任何真人。
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db  # noqa: E402

PREFIX = "DEMO-"

SPECIES = (["MAC – M. avium"] * 22 + ["MAC – M. intracellulare"] * 14
           + ["M. abscessus subsp. abscessus"] * 9
           + ["M. abscessus subsp. massiliense"] * 6 + ["M. kansasii"] * 5
           + ["M. fortuitum"] * 3 + ["M. chelonae"] * 2 + ["混合感染"] * 2)
PATTERN = (["結節-支氣管擴張型 (NB)"] * 38 + ["纖維空洞型 (FC)"] * 12
           + ["混合型"] * 9 + ["孤立性結節/腫塊"] * 4)
OUTCOME = (["治癒/完成療程"] * 20 + ["治療中"] * 18 + ["僅觀察追蹤"] * 11
           + ["治療失敗"] * 5 + ["復發"] * 4 + ["中止治療"] * 3 + ["死亡"] * 2)
SIR = ["S 敏感"] * 7 + ["R 抗藥"] * 2 + ["I 中間"]
REGIMENS = [
    ["Azithromycin", "Ethambutol", "Rifampin"],
    ["Clarithromycin", "Ethambutol", "Rifampin"],
    ["Azithromycin", "Ethambutol", "Rifampin", "Amikacin IV"],
    ["Azithromycin", "Clofazimine", "Ethambutol"],
]


def _next_followup(status):
    """追蹤中的個案排一個未來或已逾期的日期，其餘不排。"""
    if status != "追蹤中":
        return None
    from datetime import date, timedelta
    offset = random.choices([-60, -20, -5, 10, 40, 90],
                            weights=[4, 6, 5, 20, 20, 15])[0]
    return (date.today() + timedelta(days=offset)).isoformat()


def make_case(i, year):
    month = random.randint(1, 12)
    dx = "%04d-%02d-%02d" % (year, month, random.randint(1, 28))
    outcome = random.choice(OUTCOME)
    treated = outcome != "僅觀察追蹤"
    converted = treated and random.random() < 0.62
    surnames = "陳林黃張李王吳劉蔡楊許鄭謝洪郭邱曾廖賴徐"
    status = random.choices(
        ["追蹤中", "結案", "暫停追蹤", "轉出他院", "失聯"],
        weights=[62, 20, 7, 6, 5])[0]
    case = {
        "case_no": "%s%d-%03d" % (PREFIX, year, i),
        "chart_no": "%07d" % random.randint(1000000, 9999999),
        "patient_name": random.choice(surnames) + random.choice("○＊") + "○",
        "phone": "09%02d-%03d-%03d" % (random.randint(0, 99), random.randint(0, 999),
                                       random.randint(0, 999)),
        "case_status": status,
        "followup_interval": random.choice(["每月", "每 2 個月", "每 3 個月", "每 6 個月"]),
        "next_followup": _next_followup(status),
        "enroll_date": dx, "diagnosis_date": dx,
        "sex": random.choices(["女", "男"], weights=[62, 38])[0],
        "birth_year": year - random.choices(
            [35, 45, 55, 62, 68, 74, 81], weights=[3, 6, 12, 16, 18, 14, 8])[0],
        "bmi": round(random.uniform(16.5, 26.0), 1),
        "smoking": random.choice(["從未", "從未", "已戒菸", "現行吸菸"]),
        "species": random.choice(SPECIES),
        "radiographic_pattern": random.choice(PATTERN),
        "cavity": random.random() < 0.28,
        "disease_form": "肺部感染",
        "specimen_types": random.sample(
            ["自然痰", "誘導痰", "支氣管沖洗液/BAL"], k=random.randint(1, 2)),
        "symptoms": random.sample(
            ["慢性咳嗽", "咳痰", "咳血", "呼吸困難", "體重減輕", "疲倦"],
            k=random.randint(1, 4)),
        "positive_culture_count": random.choice([1, 2, 2, 3]),
        "ats_clinical": random.random() < 0.88,
        "ats_radiographic": random.random() < 0.92,
        "ats_micro": random.random() < 0.85,
        "treated": treated,
        "outcome": outcome,
        "culture_conversion": converted,
        "sustained_conversion_12m": converted and random.random() < 0.7,
        "notes": "示範資料，非真實個案",
    }
    for name, p in (("cm_bronchiectasis", .58), ("cm_copd", .24), ("cm_prior_tb", .21),
                    ("cm_dm", .17), ("cm_gerd", .14), ("cm_malignancy", .10),
                    ("cm_immunosuppressant", .09), ("cm_asthma", .08)):
        case[name] = random.random() < p
    if treated:
        case["treatment_start"] = "%04d-%02d-15" % (year, min(12, month + 1))
        case["regimen"] = random.choice(REGIMENS)
        case["dosing_schedule"] = random.choice(["每日", "每週三次"])
    if random.random() < 0.55:
        case["dst_done"] = True
        case["dst_clarithromycin"] = random.choice(SIR)
        case["dst_amikacin"] = random.choice(SIR)
        if random.random() < 0.6:
            case["dst_moxifloxacin"] = random.choice(SIR)
        if random.random() < 0.4:
            case["dst_linezolid"] = random.choice(SIR)
    return case


def clear():
    conn = db.connect()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE cases SET deleted=1, updated_at=?"
                " WHERE deleted=0 AND case_no LIKE ?", (db.now(), PREFIX + "%"))
        return cur.rowcount
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=60, help="產生筆數（預設 60）")
    ap.add_argument("--years", type=int, default=6, help="分布在最近幾年（預設 6）")
    ap.add_argument("--yes", action="store_true", help="確認要寫入資料庫")
    ap.add_argument("--clear", action="store_true", help="刪除所有示範個案")
    ap.add_argument("--seed", type=int, help="亂數種子，指定後結果可重現")
    args = ap.parse_args()

    db.init_db()

    if args.clear:
        print("已刪除 %d 筆示範個案。" % clear())
        return 0

    if not args.yes:
        print(__doc__)
        print("請加上 --yes 確認要寫入 %s" % db.DB_PATH)
        return 1

    if args.seed is not None:
        random.seed(args.seed)

    from datetime import datetime
    this_year = datetime.now(db.TAIPEI).year
    years = list(range(this_year - args.years + 1, this_year + 1))
    weights = [i + 1 for i in range(len(years))]      # 近年個案較多，比較像真實收案

    made = 0
    for i in range(1, args.n + 1):
        case = make_case(i, random.choices(years, weights=weights)[0])
        try:
            db.save_case(case, "demo_data")
            made += 1
        except ValueError:
            pass                                       # 編號碰撞就跳過
    print("已產生 %d 筆示範個案（編號 %s…）。" % (made, PREFIX))
    print("到「統計儀表板」就能看到圖表。清除請執行："
          "python3 tools/demo_data.py --clear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
