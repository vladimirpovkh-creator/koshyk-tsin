#!/usr/bin/env python3
"""Verified public promotions from the official METRO Ukraine website.

Source: https://www.metro.ua/propositions (default store: Kyiv Pozniaky).
Never use Zakaz.ua, guessed prices, VAT-exclusive prices or unrelated cards.
"""
import datetime as dt
import hashlib
import re
from urllib.parse import urlparse

SOURCE = "https://www.metro.ua/propositions"
NUMBER = r"(\d[\d\s\u00a0\u202f]{0,9}[.,]\d{2})"
OFFER = re.compile(
    r"(?<!\w)Акція\s+((?:(?!\bАкція\b).){7,190}?)\s+"
    r"(Available|Limited\s+Availability|Not\s+Available)\s+"
    + NUMBER + r"\s*₴\s*" + NUMBER
    + r"\s*₴\s*[-−]\s*(\d{1,2})\s*%",
    re.I | re.S,
)



def catalog_pdf_candidates(discovered, known_pdf, known_until, checked_date):
    """Prefer official discovered links; use pinned fallback only until its known expiry."""
    candidates = []
    for link in discovered:
        if not isinstance(link, str):
            continue
        parsed = urlparse(link)
        if (parsed.scheme != "https" or parsed.hostname != "promotions.metro.ua"
                or "/pdfs/" not in parsed.path or not parsed.path.lower().endswith(".pdf")):
            continue
        clean = parsed._replace(query="", fragment="").geturl()
        if clean not in candidates:
            candidates.append(clean)
        if len(candidates) == 4:
            break
    # A static PDF becomes stale: never treat an expired pinned URL as a new catalog.
    if not candidates and known_until >= checked_date:
        candidates.append(known_pdf)
    return candidates


def merge_metro_offer(items, conflicting_ids, item):
    """Reject a SKU in all source catalogs if independently printed prices disagree."""
    key = item["id"]
    if key in conflicting_ids:
        return
    old = items.get(key)
    if old is not None and old["price"] != item["price"]:
        items.pop(key)
        conflicting_ids.add(key)
    elif old is None:
        items[key] = item


def _amount(value):
    return float(re.sub(r"[\s\u00a0\u202f]", "", value).replace(",", "."))


def parse_promotions(text, checked_date=None):
    """Return only exact, independently verifiable old/new promotional prices."""
    checked_date = checked_date or dt.date.today().isoformat()
    text = re.sub(r"\s+", " ", text or "").strip()
    offers = {}
    for match in OFFER.finditer(text):
        raw_name, availability, original, reduced, pct = match.groups()
        if availability.casefold() == "not available":
            continue
        old, price, discount = _amount(original), _amount(reduced), int(pct)
        if not (0 < price < old <= 100000 and 1 <= discount <= 99):
            continue
        if abs((1 - price / old) * 100 - discount) > 1.5:
            continue
        title = re.sub(r"\s+(?:1\s*(?:шт|кг))$", "", raw_name).strip()
        if not 7 <= len(title) <= 180 or "₴" in title:
            continue
        # Price and source are unambiguous; do not attribute this to Zakaz.
        key = hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:18]
        item = {
            "id": "metro-" + key,
            "name": title,
            "store": "metro",
            "price": price,
            "oldPrice": old,
            "discount": discount,
            "category": "Акційні товари",
            "date": checked_date,
            "url": SOURCE,
            "locationKey": "kyiv",
            "location": "METRO Київ, Позняки; ціни можуть залежати від ТЦ",
            "sourceType": "metro-official-public-promotions",
            "sourceLabel": "METRO.ua — офіційні акційні ціни (Київ, Позняки)",
            "priceVerified": True,
            "availabilityStatus": "limited" if "limited" in availability.lower() else "listed",
        }
        offers[item["id"]] = item
    return list(offers.values())


async def collect_official(page, stats=None):
    """Official METRO listings first, then verified entries from dated PDFs."""
    from metro_catalog_pdf import parse_pdf, valid_period_from_cover
    from zoneinfo import ZoneInfo
    today = dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()
    diagnostics = []
    items = {}
    conflicting_ids = set()
    for url in (SOURCE, "https://www.metro.ua/propositions/topoffers"):
        try:
            r = await page.goto(url,wait_until="domcontentloaded",timeout=18000)
            code = r.status if r else None
            if code in (401,403,429):
                diagnostics.append({"source":url,"status":code,"count":0})
                continue
            body = await page.locator("body").inner_text(timeout=10000)
            parsed = parse_promotions(body,checked_date=today)
            diagnostics.append({"source":url,"status":code,"count":len(parsed)})
            for item in parsed:
                item["url"] = url
                merge_metro_offer(items, conflicting_ids, item)
        except Exception as exc:
            diagnostics.append({"source":url,"error":str(exc)[:100]})

    # A public, hydrated official storefront provides independently printed
    # VAT-inclusive promo price pairs for Kyiv Pozniaky.
    from metro_shop import collect_shop_promotions
    shop_stats = {}
    shop_offers = await collect_shop_promotions(page, stats=shop_stats)
    diagnostics.append(shop_stats)
    for item in shop_offers:
        merge_metro_offer(items, conflicting_ids, item)

    catalogs = [
      ("https://promotions.metro.ua/katalogh-vighidnikh-vikhidnikh/",
       "https://promotions.metro.ua/834/2320121/pdfs/1a7d1e2b-ede4-4724-b6d5-ec2c2b286c77.pdf",
       "2026-11-08"),
      ("https://promotions.metro.ua/katalogh-vighidnikh-propozitsii",
       "https://promotions.metro.ua/834/2320153/pdfs/4c86826c-5dae-4b5a-9fab-a97f239eaee9.pdf",
       "2026-12-01"),
    ]
    for catalog_url, known_pdf, valid_to in catalogs:
        entry = {"catalog":catalog_url}
        try:
            response = await page.goto(catalog_url,wait_until="domcontentloaded",timeout=20000)
            if response and response.status != 200:
                entry["status"] = response.status
                diagnostics.append(entry)
                continue
            await page.wait_for_timeout(1700)
            links = await page.locator('a[href*="/pdfs/"][href*=".pdf"]').evaluate_all(
                "(a)=>a.map(x=>x.href).filter(x=>x.startsWith('https://promotions.metro.ua/'))"
            )
            candidates = catalog_pdf_candidates(links,known_pdf,valid_to,today)
            entry["pdfCandidates"] = len(candidates)
            for link in candidates:
                try:
                    pdf_response = await page.request.get(link,timeout=35000)
                    payload = await pdf_response.body()
                    if not pdf_response.ok or not payload.startswith(b"%PDF-"):
                        entry.setdefault("rejections", []).append(
                            {"httpStatus":pdf_response.status,"pdfValid":False})
                        continue
                    source_kind = "weekend" if "vighidnikh-vikhidnikh" in catalog_url else "long"
                    verified_until = valid_period_from_cover(payload,source_kind,checked_date=today)
                    if not verified_until:
                        entry.setdefault("rejections", []).append({"invalidOrExpiredCover":True})
                        continue
                    entries = parse_pdf(payload,link,verified_until,checked_date=today,
                                        max_pages=12)
                    entry.update({"httpStatus":200,"pdfBytes":len(payload),
                                  "verifiedOffers":len(entries),
                                  "sample":[[o["name"],o["price"]] for o in entries[:8]]})
                    for item in entries:
                        merge_metro_offer(items, conflicting_ids, item)
                    if entries:
                        break
                except Exception as pdf_exc:
                    entry.setdefault("rejections", []).append({"error":str(pdf_exc)[:140]})
            diagnostics.append(entry)
        except Exception as exc:
            entry["error"] = str(exc)[:180]
            diagnostics.append(entry)
    if stats is not None:
        stats.update({"officialSources":diagnostics,"offersParsed":len(items),
                      "conflictingPriceIds":len(conflicting_ids),
                      "fullCatalog":False,
                      "scope":"Official METRO listings and individually validated PDF price labels only"})
    if not items:
        raise RuntimeError("No individually validated offers from official METRO sources: "+
                           str(diagnostics)[:200])
    return list(items.values())
