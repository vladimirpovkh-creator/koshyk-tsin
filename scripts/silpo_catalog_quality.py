#!/usr/bin/env python3
"""Validate Silpo's store-scoped price catalog before it is published.

No remote calls. These are consistency checks, not a guarantee that a public
promotion is available to every shopper without a loyalty condition.
"""
import datetime as dt
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from price_units import unit_price
from silpo_app_catalog import LOCATION

def audit(rows, day=None):
    today=day or dt.datetime.now(ZoneInfo("Europe/Kyiv")).date()
    errors=[]
    seen=set()
    comparable=0
    for i,item in enumerate(rows):
        if not isinstance(item,dict):
            errors.append(f"row {i}: not an object");continue
        rid=item.get("id")
        if not isinstance(rid,str) or not rid.startswith("silpo-") or rid in seen:
            errors.append(f"row {i}: duplicate or invalid id")
        seen.add(rid)
        price,old=item.get("price"),item.get("oldPrice")
        if (isinstance(price,bool) or isinstance(old,bool)
                or not isinstance(price,(int,float))
                or not isinstance(old,(int,float))
                or not 0<price<old<=100000):
            errors.append(f"row {i}: inconsistent discount")
        if (item.get("date")!=today.isoformat()
                or item.get("locationKey")!="sofia"
                or item.get("location")!=LOCATION
                or item.get("sourceType")!="live-promo-app"
                or item.get("priceVerified") is not True
                or item.get("conditionsVerified") is not False):
            errors.append(f"row {i}: stale, unverified or wrong store")
        url=item.get("url")
        if (not isinstance(url,str) or
                urlparse(url).scheme!="https" or
                urlparse(url).netloc!="silpo.ua" or
                not urlparse(url).path.startswith("/product/")):
            errors.append(f"row {i}: invalid product link")
        if "validTo" in item:
            errors.append(f"row {i}: unverified expiry date")
        if isinstance(price,(int,float)) and not isinstance(price,bool):
            expected=unit_price(item.get("pack"),price)
        else:expected=None
        got=("unitPrice" in item or "unitPriceUnit" in item)
        if expected is None:
            if got:errors.append(f"row {i}: unsupported price-unit conversion")
        else:
            if (item.get("unitPriceUnit")!=expected["unitPriceUnit"] or
                    not isinstance(item.get("unitPrice"),(int,float)) or
                    abs(item["unitPrice"]-expected["unitPrice"])>0.011):
                errors.append(f"row {i}: incorrect price-unit conversion")
            comparable+=1
    return {"count":len(rows),"uniqueIds":len(seen),
            "comparableUnits":comparable,"errors":errors[:12]}
