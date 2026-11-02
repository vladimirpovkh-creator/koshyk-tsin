#!/usr/bin/env python3
"""No-network regression: licensed Silpo feed is opt-in and never invents prices."""
import datetime as dt
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from silpo_partner_feed import verified_offers
today=dt.date(2026,11,2)
base={"name":"Молоко Премія 900 г","price":37.99,"oldPrice":53.99,"validTo":"2026-11-03","url":"https://silpo.ua/product/moloko-premiia"}
payload={"offers":[
 base,
 {**base,"name":"Печиво ванільне 200 г","price":19.99,"oldPrice":29.99,"url":"https://silpo.ua/product/pechyvo"},
 {**base,"name":"Прострочена пропозиція","validTo":"2026-11-01","url":"https://silpo.ua/product/expired"},
 {**base,"name":"Помилковий відсоток","discount":99,"url":"https://silpo.ua/product/badge"},
 {**base,"name":"Чужий магазин","url":"https://example.org/product/not-silpo"},
 {**base,"name":"Неправильна ціна","price":0.01,"url":"https://silpo.ua/product/wrong"},
 {**base,"name":"Немає старої ціни","oldPrice":37.99,"url":"https://silpo.ua/product/no-discount"},
 base]}
rows=verified_offers(payload,today)
assert len(rows)==2,rows
assert all(r["store"]=="silpo" and r["priceVerified"] is True for r in rows)
assert all(r["validTo"]>="2026-11-02" and r["oldPrice"]>r["price"] for r in rows)
assert all(r["sourceType"]=="partner-promo" for r in rows)
print("PASS: two verified Silpo offers; duplicates, expired, external and bad prices rejected")
