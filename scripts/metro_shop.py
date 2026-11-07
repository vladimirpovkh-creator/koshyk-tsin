#!/usr/bin/env python3
"""Verified, explicitly discounted public METRO Shop offers for Kyiv Pozniaky.

Only rendered public HTML text, without login, hidden APIs or bypasses.
Never treat VAT-exclusive or quantity-dependent prices as retail discounts.
"""
import asyncio
import datetime as dt
import hashlib
import re
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

SOURCE = "https://shop.metro.ua/"
STORE_TEXT = "Київ, Позняки. ТЦ №10"
VALUE = r"([0-9][0-9\s\u00a0\u202f]{0,11}[.,][0-9]{2})"
PRICE_PAIR = re.compile(r"Ціна з ПДВ\s+" + VALUE + r"\s*грн\s*" + VALUE + r"\s*грн", re.I)
PROMO = re.compile(r"Акція\s*Діє\s*протягом\s*\d+\s*днів\b", re.I)
AVAILABLE = re.compile(r"Доступний\s*\(за умови наявності в Київ, Позняки\. ТЦ №10\)", re.I)
NOT_AVAILABLE = re.compile(r"Наразі недоступно", re.I)
WHOLESALE = re.compile(r"від\s*\d+\s*\+|від\s*\d+\s*(?:шт\b|од\b)",re.I)


def _money(value):
    return float(re.sub(r"[\s\u00a0\u202f]", "", value).replace(",", "."))


def parse_shop_promotions(text, checked_date=None):
    """Only explicit promo cards with unambiguous displayed VAT-inclusive prices."""
    checked = checked_date or dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()
    if STORE_TEXT not in text:
        return []
    offers = {}
    rejected_ids = set()
    for section in text.split("Купуйте в ТЦ"):
        markers = list(PROMO.finditer(section))
        if not markers:
            continue
        block = section[markers[-1].end():].strip()
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        title = lines[0]
        if (not 12 <= len(title) <= 190 or "грн" in title.casefold()
                or "Тип пакування:" not in block or "Ціна без ПДВ" not in block):
            continue
        if NOT_AVAILABLE.search(block) or not AVAILABLE.search(block) or WHOLESALE.search(block):
            continue
        matches = list(PRICE_PAIR.finditer(block))
        if len(matches) != 1:
            continue
        new, old = map(_money, matches[0].groups())
        if not (0 < new < old < 100000) or (1 - new / old) * 100 < 1:
            continue
        # The old-price line must precede the expressly VAT-exclusive line.
        if "Ціна без ПДВ" not in block[matches[0].end():]:
            continue
        key = "metro-" + hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:18]
        item = {
            "id": key, "name": title, "store": "metro",
            "price": new, "oldPrice": old,
            "discount": round((1 - new / old) * 100),
            "date": checked, "url": SOURCE,
            "locationKey": "kyiv",
            "location": "METRO Київ, Позняки. ТЦ №10; наявність залежить від ТЦ",
            "sourceType": "metro-official-shop-public-promo",
            "sourceLabel": "METRO Shop — акційна ціна з ПДВ (Київ, Позняки)",
            "priceVerified": True, "conditionsVerified": False,
            "availabilityStatus": "listed",
            "catalogCoverage": "verified-individual-price-only",
        }
        if key in rejected_ids:
            continue
        existing = offers.get(key)
        if existing and (existing["price"], existing["oldPrice"]) != (new, old):
            offers.pop(key)
            rejected_ids.add(key)
        else:
            offers[key] = item
    return list(offers.values())


def catalog_url(url):
    """Allow only public METRO Shop categories, product lists and pagination."""
    if not isinstance(url,str) or len(url)>1500:
        return None
    u=urlparse(url)
    if u.scheme!="https" or u.hostname!="shop.metro.ua" or u.username or u.password:
        return None
    if not (u.path.startswith("/shop/category/") or
            u.path.startswith("/shop/storelist/")):
        return None
    # Query params are not part of a signed endpoint; only explicit pagination.
    query=parse_qsl(u.query,keep_blank_values=True)
    if query and not all(k in ("page","p") and v.isdecimal() and 1<=int(v)<=100 for k,v in query):
        return None
    return urlunparse(("https","shop.metro.ua",u.path,"",urlencode(query),""))


async def _rendered(page, url, home=False):
    """Read a settled public listing, not just the pre-hydration shell."""
    response=await page.goto(url,wait_until="domcontentloaded",timeout=26000)
    if not response or response.status!=200 or urlparse(page.url).hostname!="shop.metro.ua":
        return None,[],response.status if response else None
    # The homepage and category pages are client-rendered; wait for store
    # selection AND product action cards, rather than sleeping blindly.
    try:
        await page.wait_for_function(
            """() => document.body?.innerText?.includes('Київ, Позняки. ТЦ №10')
                && document.body?.innerText?.includes('Купуйте в ТЦ')""",
            timeout=16000)
    except Exception:
        pass
    await page.wait_for_timeout(1200 if not home else 2000)
    body=(await page.locator("body").inner_text(timeout=12000))[:350000]
    urls=await page.locator('a[href]').evaluate_all(
        """els=>els.map(a=>a.href).filter(h=>
            h.startsWith('https://shop.metro.ua/shop/category/') ||
            h.startsWith('https://shop.metro.ua/shop/storelist/'))""")
    return body,urls,response.status


async def collect_shop_promotions(page, stats=None, max_pages=420):
    """Inspect discoverable official category/list pages and keep only verified promotions.

    A bounded crawl cannot prove the whole retail catalog was enumerated; diagnostics
    disclose caps, missing pages and the exact number of pages inspected.
    """
    info={"source":SOURCE,"fullCatalog":False,
          "coverage":"All publicly linked catalog categories and product lists, bounded traversal"}
    items={}
    conflicting=set()
    discovered=set()
    processed=set()
    failures=[]
    visited=0
    counts={"home":0,"categories":0,"lists":0,"total":0}
    try:
        body,links,status=await _rendered(page,SOURCE,home=True)
        info["httpStatus"]=status
        if body is None or STORE_TEXT not in body:
            info["hasExpectedStore"]=False
            return []
        info["hasExpectedStore"]=True
        def add(rows):
            for item in rows:
                key=item["id"]
                if key in conflicting:continue
                previous=items.get(key)
                if previous and (previous["price"],previous["oldPrice"])!=(
                        item["price"],item["oldPrice"]):
                    items.pop(key)
                    conflicting.add(key)
                elif previous is None:
                    items[key]=item
        add(parse_shop_promotions(body))
        counts["home"]=1
        queue=[]
        for url in links:
            clean=catalog_url(url)
            if clean and clean not in discovered:
                discovered.add(clean)
                queue.append(clean)
        # A small number of isolated browser tabs makes network load predictable.
        # No login, private APIs, pagination guessing or anti-bot bypasses.
        while queue and visited<max_pages:
            batch=queue[:3]
            queue=queue[3:]
            async def visit(url):
                # collect_store.py uses browser.new_page(), whose automatically owned
                # context rejects context.new_page(). Create an independent
                # public browser tab with its own context instead.
                tab=await page.context.browser.new_page(
                    locale="uk-UA",viewport={"width":1350,"height":900})
                try:
                    content,extra,code=await _rendered(tab,url)
                    return (url,content,extra,code,None)
                except Exception as exc:
                    return (url,None,[],None,type(exc).__name__)
                finally:
                    await tab.close()
            results=await asyncio.gather(*(visit(u) for u in batch))
            for url,content,more,code,error in results:
                processed.add(url)
                visited+=1
                if not content or STORE_TEXT not in content:
                    failures.append({"url":url,"status":code,"error":error or "store or public cards missing"})
                    continue
                if "/shop/category/" in url:counts["categories"]+=1
                else:counts["lists"]+=1
                add(parse_shop_promotions(content))
                for candidate in more:
                    clean=catalog_url(candidate)
                    if clean and clean not in discovered:
                        discovered.add(clean)
                        queue.append(clean)
        info.update({"pagesVisited":visited+1,"categoryPages":counts["categories"],
                     "listPages":counts["lists"],"discoveredPages":len(discovered),
                     "unvisitedPages":len(queue),"failedPages":len(failures),
                     "failedPageSamples":failures[:8],
                     "verifiedOffers":len(items),"conflictingOfferIds":len(conflicting),
                     "listingPagesComplete":not queue and not failures,
                     "fullCatalog":False})
        return list(items.values())
    except Exception as exc:
        info["error"]=type(exc).__name__+": "+str(exc)[:180]
        return list(items.values())
    finally:
        if stats is not None:
            stats.update(info)
