#!/usr/bin/env python3
"""ATB offer validation: never use prices from adjacent cards."""
import datetime as dt
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from atb_economy import normalize_atb
NOW=dt.date(2026,11,2)
base={"name":"Корм 300г Friskies сухий Курка з овочами",
 "url":"https://www.atbmarket.com/product/korm-friskies-kurka",
 "price":39.4,"oldPrice":58.9,"discount":33,
 "expires":"до 03.11","pack":"шт"}
item=normalize_atb(base,NOW)
assert item is not None,item
assert item["price"]==39.4 and item["oldPrice"]==58.9
assert item["validTo"]=="2026-11-03"
assert item["pack"]=="1 шт" and item["priceVerified"] is True
assert item["conditionsVerified"] is False
assert normalize_atb({**base,"pack":"кг"},NOW)["pack"]=="1 кг"
invalid=[
 {"price":39.4,"oldPrice":39.4},
 {"price":70,"oldPrice":58.9},
 {"discount":20},
 {"expires":"до 01.11"},
 {"expires":"до 31.02"},
 {"expires":""},
 {"url":"https://evil.example/product/abc"},
 {"url":"http://www.atbmarket.com/product/abc"},
 {"url":"https://www.atbmarket.com/catalog/economy"},
 {"name":"Пиво 0,5л lager"},
 {"pack":"100г"},
 {"price":float("nan")},
]
for change in invalid:
    assert normalize_atb({**base,**change},NOW) is None,change
print("PASS: ATB strict expiry, discount, unit, source and product-card checks")
