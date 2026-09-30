#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把院內的衛教 Word 檔轉成衛教專區的資料檔。

    python3 tools/docx_to_education.py --file 衛教文章.docx

產生 static/education.js。文章結構（標題／作者／小標／內文）由排版推斷：
標題 = 下一段以「撰文/」開頭的那一段；小標 = 短且不以句號結尾的段落。
"""

import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def paragraphs(path):
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    out = []
    for p in root.iter(NS + "p"):
        text = "".join(t.text or "" for t in p.iter(NS + "t"))
        text = text.replace("﻿", "").strip()
        if text:
            out.append(text)
    return out


# 依標題關鍵字挑圖示，找不到就用預設的書本
ICON_RULES = [
    ("三不一沒有", "\U0001F44B"), ("初見面", "\U0001F44B"),
    ("什麼是", "\U0001F4D6"), ("又稱環境", "\U0001F4D6"),
    ("異與同", "\u2696\uFE0F"), ("結核菌", "\u2696\uFE0F"),
    ("診斷", "\U0001F52C"),
    ("威脅", "\u26A0\uFE0F"), ("全身健康", "\u26A0\uFE0F"),
    ("追蹤策略", "\U0001F4C5"), ("治療時機", "\U0001F4C5"),
    ("鳥型", "\U0001F9A0"),
    ("膿瘍", "\U0001F489"),
    ("非藥物", "\U0001FAC1"), ("輔助治療", "\U0001FAC1"),
    ("吸入性", "\U0001F4A8"),
    ("藥物敏感", "\U0001F9EA"), ("敏感檢驗", "\U0001F9EA"),
    ("Clofazimine", "\U0001F48A"), ("新選擇", "\U0001F48A"),
]


def pick_icon(title):
    for keyword, icon in ICON_RULES:
        if keyword in title:
            return icon
    return "\U0001F4D8"


def make_summary(blocks, limit=52):
    """取第一段內文的前一兩句當卡片摘要。"""
    for block in blocks:
        text = block.get("p")
        if not text or len(text) < 20:
            continue
        # 切到第一個句號，太長再截斷
        first = re.split(r"[。！？]", text)[0]
        if len(first) > limit:
            first = first[:limit].rstrip("，、 ") + "…"
        return first + ("。" if not first.endswith("…") else "")
    return ""


def is_author(text):
    return text.startswith("撰文") or re.match(r"^[一-鿿]{2,4}醫師\s*\(", text)


def is_heading(text):
    """小標：以「一、」開頭，或短句而不以句號結尾（問句型小標很常見）。"""
    if re.match(r"^[一二三四五六七八九十]+[、.]", text):
        return True
    if len(text) > 26:
        return False
    return not text.endswith("。")


def build(paras):
    articles = []
    i = 0
    while i < len(paras):
        # 標題的判準：後面緊接著作者列
        if i + 1 < len(paras) and is_author(paras[i + 1]):
            title = paras[i]
            i += 1
            authors = []
            while i < len(paras) and is_author(paras[i]):
                authors.append(paras[i].replace("撰文/", "").strip())
                i += 1
            blocks = []
            while i < len(paras):
                if i + 1 < len(paras) and is_author(paras[i + 1]):
                    break          # 下一篇開始了
                text = paras[i]
                blocks.append({"h": text} if is_heading(text) else {"p": text})
                i += 1
            articles.append({
                "title": title,
                "authors": authors,
                "icon": pick_icon(title),
                "summary": make_summary(blocks),
                "blocks": blocks,
            })
        else:
            i += 1
    return articles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="衛教文章 .docx")
    ap.add_argument("--out", default=os.path.join(BASE_DIR, "static", "education.js"))
    args = ap.parse_args()

    articles = build(paragraphs(args.file))
    if not articles:
        raise SystemExit("這個檔案裡找不到「標題 + 撰文/作者」的結構")

    body = ("/* 衛教內容，由院內衛教 Word 檔轉出，請勿手動編輯。\n"
            " * 重新產生：python3 tools/docx_to_education.py --file 衛教文章.docx\n"
            " */\n'use strict';\n\nconst EDU_ARTICLES = %s;\n"
            % json.dumps(articles, ensure_ascii=False, indent=2))
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(body)

    print("已產生 %s" % args.out)
    print("共 %d 篇文章：" % len(articles))
    for a in articles:
        heads = sum(1 for b in a["blocks"] if "h" in b)
        print("   %-40s %d 段（含 %d 個小標）"
              % (a["title"][:38], len(a["blocks"]), heads))


if __name__ == "__main__":
    main()
