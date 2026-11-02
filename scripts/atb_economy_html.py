#!/usr/bin/env python3
"""ATB public Economy HTML: bounded personal-use price snapshot, no login.

Parse only normal server-delivered HTML with explicit product links. Stop on
HTTP denial or a Cloudflare interstitial. No stealth, proxies or captcha solve.
"""
import re
from urllib import error,request
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
from atb_economy import SOURCE,normalize_atb

MONEY=re.compile(r"(\d{1,5}[.,]\d{2})\s*грн\s*/\s*(шт|кг)\D{0,38}(\d{1,5}[.,]\d{2})(?!\d)",re.I)
DATE=re.compile(r"\bдо\s*\d{1,2}[.]\d{1,2}\b",re.I)
BADGE=re.compile(r"[-−]\s*(\d{1,2})\s*%")

def extract_html(html,today=None):
    soup=BeautifulSoup(html,"html.parser")
    title=soup.title.get_text(" ",strip=True).lower() if soup.title else ""
    if "трохи зачекайте" in title or "just a moment" in title:
        raise RuntimeError("ATB protection challenge")
    gathered={}
    seen=set()
    for anchor in soup.find_all("a",href=True):
        url=urljoin(SOURCE,anchor["href"])
        parsed=urlparse(url)
        if parsed.hostname!="www.atbmarket.com" or not parsed.path.startswith("/product/"):continue
        if parsed.path in seen:continue
        name=anchor.get_text(" ",strip=True)
        if not name:
            image=anchor.find("img",alt=True)
            name=image.get("alt","") if image else ""
        name=" ".join(name.split())
        if not 7<=len(name)<=190:continue
        node=anchor
        card=None
        for _ in range(7):
            node=node.parent
            if node is None:break
            raw=" ".join(node.stripped_strings)
            if not 30<=len(raw)<=850:continue
            if not (DATE.search(raw) and BADGE.search(raw) and MONEY.search(raw)):continue
            unique={
                urlparse(urljoin(SOURCE,x.get("href",""))).path
                for x in node.find_all("a",href=True)
                if "/product/" in x.get("href","")
            }
            if len(unique)!=1:continue
            card=raw
            break
        if not card:continue
        money=MONEY.search(card)
        badge=BADGE.search(card)
        expiry=DATE.search(card)
        if not money or not badge or not expiry:continue
        row={
            "name":name,"url":url,
            "price":float(money[1].replace(",",".")),
            "oldPrice":float(money[3].replace(",",".")),
            "pack":money[2].lower(),"discount":int(badge[1]),
            "expires":expiry[0],
        }
        accepted=normalize_atb(row,today=today)
        if accepted:
            gathered[accepted["id"]]=accepted
            seen.add(parsed.path)
    return list(gathered.values())

def collect_html():
    req=request.Request(SOURCE,headers={
        "Accept":"text/html","User-Agent":"KoshykTsin-ATB-PersonalPriceCheck/1.0",
    })
    try:
        with request.urlopen(req,timeout=20) as resp:
            if resp.status!=200:raise RuntimeError("ATB public catalog non-success HTTP status")
            if "html" not in resp.headers.get("Content-Type","").lower():
                raise RuntimeError("ATB did not return HTML")
            raw=resp.read(900001)
            if len(raw)>900000:raise RuntimeError("ATB public HTML too large for bounded read")
    except error.HTTPError as exc:
        raise RuntimeError("ATB public catalog access denied HTTP "+str(exc.code)) from exc
    except error.URLError as exc:
        raise RuntimeError("ATB public catalog DNS/network failure") from exc
    products=extract_html(raw.decode("utf-8","replace"))
    if not products:
        raise RuntimeError("ATB public HTML had no individually verified current Economy cards")
    return products
