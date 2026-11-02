#!/usr/bin/env python3
"""Offline tests for bounded current Silpo store price collection."""
import datetime as dt
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from silpo_app_catalog import BRANCH_ID,normalize_item,collect_public_catalog

DAY=dt.date(2026,11,2)
valid={
 "branchId":BRANCH_ID,"title":"Молоко ультрапастеризоване «Премія» 900 г",
 "slug":"moloko-premiia-ultra-100001","displayPrice":37.99,
 "displayOldPrice":53.99,"stock":4,
}
record=normalize_item(valid,DAY)
assert record and record["price"]==37.99 and record["oldPrice"]==53.99,record
assert record["locationKey"]=="sofia"
assert record["url"]=="https://silpo.ua/product/moloko-premiia-ultra-100001"
assert record["sourceType"]=="live-promo-app"
assert "validTo" not in record  # Do not fabricate a promo end date.
bad=[
 {**valid,"branchId":"wrong-store"},
 {**valid,"displayOldPrice":None},
 {**valid,"displayOldPrice":35},
 {**valid,"stock":0},
 {**valid,"displayPrice":float("nan")},
 {**valid,"slug":"https://other.example/a"},
 {**valid,"title":"x"},
 {**valid,"displayOldPrice":True},
]
assert all(normalize_item(x,DAY) is None for x in bad)
with patch("silpo_app_catalog._read_page",side_effect=[
 {"items":[valid,{**valid,"displayOldPrice":None}]},
]) as mocked:
 result=collect_public_catalog(max_pages=1,page_size=40)
 assert mocked.call_count==1 and len(result)==1
 assert result[0]["name"]==valid["title"]
for mp,sz in ((0,40),(13,40),(1,100),(1,0)):
 try:collect_public_catalog(max_pages=mp,page_size=sz)
 except ValueError:pass
 else:raise AssertionError("Unbounded request accepted")
print("PASS: Silpo local store, valid old/new prices, safe URLs, daily freshness and bounded pages")
