#!/usr/bin/env python3
"""Bounded anonymous promotion collector for one Sofiivska Borshchahivka Silpo.

Reads product listings through Silpo's publicly responding shopping-app catalog.
No login, cookies, private APIs, Cloudflare bypass, or bulk server crawling.
Only verified regular old/new discounts from this exact store are published.
"""
import datetime as dt
import hashlib
import json
import math
import re
import time
from urllib import error,parse,request
from zoneinfo import ZoneInfo

BRANCH_ID="1edb734d-0398-6a04-90b8-198a97b604e9"
LOCATION="Софіївська Борщагівка, вул. Київська, 36"
BASE="https://sf-ecom-api.silpo.ua"
ROOT=f"{BASE}/v1/uk/branches/{BRANCH_ID}/products"
SLUG=re.compile(r"^[a-z0-9][a-z0-9-]{4,180}$")
KYIV=ZoneInfo("Europe/Kyiv")

def _number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float)):
        return None
    if not math.isfinite(x) or not 0.1<=x<=100000:
        return None
    return float(x)

def normalize_item(item, day=None):
    if not isinstance(item,dict):return None
    if item.get("branchId")!=BRANCH_ID:return None
    name=item.get("title")
    slug=item.get("slug")
    if not isinstance(name,str) or not 7<=len(name.strip())<=190:return None
    if not isinstance(slug,str) or not SLUG.fullmatch(slug):return None
    price=_number(item.get("displayPrice"))
    old=_number(item.get("displayOldPrice"))
    if price is None or old is None or not old>price:return None
    pct=(old-price)/old*100
    if not 0.5<=pct<99.9:return None
    stock=item.get("stock")
    if isinstance(stock,(int,float)) and stock<=0:return None
    # Special quantity-price bundles must not masquerade as unconditional
    # discounts. Only the API's explicit old/final display price is accepted.
    when=day or dt.datetime.now(KYIV).date()
    url="https://silpo.ua/product/"+slug
    key="silpo-"+hashlib.sha256((BRANCH_ID+"|"+slug).encode()).hexdigest()[:18]
    return {
        "id":key,"name":name.strip(),"store":"silpo",
        "price":round(price,2),"oldPrice":round(old,2),
        "category":"Акційні товари","date":when.isoformat(),"url":url,
        "locationKey":"sofia","location":LOCATION,
        "sourceType":"live-promo-app","sourceLabel":"Сільпо — застосунок, вул. Київська, 36",
        "priceVerified":True,
    }

def _read_page(offset,limit):
    query=parse.urlencode({"limit":limit,"offset":offset,"inStock":"true"})
    url=ROOT+"?"+query
    req=request.Request(url,headers={
        "Accept":"application/json",
        "User-Agent":"KoshykTsin-PriceCheck/1.0",
    })
    try:
        with request.urlopen(req,timeout=14) as resp:
            if resp.status!=200:raise RuntimeError("Silpo returned non-success status")
            if "json" not in resp.headers.get("Content-Type","").lower():
                raise RuntimeError("Silpo catalog did not return JSON")
            body=resp.read(1_200_001)
            if len(body)>1_200_000:raise RuntimeError("Silpo response exceeded safety limit")
            payload=json.loads(body)
    except error.HTTPError as exc:
        # Do not rotate identities, attempt authentication or retry 401/403/429.
        raise RuntimeError("Silpo catalog HTTP "+str(exc.code)) from exc
    except error.URLError as exc:
        raise RuntimeError("Silpo catalog network unavailable") from exc
    if not isinstance(payload,dict) or not isinstance(payload.get("items"),list):
        raise RuntimeError("Silpo catalog schema unexpectedly changed")
    if len(payload["items"])>limit:
        raise RuntimeError("Silpo returned oversized page")
    return payload

def collect_public_catalog(max_pages=8,page_size=40):
    if not 1<=max_pages<=12 or not 1<=page_size<=50:
        raise ValueError("Unbounded Silpo catalog request refused")
    gathered={}
    checked=0
    day=dt.datetime.now(KYIV).date()
    for page in range(max_pages):
        data=_read_page(page*page_size,page_size)
        items=data["items"]
        checked+=len(items)
        for item in items:
            row=normalize_item(item,day=day)
            if row:gathered[row["id"]]=row
        print("Silpo app page",page+1,"read",len(items),"verified discounts",len(gathered),flush=True)
        if len(items)<page_size:break
        if page+1<max_pages:time.sleep(0.3)
    if not checked:
        raise RuntimeError("Silpo app returned zero products for selected store")
    return list(gathered.values())
