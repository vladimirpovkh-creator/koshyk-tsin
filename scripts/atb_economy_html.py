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

def inspect_candidates(html):
    """Diagnose which isolation constraint rejected public product cards."""
    soup=BeautifulSoup(html,"html.parser")
    samples=[]
    seen=set()
    counters={"anchors":0,"namedAnchors":0,"containersWithBadge":0,
              "containersWithDate":0,"containersWithMoney":0,
              "containersWithOneProduct":0}
    for anchor in soup.find_all("a",href=True):
        u=urlparse(urljoin(SOURCE,anchor["href"]))
        if u.hostname!="www.atbmarket.com" or not u.path.startswith("/product/"):continue
        if u.path in seen:continue
        seen.add(u.path)
        counters["anchors"]+=1
        name=anchor.get_text(" ",strip=True)
        if not name and (im:=anchor.find("img",alt=True)):
            name=im.get("alt","")
        if name:counters["namedAnchors"]+=1
        if len(samples)>=4:continue
        candidate=[]
        for node in list(anchor.parents)[:8]:
            if not hasattr(node,"find_all"):continue
            raw=" ".join(node.stripped_strings)
            if not 20<=len(raw)<=950:continue
            links={urlparse(urljoin(SOURCE,x.get("href",""))).path
                   for x in node.find_all("a",href=True)
                   if "/product/" in x.get("href","")}
            is_badge=bool(BADGE.search(raw))
            is_date=bool(DATE.search(raw))
            is_money=bool(MONEY.search(raw))
            counters["containersWithBadge"]+=is_badge
            counters["containersWithDate"]+=is_date
            counters["containersWithMoney"]+=is_money
            counters["containersWithOneProduct"]+=(len(links)==1)
            candidate.append({"tag":node.name,"chars":len(raw),"products":len(links),
                              "badge":is_badge,"date":is_date,"money":is_money,
                              "sample":raw[:220]})
        samples.append({"urlPath":u.path,"name":name[:90],"ancestors":candidate[:5]})
    return {"counts":counters,"examples":samples}

def collect_html(stats=None):
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
    html=raw.decode("utf-8","replace")
    products=extract_html(html)
    if stats is not None:
        stats.update({"htmlLength":len(html),"acceptedOffers":len(products)})
        if not products:stats["rejectionProbe"]=inspect_candidates(html)
    if not products:
        raise RuntimeError("ATB public HTML had no individually verified current Economy cards")
    return products
