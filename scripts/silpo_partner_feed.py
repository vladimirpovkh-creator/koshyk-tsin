#!/usr/bin/env python3
"""Strict adapter for a licensed Silpo promotions JSON feed.

Enable ONLY after the feed provider has granted permission to republish prices.
A third-party catalog webpage must not be scraped as a substitute for the feed.
Expected JSON: {"offers":[{"name":"...","price":39.99,"oldPrice":59.99,
"validTo":"2026-11-12","url":"https://silpo.ua/product/..."}]}.
"""
import datetime as dt
import hashlib
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

KYIV=ZoneInfo("Europe/Kyiv")
SOURCE="Сільпо — партнерський каталог акцій"

def verified_offers(payload, today=None):
    day=today or dt.datetime.now(KYIV).date()
    rows=payload.get("offers") if isinstance(payload,dict) else payload
    if not isinstance(rows,list):
        raise ValueError("Partner feed must contain an offers array")
    out={}
    for row in rows:
        if not isinstance(row,dict): continue
        name=row.get("name")
        url=row.get("url")
        price=row.get("price")
        old=row.get("oldPrice")
        end=row.get("validTo")
        if not isinstance(name,str) or not 6<=len(name.strip())<=190:continue
        if not isinstance(url,str):continue
        parsed=urlparse(url)
        if parsed.scheme!="https" or parsed.hostname not in ("silpo.ua","www.silpo.ua") or not parsed.path.startswith("/"):continue
        if not isinstance(price,(int,float)) or isinstance(price,bool):continue
        if not isinstance(old,(int,float)) or isinstance(old,bool):continue
        if not (0.1<=price<old<=100000):continue
        if not isinstance(end,str):continue
        try: expires=dt.date.fromisoformat(end)
        except ValueError:continue
        if expires<day:continue
        discount=100*(old-price)/old
        if discount<1 or discount>=100:continue
        declared=row.get("discount")
        if declared is not None and (not isinstance(declared,(int,float)) or abs(discount-declared)>2):continue
        key="silpo-"+hashlib.sha256(("silpo|"+url+"|"+name.strip()).encode()).hexdigest()[:18]
        out[key]={"id":key,"name":name.strip(),"store":"silpo",
            "price":round(float(price),2),"oldPrice":round(float(old),2),
            "date":day.isoformat(),"validTo":end,"url":url,
            "category":"Акційні товари","locationKey":"kyiv",
            "location":"Київський регіон; наявність за адресою не перевірена",
            "sourceType":"partner-promo","sourceLabel":SOURCE,
            "priceVerified":True}
    return list(out.values())

def collect_partner_feed():
    url=os.environ.get("SILPO_FEED_URL","").strip()
    if not url or urlparse(url).scheme!="https":
        raise ValueError("SILPO_FEED_URL must be an authorized HTTPS partner feed")
    token=os.environ.get("SILPO_FEED_TOKEN","")
    headers={"Accept":"application/json","User-Agent":"KoshykTsin/1.0"}
    if token:headers["Authorization"]="Bearer "+token
    with urlopen(Request(url,headers=headers),timeout=25) as response:
        if response.status!=200:raise RuntimeError("Partner feed returned HTTP "+str(response.status))
        raw=response.read(4_000_001)
        if len(raw)>4_000_000:raise ValueError("Partner feed exceeds size limit")
    data=json.loads(raw.decode("utf-8"))
    return verified_offers(data)
