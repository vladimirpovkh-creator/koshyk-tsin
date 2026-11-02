#!/usr/bin/env python3
"""Regression for factual, dated and free Silpo official Telegram announcements."""
import datetime as dt
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from silpo_public_announcements import extract_posts, TZ
NOW=dt.datetime(2026,11,2,8,30,tzinfo=TZ)
posts=[
 {"url":"https://t.me/silposilpo/1001","postedAt":"2026-11-01T10:00:00+02:00",
  "text":"Тільки з 1 до 8 листопада:\n☕ Кава зернова тестова, 1 кг зі знижкою 40% — за 199,00 грн.\n🐟 Риба охолоджена тестова, 100 г зі знижкою 18% – 59,90 грн"},
 {"url":"https://t.me/silposilpo/1002","postedAt":"2026-10-30T08:00:00+02:00",
  "text":"З 30.10 по 01.11\nКава тестова, 500 г зі знижкою 50% — 100 грн"},
 {"url":"https://t.me/silposilpo/1003","postedAt":"2026-11-02T06:00:00+02:00",
  "text":"Тільки сьогодні\nМолоко тестове 900г зі знижкою 21% — 49,90 грн при купівлі від 3 шт"},
 {"url":"https://t.me/not-silpo/111","postedAt":"2026-11-02T06:00:00+02:00",
  "text":"Тільки сьогодні\nМолоко тестове 900г зі знижкою 21% — 49,90 грн"},
 {"url":"https://t.me/silposilpo/1004","postedAt":"2026-11-02T06:00:00+02:00",
  "text":"Тільки сьогодні\nЗнижки до 40% на всі товари для дому"},
]
a=extract_posts(posts,NOW)
assert len(a)==2,a
assert {x["price"] for x in a}=={199.0,59.9},a
assert all(x["sourceType"]=="official-announcement" and x["validTo"]=="2026-11-08" for x in a)
assert all("oldPrice" not in x for x in a)
print("PASS Silpo: only explicit dated official price posts; no inferred old prices")
