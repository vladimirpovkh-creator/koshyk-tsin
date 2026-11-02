#!/usr/bin/env python3
"""Bounded connectivity diagnostics for ATB's public 'Economy' catalogue.

Read-only, no authentication, no cookies, no proxy or anti-bot workarounds.
Never treat a Cloudflare challenge page as product data.
"""
import json
import re
from urllib import error,request

URLS=(
    "https://www.atbmarket.com/catalog/economy",
    "https://www.atbmarket.com/promo/economy",
)

def inspect_html(html):
    title_match=re.search(r"<title[^>]*>(.*?)</title>",html,re.I|re.S)
    title=re.sub(r"\s+"," ",title_match.group(1)).strip()[:120] if title_match else ""
    lower=html.lower()
    product_links=set(re.findall(r'href\s*=\s*["\']([^"\']*/product/[^"\']+)["\']',html,re.I))
    # Production HTML can mention Cloudflare in analytics scripts without
    # actually serving an interstitial. Judge the page title and real cards.
    cf=(("трохи зачекайте" in title.lower() or "just a moment" in title.lower())
        or ("триває перевірка безпеки" in lower and not product_links))
    return {"title":title,"challenge":cf,"htmlLength":len(html),
            "productLinkCount":len(product_links),
            "hasEconomyHeading":("Економія" in html or "экономия" in lower),
            "priceMarkers":len(re.findall(r"грн|₴",html,re.I))}

def probe_site(url):
    if url not in URLS:raise ValueError("Unapproved target URL")
    result={"source":url,"reachable":False}
    req=request.Request(url,headers={
        "Accept":"text/html",
        "User-Agent":"KoshykTsin-ATB-PersonalPriceCheck/1.0",
    })
    try:
        with request.urlopen(req,timeout=15) as resp:
            result["httpStatus"]=resp.status
            content_type=resp.headers.get("Content-Type","")
            result["contentType"]=content_type[:60]
            if "html" not in content_type.lower():return result
            raw=resp.read(800001)
            if len(raw)>800000:
                result["error"]="Response exceeds limited diagnostic size"
                return result
            details=inspect_html(raw.decode("utf-8","replace"))
            result.update(details)
            result["reachable"]=not details["challenge"]
    except error.HTTPError as exc:
        result["httpStatus"]=exc.code
        result["error"]="HTTP access denied/unavailable"
    except error.URLError as exc:
        result["error"]="Network unavailable: "+type(exc.reason).__name__
    except (OSError,TimeoutError):
        result["error"]="Network timeout/unavailable"
    return result

def probe():
    return {"mode":"anonymous-bounded-check","results":[probe_site(u) for u in URLS]}

if __name__=="__main__":
    print(json.dumps(probe(),ensure_ascii=False))
