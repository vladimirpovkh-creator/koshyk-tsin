#!/usr/bin/env python3
"""Fail closed when Silpo records contain stale, mismatched or unsupported data."""
import datetime as dt
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from silpo_catalog_quality import audit
from silpo_app_catalog import normalize_item, BRANCH_ID

day=dt.date(2026,11,2)
item={
    "branchId":BRANCH_ID,"title":"Яблуко Гала відбірне",
    "slug":"iabluko-gala-ved-91888","displayPrice":3.99,
    "displayOldPrice":4.99,"displayRatio":"100г","stock":7
}
assert normalize_item({**item,"specialPrices":[{"price":2.99}]},day) is None
assert normalize_item({**item,"specialPrices":{"loyalty":2.99}},day) is None
assert normalize_item({**item,"specialPrices":[]},day) is not None
row=normalize_item(item,day)
assert row["unitPrice"]==39.9,row
assert row["conditionsVerified"] is False
good=audit([row],day)
assert good["count"]==1 and good["comparableUnits"]==1 and not good["errors"],good

for changes in (
    {"date":"2026-11-01"},
    {"price":5.99},
    {"oldPrice":3.99},
    {"locationKey":"kyiv"},
    {"location":"Other shop"},
    {"conditionsVerified":True},
    {"priceVerified":False},
    {"unitPrice":3.99},
    {"unitPriceUnit":"л"},
    {"url":"https://example.com/product/test"},
    {"validTo":"2026-11-12"},
):
    broken={**row,**changes}
    result=audit([broken],day)
    assert result["errors"],(changes,result)
assert audit([row,row],day)["errors"]
ambiguous=normalize_item({**item,"displayRatio":"за 100 г"},day)
assert ambiguous is not None and "unitPrice" not in ambiguous
assert not audit([ambiguous],day)["errors"]
print("PASS: Silpo QA rejects inconsistent price, location, date, unit and eligibility")
