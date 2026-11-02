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
    row={
        "id":key,"name":name.strip(),"store":"silpo",
        "price":round(price,2),"oldPrice":round(old,2),
        "category":"Акційні товари","date":when.isoformat(),"url":url,
        "locationKey":"sofia","location":LOCATION,
        "sourceType":"live-promo-app","sourceLabel":"Сільпо — застосунок, вул. Київська, 36",
        "priceVerified":True,
    }
    # Preserve explicit quantity/unit from the retailer; never infer from price.
    # Numeric ratios alone are insufficient to identify kg versus pieces.
    label=item.get("displayRatio")
    if isinstance(label,str):
        label=" ".join(label.split())
        if (2<=len(label)<=40 and re.search(
                r"(?i)(?:^|[^a-zа-яіїєґ])(?:кг|г|мл|л|шт)(?=$|[^a-zа-яіїєґ])",
                label)):
            row["pack"]=label
    return row

SEARCH_TERMS=(
    "молоко","сир","йогурт","яйця","хліб","масло","кава","чай",
    "шоколад","печиво","крупа","макарони","яблуко","банан",
    "курка","риба","ковбаса","соус","сік","вода",
    "олія","порошок","підгузки","корм",
    "кефір","сметана","сосиски","шинка","морозиво","цукерки",
    "картопля","морква","помідор","огірок","майонез","кетчуп",
)

def _read_page(term,limit,offset=0):
    # Public app endpoint requires a search term; a bare listing returns 400.
    query=parse.urlencode({"search":term,"limit":limit,"offset":offset,"inStock":"true"})
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
        # Do not rotate identities or try to bypass access restrictions.
        raise RuntimeError("Silpo catalog HTTP "+str(exc.code)+" for term "+term) from exc
    except error.URLError as exc:
        raise RuntimeError("Silpo catalog network unavailable") from exc
    if not isinstance(payload,dict) or not isinstance(payload.get("items"),list):
        raise RuntimeError("Silpo catalog schema unexpectedly changed")
    if len(payload["items"])>limit:
        raise RuntimeError("Silpo returned oversized page")
    return payload


def collect_public_catalog(max_terms=36,page_size=20,max_pages_per_term=2,stats=None):
    """Read small paginated search windows; stop on repeats and honor access limits.

    Covering all products is not guaranteed: the endpoint requires a search or
    category and returns a ranked slice. Record truncation instead of claiming
    a complete store catalog.
    """
    if (not 1<=max_terms<=len(SEARCH_TERMS)
            or not 1<=page_size<=30 or not 1<=max_pages_per_term<=3):
        raise ValueError("Unbounded Silpo catalog request refused")
    max_requests=90
    gathered={}
    checked=0
    requests=0
    invalid_queries=0
    unique_products=set()
    ratio_examples={}
    paginated_terms=0
    truncated_terms=0
    terms_with_results=0
    day=dt.datetime.now(KYIV).date()

    def get_page(term,limit,offset):
        nonlocal requests
        if requests>=max_requests:
            raise RuntimeError("Silpo catalog reached hard request budget")
        requests+=1
        return _read_page(term,limit,offset)

    for index,term in enumerate(SEARCH_TERMS[:max_terms]):
        try:
            data=get_page(term,page_size,0)
            limit=page_size
        except RuntimeError as exc:
            if "HTTP 400" not in str(exc):raise
            # A single smaller request can diagnose a rejected page size.
            try:
                data=get_page(term,2,0)
                limit=2
            except RuntimeError as smaller_exc:
                if "HTTP 400" not in str(smaller_exc):raise
                invalid_queries+=1
                print("Silpo app invalid query",term,flush=True)
                if invalid_queries>=3:
                    raise RuntimeError("Silpo app rejected three anonymous search terms") from smaller_exc
                continue

        items=data["items"]
        total=data.get("total")
        seen_in_term=set()
        terms_with_results+=bool(items)
        for page in range(max_pages_per_term):
            if page:
                if requests>=max_requests:
                    truncated_terms+=1
                    break
                try:
                    data=get_page(term,limit,page*limit)
                except RuntimeError as exc:
                    if "HTTP 400" not in str(exc):raise
                    truncated_terms+=1
                    print("Silpo app pagination unsupported for",term,flush=True)
                    break
                items=data["items"]
            if not items:break
            current_keys=set()
            for item in items:
                if isinstance(item,dict):
                    raw_ratio=item.get("displayRatio")
                    ratio_repr=str(raw_ratio)[:40] if raw_ratio is not None else "(missing)"
                    ratio_examples[ratio_repr]=ratio_examples.get(ratio_repr,0)+1
                    product_id=item.get("id") or item.get("slug")
                    if isinstance(product_id,str):current_keys.add(product_id)
                row=normalize_item(item,day=day)
                if row:gathered[row["id"]]=row
            # If pagination ignores offset, don't rescan the same page.
            if current_keys and current_keys.issubset(seen_in_term):
                truncated_terms+=1
                break
            seen_in_term.update(current_keys)
            unique_products.update(current_keys)
            checked+=len(items)
            if page:paginated_terms+=1
            if len(items)<limit:break
            # Respect explicit total (if available) and our per-term page cap.
            if isinstance(total,int) and total>=0 and (page+1)*limit>=total:break
            if page+1==max_pages_per_term:
                truncated_terms+=1
                break
            time.sleep(0.3)
        print("Silpo app search",index+1,term,"unique products",len(unique_products),
              "verified discounts",len(gathered),flush=True)
        if index+1<max_terms:time.sleep(0.3)

    if stats is not None:
        stats.update({
            "termsChecked":max_terms,"termsWithResults":terms_with_results,
            "requests":requests,"productRowsRead":checked,
            "uniqueProducts":len(unique_products),
            "verifiedDiscounts":len(gathered),
            "offersWithPack":sum(bool(x.get("pack")) for x in gathered.values()),
            "ratioSamples":sorted(ratio_examples.items(),key=lambda p:-p[1])[:8],
            "paginatedTerms":paginated_terms,
            "truncatedTerms":truncated_terms,
            "rejectedSearchTerms":invalid_queries,
            "coverage":"bounded search windows, NOT full catalog",
        })
    if not checked:
        raise RuntimeError("Silpo app returned zero search results for selected store")
    return list(gathered.values())
