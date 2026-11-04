#!/usr/bin/env python3
"""Offline regression tests for source-specific catalog quality checks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_catalog import audit

ROW = {
    "id": "novus-item1", "name": "Молоко тестове 1л", "store": "novus",
    "channel": "online", "availabilityStatus": "unverified", "price": 39.9, "oldPrice": 49.9,
    "date": "2026-11-04", "validTo": "2026-11-12",
    "url": "https://novus.zakaz.ua/uk/products/moloko-testove--123/",
}
second = {**ROW, "id": "novus-item2", "name": "Кефір тестовий 900г",
          "url": "https://novus.zakaz.ua/uk/products/kefir-testovyi--456/"}

ok = audit([ROW, second], "novus")
assert ok["ok"] and ok["count"] == 2 and ok["uniqueIds"] == 2, ok
assert not ok["warnings"], ok

duplicate_id = audit([ROW, {**second, "id": ROW["id"]}], "novus")
assert not duplicate_id["ok"] and "duplicate ID" in str(duplicate_id["errors"])

duplicate_url = audit([ROW, {**second, "url": ROW["url"] + "?ref=promo"}], "novus")
assert not duplicate_url["ok"] and "duplicate product URL" in str(duplicate_url["errors"])

for changes in (
    {"price": 0}, {"price": 60}, {"oldPrice": None},
    {"price": float("nan")}, {"price": True},
    {"url": "https://evil.example/uk/products/milk/"},
    {"url": "http://novus.zakaz.ua/uk/products/milk/"},
    {"store": "metro"}, {"channel": "official"},
    {"availabilityStatus": "in_stock"}, {"inStock": True},
    {"date": "2026-19-89"}, {"validTo": "2026-11-03"},
    {"name": ""}, {"id": ""},
):
    report = audit([{**ROW, **changes}], "novus")
    assert not report["ok"], (changes, report)

extreme = audit([{**ROW, "price": 1.0}], "novus")
assert extreme["ok"] and extreme["extremeDiscountSamples"]
assert audit([ROW], "novus", previous_count=100)["warnings"]
assert not audit({"unexpected": "object"}, "novus")["ok"]

print("PASS: catalog audit validates NOVUS offers and detects bad prices, URLs, dates and duplicate IDs")
