#!/usr/bin/env python3
"""Verified public promotions from the official METRO Ukraine website.

Source: https://www.metro.ua/propositions (default store: Kyiv Pozniaky).
Never use Zakaz.ua, guessed prices, VAT-exclusive prices or unrelated cards.
"""
import datetime as dt
import hashlib
import re

SOURCE = "https://www.metro.ua/propositions"
NUMBER = r"(\d[\d\s\u00a0\u202f]{0,9}[.,]\d{2})"
OFFER = re.compile(
    r"(?<!\w)Акція\s+((?:(?!\bАкція\b).){7,190}?)\s+"
    r"(Available|Limited\s+Availability|Not\s+Available)\s+"
    + NUMBER + r"\s*₴\s*" + NUMBER
    + r"\s*₴\s*[-−]\s*(\d{1,2})\s*%",
    re.I | re.S,
)


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
    from metro_catalog_pdf import parse_pdf
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=2))).date().isoformat()
    diagnostics = []
    items = {}
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
                items[item["id"]] = item
        except Exception as exc:
            diagnostics.append({"source":url,"error":str(exc)[:100]})

    catalogs = [
      ("https://promotions.metro.ua/katalogh-vighidnikh-vikhidnikh/",
       "https://promotions.metro.ua/834/2320121/pdfs/1a7d1e2b-ede4-4724-b6d5-ec2c2b286c77.pdf",
       "2026-11-08"),
      ("https://promotions.metro.ua/katalogh-vighidnikh-propozitsii",
       "https://promotions.metro.ua/834/2320153/pdfs/4c86826c-5dae-4b5a-9fab-a97f239eaee9.pdf",
       "2026-12-01"),
    ]
    for catalog_url, known_pdf, valid_to in catalogs:
        if valid_to < today:
            continue
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
            # Known PDFs were verified in run #228; never use expired links.
            link = links[0] if links else known_pdf
            pdf_response = await page.request.get(link,timeout=35000)
            payload = await pdf_response.body()
            if not pdf_response.ok or not payload.startswith(b"%PDF-"):
                entry.update({"httpStatus":pdf_response.status,"pdfValid":False})
                diagnostics.append(entry)
                continue
            entries = parse_pdf(payload,link.split("?")[0],valid_to,checked_date=today,
                                max_pages=12)
            entry.update({"httpStatus":200,"pdfBytes":len(payload),
                          "verifiedOffers":len(entries),
                          "sample":[[o["name"],o["price"]] for o in entries[:8]]})
            diagnostics.append(entry)
            for item in entries:
                # Do not silently override contradictory values across PDFs.
                existing = items.get(item["id"])
                if existing is None or existing["price"] == item["price"]:
                    items[item["id"]] = item
        except Exception as exc:
            entry["error"] = str(exc)[:180]
            diagnostics.append(entry)
    if stats is not None:
        stats.update({"officialSources":diagnostics,"offersParsed":len(items),
                      "fullCatalog":False,
                      "scope":"Official METRO listings and individually validated PDF price labels only"})
    if not items:
        raise RuntimeError("No individually validated offers from official METRO sources: "+
                           str(diagnostics)[:200])
    return list(items.values())
