#!/usr/bin/env python3
"""Offline tests for bounded current Silpo store price collection."""
import datetime as dt
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from silpo_app_catalog import BRANCH_ID,SEARCH_TERMS,normalize_item,collect_public_catalog

for term in ("пиво","вино","ігристе","горілка","віскі","коньяк","ром","джин","сидр"):
 assert term in SEARCH_TERMS, f"missing Silpo alcohol search group: {term}"

DAY=dt.date(2026,11,2)
valid={
 "branchId":BRANCH_ID,"title":"Молоко ультрапастеризоване «Премія» 900 г",
 "slug":"moloko-premiia-ultra-100001","displayPrice":37.99,
 "displayOldPrice":53.99,"stock":4,"displayRatio":"1 шт",
}
record=normalize_item(valid,DAY)
assert record and record["price"]==37.99 and record["oldPrice"]==53.99,record
assert record["locationKey"]=="sofia"
assert record["url"]=="https://silpo.ua/product/moloko-premiia-ultra-100001"
assert record["sourceType"]=="live-promo-app"
assert record["conditionsVerified"] is False
assert record["pack"]=="1 шт"
assert record["unitPriceUnit"]=="шт" and record["unitPrice"]==37.99
assert normalize_item({**valid,"displayRatio":"100г","displayPrice":3.99,"displayOldPrice":5},DAY)["unitPrice"]==39.9
assert normalize_item({**valid,"displayRatio":"0,2л","displayPrice":19.99,"displayOldPrice":29},DAY)["unitPriceUnit"]=="л"
assert normalize_item({**valid,"displayRatio":"за 100 г"},DAY)["pack"]=="за 100 г"
assert "pack" not in normalize_item({**valid,"displayRatio":"1.0"},DAY)
assert "pack" not in normalize_item({**valid,"displayRatio":None},DAY)
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
 result=collect_public_catalog(max_terms=1,page_size=20)
 assert mocked.call_count==1 and len(result)==1
 assert result[0]["name"]==valid["title"]
for mp,sz in ((0,20),(len(SEARCH_TERMS)+1,20),(1,31),(1,0)):
 try:collect_public_catalog(max_terms=mp,page_size=sz)
 except ValueError:pass
 else:raise AssertionError("Unbounded request accepted")

# Full first search page with a total above the page size must trigger offset pagination.
second={**valid,"title":"Сметана 20% 350 г","slug":"smetana-test-200002",
        "displayPrice":39.99,"displayOldPrice":50.99}
stats={}
with patch("silpo_app_catalog._read_page",side_effect=[
 {"items":[valid,{**valid,"displayOldPrice":None}],"total":4},
 {"items":[second,{**valid,"slug":"moloko-non-promo-200001",
                   "displayOldPrice":None}],"total":4}
]) as mocked,patch("silpo_app_catalog.time.sleep"):
 result=collect_public_catalog(max_terms=1,page_size=2,max_pages_per_term=2,stats=stats)
 assert mocked.call_count==2,mocked.call_args_list
 assert mocked.call_args_list[1].args[2]==2,mocked.call_args_list
 assert len(result)==2,result
 assert stats["paginatedTerms"]==1,stats
 assert stats["uniqueProducts"]==3 or stats["uniqueProducts"]==4,stats
 assert stats["requests"]==2,stats
 assert stats["offersWithPack"]==2,stats
 assert stats["ratioSamples"],stats

# If the remote endpoint ignores offset, repeated page must never inflate offers.
repeat_stats={}
with patch("silpo_app_catalog._read_page",side_effect=[
 {"items":[valid,second],"total":10},
 {"items":[valid,second],"total":10},
]) as mocked,patch("silpo_app_catalog.time.sleep"):
 result=collect_public_catalog(max_terms=1,page_size=2,max_pages_per_term=2,stats=repeat_stats)
 assert len(result)==2 and mocked.call_count==2
 assert repeat_stats["truncatedTerms"]>=1,repeat_stats

# No request may continue beyond a hard cap or collect a different branch.
try:
 collect_public_catalog(max_terms=1,page_size=2,max_pages_per_term=4)
except ValueError:pass
else:raise AssertionError("Unbounded pagination allowed")

print("PASS: Silpo local store, valid old/new prices, safe URLs, daily freshness and bounded pages")

